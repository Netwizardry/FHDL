"""
FHDL 수리 해석 솔버.
2-Pass Newton-Raphson 기반 정상상태 수압 평형 계산.
입력: EntityMap (정규화 완료)
출력: (node_results, pipe_results, summary, diagnostics)
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Set, Tuple

import networkx as nx

from .fittings import elbow_k_for_angle
from .models import (
    AnalysisResult, ConstraintConfig, DiagnosticItem, EntityMap,
    FluidConfig, NodeCalcResult, PipeCalcResult, PipeEntity,
    SourceSpan, SystemSummary,
)

G = 9.80665  # m/s²

# 표준 관경 테이블 (KS, 내경 m)
_KS_DIAMETERS_M = [
    0.0127, 0.0159, 0.0211, 0.0267, 0.0352, 0.0422,
    0.0528, 0.0686, 0.0825, 0.1023, 0.1263, 0.1503,
    0.2027, 0.2527, 0.3027, 0.3527, 0.4027, 0.5027,
]


# ---------------------------------------------------------------------------
# 마찰 손실 계산
# ---------------------------------------------------------------------------

def _darcy_weisbach(q_m3s: float, d_m: float, L: float,
                    roughness_m: float, nu: float) -> Tuple[float, float, float]:
    """DW 마찰 손실 수두 반환: (h_f, velocity, f)"""
    A = math.pi * (d_m / 2) ** 2
    v = abs(q_m3s) / max(A, 1e-12)
    if v < 1e-9:
        return 0.0, 0.0, 0.0
    Re = v * d_m / max(nu, 1e-12)
    if Re < 2000:
        f = 64.0 / max(Re, 1e-9)
    elif Re < 4000:
        f_l = 64.0 / 2000.0
        f_t = _colebrook(roughness_m / d_m, 4000.0)
        s = (Re - 2000.0) / 2000.0
        w = 3 * s * s - 2 * s * s * s
        f = f_l * (1 - w) + f_t * w
    else:
        f = _colebrook(roughness_m / d_m, Re)
    h_f = f * (L / d_m) * (v * v) / (2 * G)
    return h_f, v, f


def _colebrook(rel_rough: float, Re: float) -> float:
    """Swamee-Jain 근사식 (Colebrook-White 대용)"""
    term = (rel_rough / 3.7) + (5.74 / max(Re ** 0.9, 1e-9))
    denom = math.log10(max(term, 1e-20))
    return 0.25 / max(denom ** 2, 1e-20)


def _hazen_williams(q_m3s: float, d_m: float, L: float, C: float) -> Tuple[float, float]:
    """HW 마찰 손실 수두 반환: (h_f, velocity)"""
    A = math.pi * (d_m / 2) ** 2
    v = abs(q_m3s) / max(A, 1e-12)
    if abs(q_m3s) < 1e-12:
        return 0.0, 0.0
    h_f = 10.67 * L * (abs(q_m3s) ** 1.852) / (max(C, 1.0) ** 1.852 * max(d_m, 1e-6) ** 4.87)
    return h_f, v


def _minor_loss(v: float, K: float) -> float:
    return K * (v * v) / (2 * G)


# ---------------------------------------------------------------------------
# 솔버
# ---------------------------------------------------------------------------

class HydraulicSolver:

    def __init__(self, em: EntityMap, cancel_fn: Optional[Callable[[], bool]] = None):
        self.em = em
        self.fluid = em.fluid
        self.cancel_fn = cancel_fn
        self._diags: List[DiagnosticItem] = []
        self._pump_suction: Dict[str, float] = {}
        self._pipe_lookup: Optional[Dict] = None

        self._nu = self.fluid.kinematic_viscosity
        self._rho = self.fluid.density
        self._p_atm = self.fluid.atm_pressure
        self._p_vap = self.fluid.vapor_pressure
        self._h_atm = self._p_atm / (self._rho * G)

    def solve(self) -> Tuple[
        List[NodeCalcResult], List[PipeCalcResult], SystemSummary
    ]:
        self._diags = []

        # 연결 그래프 구성
        adj, rev_adj = self._build_adj()

        # 노드 인덱스 맵 (탱크/펌프/분기점/말단)
        node_ids = self.em.all_node_ids()
        if not node_ids:
            self._err("NET002", "노드가 없습니다.", SourceSpan())
            return [], [], SystemSummary()

        # 탱크/소스 검증
        sources = list(self.em.tanks) + list(self.em.pumps)
        if not sources:
            self._err("NET002", "공급원(tank/pump)이 없습니다.", SourceSpan(),
                      "최소 1개의 tank 또는 pump를 정의하세요.")
            return [], [], SystemSummary()

        # 토폴로지 무결성 검사 (NET001/003/004/005)
        self._validate_network(adj, sources)
        # connect ↔ pipe 정합성 (NET006)
        self._check_connect_pipe_consistency()

        terminals = list(self.em.terminals)
        if not terminals:
            self._warn("WRN002",
                       "말단 장치(terminal)가 정의되지 않아 요구 유량이 0입니다.",
                       SourceSpan(),
                       "최소 1개의 terminal을 정의해 요구 유량을 지정하세요.")

        # 꺾임각 기반 자동 피팅 K (auto_k) 산정
        self._compute_auto_fitting_k(adj, rev_adj)

        # Pass 1: 유량 역산
        #   node_demand: 노드별 누적 요구유량 (소스 방향)
        #   pipe_q:      배관별 통과 유량 (파이프 ID 기준)
        node_demand, pipe_q = self._pass1_flow_synthesis(adj, rev_adj, sources, terminals)

        # 펌프 공급 수두(흡입수두 − 흡입관손실 + 양정) 사전 계산
        pump_init = self._pump_supply_heads(rev_adj, pipe_q)

        # Pass 2: 수압 평형 (Newton-Raphson) — 배관 유량 기준 마찰손실 반영
        head_map = self._pass2_hydraulic_balance(adj, pipe_q, sources, pump_init)

        # 결과 수집
        node_results, pipe_results = self._collect_results(node_demand, pipe_q, head_map)

        # 사양 산정
        summary = self._compute_summary(node_results, pipe_results, head_map, node_demand, sources)

        return node_results, pipe_results, summary

    @property
    def diagnostics(self) -> List[DiagnosticItem]:
        return self._diags

    # ------------------------------------------------------------------
    # 인접 맵 구성
    # ------------------------------------------------------------------

    def _build_adj(self) -> Tuple[Dict, Dict]:
        """엣지의 단일 진실원은 배관(pipe.start_id→end_id)이다.

        connect 문은 토폴로지를 정의하지 않고 배관과의 정합성만 검증한다
        (_check_connect_pipe_consistency). 배관 없는 connect 는 엣지를 만들지
        않으므로 해당 경로는 도달불가(NET003)로 드러난다.
        """
        adj: Dict[str, List[str]] = {}
        rev_adj: Dict[str, List[str]] = {}

        for nid in self.em.all_node_ids():
            adj[nid] = []
            rev_adj[nid] = []

        for pipe in self.em.pipes.values():
            s, e = pipe.start_id, pipe.end_id
            if not s or not e:
                continue
            if s not in adj:
                adj[s] = []
            if e not in rev_adj:
                rev_adj[e] = []
            if e not in adj[s]:
                adj[s].append(e)
            if s not in rev_adj[e]:
                rev_adj[e].append(s)

        return adj, rev_adj

    def _check_connect_pipe_consistency(self) -> None:
        """connect 문과 배관의 정합성 검사 (NET006).

        엣지는 배관이 정의한다. 노드-노드 connect 인데 대응 배관이 없으면
        (또는 방향이 반대이면) 해당 연결은 수리계산에서 무시되므로 경고한다.
        """
        node_ids = set(self.em.all_node_ids())
        pipe_fwd = {(p.start_id, p.end_id) for p in self.em.pipes.values()
                    if p.start_id and p.end_id}
        seen: Set[Tuple[str, str]] = set()
        for f, t in self.em.connections:
            if f not in node_ids or t not in node_ids:
                continue  # 배관 ID 가 끼인 연결은 끝점 추론에서 처리됨
            if (f, t) in pipe_fwd or (f, t) in seen:
                continue
            seen.add((f, t))
            if (t, f) in pipe_fwd:
                self._warn("NET006",
                           f"연결 '{f} -> {t}' 방향이 배관과 반대입니다. 배관 방향(start→end)을 따릅니다.",
                           SourceSpan(),
                           "connect 방향 또는 배관의 start/end 를 일치시키세요.")
            else:
                self._warn("NET006",
                           f"연결 '{f} -> {t}'에 대응하는 배관(pipe)이 없어 수리계산에서 제외됩니다.",
                           SourceSpan(),
                           f"'{f}'와 '{t}'를 잇는 pipe 블록을 정의하세요.")

    def _get_pipe(self, from_id: str, to_id: str) -> Optional[PipeEntity]:
        # (start,end) → pipe O(1) 조회 (대규모 네트워크 성능). 최초 1회 구축.
        lookup = self._pipe_lookup
        if lookup is None:
            lookup = {}
            for p in self.em.pipes.values():
                lookup.setdefault((p.start_id, p.end_id), p)
            self._pipe_lookup = lookup
        return lookup.get((from_id, to_id))

    def _node_elevation(self, nid: str) -> float:
        entity = self.em.get_node_entity(nid)
        if entity:
            return entity.elevation
        return 0.0

    def _node_span(self, nid: str) -> SourceSpan:
        ent = self.em.get_node_entity(nid)
        return getattr(ent, "span", None) or SourceSpan()

    def _node_type(self, nid: str) -> str:
        if nid in self.em.tanks:
            return "tank"
        if nid in self.em.pumps:
            return "pump"
        if nid in self.em.terminals:
            return "terminal"
        return "junction"

    # ------------------------------------------------------------------
    # 해발고도(datum) 기반 대기압
    # ------------------------------------------------------------------

    def _abs_altitude(self, nid: str) -> float:
        """노드의 절대 해발고도 = 프로젝트 datum(altitude) + 노드 상대 z."""
        return self.fluid.altitude + self._node_elevation(nid)

    def _atm_pa_at(self, nid: str) -> float:
        """노드 실제 해발고도에서의 대기압(Pa)."""
        return FluidConfig.atm_pressure_at(self._abs_altitude(nid))

    # ------------------------------------------------------------------
    # 펌프 공급 수두 / 자동 피팅 K
    # ------------------------------------------------------------------

    def _pipe_loss(self, pipe: PipeEntity, q: float) -> float:
        """배관의 총 손실수두(마찰 + 국부) — 흡입관 손실 등 보조 계산용."""
        d = pipe.diameter.value
        L = pipe.length if pipe.length > 0 else 1.0
        if self.em.fluid.friction_model == "HW":
            h_f, v = _hazen_williams(q, d, L, pipe.c_factor)
        else:
            h_f, v, _ = _darcy_weisbach(q, d, L, pipe.roughness, self._nu)
        return h_f + _minor_loss(v, pipe.total_k)

    def _pump_supply_heads(self, rev_adj: Dict[str, List[str]],
                           pipe_q: Dict[str, float]) -> Dict[str, float]:
        """펌프별 공급 수두 = 흡입 가용수두 + 양정(manual head).

        흡입수두 = (상류 탱크 수면 수두) − (흡입관 마찰·국부손실). 상류 탱크가 없으면
        펌프 고도를 흡입수두로 본다. head.mode 가 AUTO 인 펌프는 양정 0(사양 선정 대상),
        MANUAL 양정 펌프는 실제 에너지원으로 주입한다.
        """
        res: Dict[str, float] = {}
        for pid, pump in self.em.pumps.items():
            suction = pump.elevation
            for up in rev_adj.get(pid, []):
                if up in self.em.tanks:
                    tk = self.em.tanks[up]
                    suction = tk.elevation + tk.level_max
                    # 흡입관(탱크→펌프) 마찰·국부손실 차감
                    suc_pipe = self._get_pipe(up, pid)
                    if suc_pipe is not None:
                        q = pipe_q.get(suc_pipe.entity_id, 0.0)
                        suction -= self._pipe_loss(suc_pipe, q)
                    break
            self._pump_suction[pid] = suction   # 흡입측 공급 수두(양정 적용 전)
            boost = pump.head.value if pump.head.mode == "MANUAL" else 0.0
            res[pid] = suction + boost
        return res

    def _dir_vec(self, a: str, b: str):
        ea = self.em.get_node_entity(a)
        eb = self.em.get_node_entity(b)
        if not ea or not eb:
            return None
        dx = getattr(eb, "x", 0.0) - getattr(ea, "x", 0.0)
        dy = getattr(eb, "y", 0.0) - getattr(ea, "y", 0.0)
        dz = eb.elevation - ea.elevation
        if abs(dx) < 1e-12 and abs(dy) < 1e-12 and abs(dz) < 1e-12:
            return None
        return (dx, dy, dz)

    @staticmethod
    def _turn_angle(a, b) -> float:
        dot = a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
        na = math.sqrt(a[0]**2 + a[1]**2 + a[2]**2)
        nb = math.sqrt(b[0]**2 + b[1]**2 + b[2]**2)
        if na < 1e-9 or nb < 1e-9:
            return 0.0
        cos = max(-1.0, min(1.0, dot / (na * nb)))
        return math.degrees(math.acos(cos))

    def _compute_auto_fitting_k(self, adj: Dict[str, List[str]],
                               rev_adj: Dict[str, List[str]]) -> None:
        """경로 꺾임각으로 각 하류 배관의 자동 엘보 K(auto_k)를 산정한다.

        노드에서 (들어오는 배관 방향 ↔ 나가는 배관 방향) 사이 각도를 구해,
        가장 잘 정렬된(직진에 가까운) 진입 배관 기준 엘보 K 를 나가는 배관에 더한다.
        좌표/고도가 없어 방향을 알 수 없으면 0(영향 없음).
        """
        for pipe in self.em.pipes.values():
            pipe.auto_k = 0.0
        for nid in self.em.all_node_ids():
            ups = rev_adj.get(nid, [])
            downs = adj.get(nid, [])
            if not ups or not downs:
                continue
            for dn in downs:
                out_pipe = self._get_pipe(nid, dn)
                v_out = self._dir_vec(nid, dn)
                if out_pipe is None or v_out is None:
                    continue
                best_angle = None
                for up in ups:
                    v_in = self._dir_vec(up, nid)
                    if v_in is None:
                        continue
                    ang = self._turn_angle(v_in, v_out)
                    if best_angle is None or ang < best_angle:
                        best_angle = ang
                if best_angle is not None:
                    out_pipe.auto_k += elbow_k_for_angle(best_angle)

    # ------------------------------------------------------------------
    # 토폴로지 무결성 검사 (NET001/003/004/005)
    # ------------------------------------------------------------------

    def _validate_network(self, adj: Dict[str, List[str]], sources: List[str]) -> None:
        """공급원 기준 도달성·고립·순환 루프를 검사하여 NET 진단을 생성한다.

        - NET001: 고립 노드 (진입/진출 차수 모두 0)
        - NET003: 공급원에서 도달 불가
        - NET004: 복합 루프(단순 병렬 외 순환) 경고
        - NET005: 공급원 없는 순환 루프(Dead Loop) 에러
        """
        node_ids = self.em.all_node_ids()
        if not node_ids:
            return

        g = nx.DiGraph()
        g.add_nodes_from(node_ids)
        for s, dests in adj.items():
            if s not in g:
                continue
            for d in dests:
                if d in g:
                    g.add_edge(s, d)

        source_set = set(sources)

        # 공급원에서 순방향 도달 가능 집합
        reachable: Set[str] = set(source_set)
        for src in source_set:
            if src in g:
                reachable |= nx.descendants(g, src)

        for nid in node_ids:
            isolated = g.in_degree(nid) == 0 and g.out_degree(nid) == 0
            if isolated:
                # NET001: 고립 노드
                self._err("NET001",
                          f"노드 '{nid}'가 어떤 배관과도 연결되어 있지 않습니다.",
                          self._node_span(nid),
                          "해당 노드를 배관(pipe)으로 연결하거나 정의를 제거하세요.")
            elif nid not in source_set and nid not in reachable:
                # NET003: 도달 불가 (고립·공급원 제외)
                self._err("NET003",
                          f"노드 '{nid}'가 어떤 공급원에서도 도달할 수 없습니다.",
                          self._node_span(nid),
                          "공급원(tank/pump)에서 해당 노드까지 경로를 연결하세요.")

        # 순환 루프 탐지: SCC 크기>1 또는 자기 루프
        for scc in nx.strongly_connected_components(g):
            is_cycle = len(scc) > 1 or any(g.has_edge(n, n) for n in scc)
            if not is_cycle:
                continue
            members = ", ".join(sorted(scc))
            if any(n in reachable for n in scc):
                # NET004: 공급원과 연결된 복합 루프 → 경고
                self._warn("NET004",
                           f"복합 루프(단순 병렬 외 순환)가 감지되었습니다: {{{members}}}. "
                           f"v0.1은 트리/단순 병렬만 지원합니다.",
                           SourceSpan(),
                           "루프를 단순 트리형으로 수정하거나 v0.2 업그레이드를 대기하세요.")
            else:
                # NET005: 공급원 없는 순환 루프 → 에러
                self._err("NET005",
                          f"공급원 없는 순환 루프(Dead Loop)가 발견되었습니다: {{{members}}}.",
                          SourceSpan(),
                          "루프를 끊거나 외부 공급원(tank/pump)과 연결하세요.")

    # ------------------------------------------------------------------
    # Pass 1: 유량 역산
    # ------------------------------------------------------------------

    def _pass1_flow_synthesis(
        self,
        adj: Dict, rev_adj: Dict,
        sources: List[str], terminals: List[str],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """말단 요구유량을 역방향으로 집계하여 각 배관 q_design (m³/s) 결정.

        반환: (node_demand, pipe_q)
          - node_demand: 노드 ID → 누적 요구유량
          - pipe_q:      파이프 ID → 통과 유량
        """
        # 각 노드의 누적 유량 (소스 방향으로)
        demand: Dict[str, float] = {}

        for tid in terminals:
            term = self.em.terminals.get(tid)
            if term:
                demand[tid] = term.required_q

        # BFS 역방향 탐색
        queue = list(terminals)
        visited: Set[str] = set(terminals)
        while queue:
            nid = queue.pop(0)
            upstreams = rev_adj.get(nid, [])
            total_q = demand.get(nid, 0.0)
            n_up = len(upstreams)
            for up in upstreams:
                demand[up] = demand.get(up, 0.0) + total_q / max(n_up, 1)
                if up not in visited:
                    visited.add(up)
                    queue.append(up)

        # 배관별 유량 결정 (말단=end_node demand 기반)
        #   배관 (a→b)의 통과 유량 = b 하류 누적 요구유량을, b로 들어오는
        #   배관 수로 균등 분배 (트리: 1개, 단순 병렬: n개)
        in_pipe_count: Dict[str, int] = {}
        for p in self.em.pipes.values():
            in_pipe_count[p.end_id] = in_pipe_count.get(p.end_id, 0) + 1

        pipe_q: Dict[str, float] = {}
        for pipe in self.em.pipes.values():
            share = max(in_pipe_count.get(pipe.end_id, 1), 1)
            pipe_q[pipe.entity_id] = demand.get(pipe.end_id, 0.0) / share

        # 배관 관경 자동 선정 (배관별 실제 통과 유량 기준)
        for pipe in self.em.pipes.values():
            if pipe.diameter.mode == "AUTO":
                q = pipe_q.get(pipe.entity_id, 0.0)
                if q > 0:
                    d = self._select_diameter(q)
                    pipe.diameter.value = d
                    pipe.diameter.mode = "AUTO"
                else:
                    pipe.diameter.value = _KS_DIAMETERS_M[2]  # 기본 최소값
                    pipe.diameter.mode = "AUTO"

        return demand, pipe_q

    def _select_diameter(self, q: float) -> float:
        """유속 제약(v_max)을 만족하는 최소 표준 관경 선정"""
        v_max = self.em.constraints.velocity_max
        for d in _KS_DIAMETERS_M:
            A = math.pi * (d / 2) ** 2
            v = q / max(A, 1e-12)
            if v <= v_max:
                return d
        # 최대 관경으로도 불가
        self._err("CAL005",
                  f"요구 유량 {q*1e6:.1f} L/s 에 대해 유속 제약({v_max}m/s)을 만족하는 표준 관경이 없습니다.",
                  SourceSpan(),
                  "velocity_max 제한을 완화하거나 요구 유량을 줄이세요.")
        return _KS_DIAMETERS_M[-1]

    # ------------------------------------------------------------------
    # Pass 2: Newton-Raphson 수압 평형
    # ------------------------------------------------------------------

    def _pass2_hydraulic_balance(
        self,
        adj: Dict, pipe_q: Dict[str, float],
        sources: List[str],
        pump_init: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """노드별 수두 H (m) 계산 (배관 통과 유량 pipe_q 기준 마찰손실 반영)"""
        all_ids = self.em.all_node_ids()
        pump_init = pump_init or {}

        # 초기 수두: 탱크는 고도+수위, 펌프는 공급수두(흡입+양정), 나머지는 고도
        head: Dict[str, float] = {}
        for nid in all_ids:
            if nid in self.em.tanks:
                tank = self.em.tanks[nid]
                head[nid] = tank.elevation + tank.level_max
            elif nid in self.em.pumps:
                head[nid] = pump_init.get(nid, self.em.pumps[nid].elevation)
            else:
                head[nid] = self._node_elevation(nid)

        tol = 1e-4
        max_iter = 100
        damping = 0.5
        converged = False

        for iteration in range(max_iter):
            if self.cancel_fn and self.cancel_fn():
                break

            delta_max = 0.0

            # 소스에서 BFS 순방향으로 수두 전파
            queue = list(sources)
            processed: Set[str] = set(sources)
            while queue:
                nid = queue.pop(0)
                downstreams = adj.get(nid, [])
                for ds in downstreams:
                    if ds in processed:
                        continue

                    pipe = self._get_pipe(nid, ds)
                    if pipe is None:
                        continue

                    q = pipe_q.get(pipe.entity_id, 0.0)
                    d = pipe.diameter.value
                    L = pipe.length
                    if L <= 0:
                        # 좌표 기반 길이 계산
                        n1 = self.em.get_node_entity(nid)
                        n2 = self.em.get_node_entity(ds)
                        if n1 and n2 and hasattr(n1, 'x') and hasattr(n2, 'x'):
                            dx = getattr(n1, 'x', 0) - getattr(n2, 'x', 0)
                            dy = getattr(n1, 'y', 0) - getattr(n2, 'y', 0)
                            dz = n1.elevation - n2.elevation
                            L = max(math.sqrt(dx*dx + dy*dy + dz*dz), 0.1)
                            pipe.length = L
                        else:
                            L = 1.0
                            pipe.length = L

                    if self.em.fluid.friction_model == "HW":
                        h_f, v = _hazen_williams(q, d, L, pipe.c_factor)
                    else:
                        h_f, v, _ = _darcy_weisbach(q, d, L, pipe.roughness, self._nu)

                    h_k = _minor_loss(v, pipe.total_k)
                    h_loss = h_f + h_k
                    z_ds = self._node_elevation(ds)

                    # 수두 갱신
                    new_head_ds = head[nid] - h_loss
                    delta = abs(new_head_ds - head.get(ds, z_ds))
                    head[ds] = head.get(ds, z_ds) * damping + new_head_ds * (1 - damping)
                    delta_max = max(delta_max, delta)

                    processed.add(ds)
                    queue.append(ds)

            if delta_max < tol:
                converged = True
                break

        if not converged:
            self._err("CAL002",
                      f"Newton-Raphson 수압 평형이 {max_iter}회 반복 후 수렴하지 않았습니다.",
                      SourceSpan(),
                      "네트워크 구조를 단순화하거나 초기값을 조정하세요.")

        return head

    # ------------------------------------------------------------------
    # 결과 수집
    # ------------------------------------------------------------------

    def _collect_results(
        self,
        demand: Dict[str, float],
        pipe_q: Dict[str, float],
        head: Dict[str, float],
    ) -> Tuple[List[NodeCalcResult], List[PipeCalcResult]]:
        node_results = []
        pipe_results = []

        # 노드 결과
        for nid in self.em.all_node_ids():
            h = head.get(nid, self._node_elevation(nid))
            z = self._node_elevation(nid)
            p_gauge = (h - z) * self._rho * G

            # NPSHa (펌프 노드)
            npsha = 0.0
            if nid in self.em.pumps:
                pump = self.em.pumps[nid]
                # NPSHa = 대기압수두 + 흡입정수두 − 증기압수두
                #   대기압: 펌프 실제 해발(datum+z)로 산정 (온도+해발 → 기압)
                #   흡입정수두: 흡입측 공급수두 − 펌프 고도
                p_atm = self._atm_pa_at(nid)
                h_atm = p_atm / (self._rho * G)
                h_vap = self._p_vap / (self._rho * G)
                h_s = self._pump_suction.get(nid, pump.elevation) - pump.elevation
                npsha = h_atm + h_s - h_vap
                if npsha < pump.npshr * self.em.constraints.safety_factor_npsh:
                    self._warn("WRN003",
                               f"펌프 '{nid}': NPSHa({npsha:.2f}m) < NPSHr({pump.npshr:.2f}m) × SF({self.em.constraints.safety_factor_npsh})",
                               pump.span,
                               "수조 수위를 높이거나 흡입관 손실을 줄이세요.")

            ent = self.em.get_node_entity(nid)
            node_results.append(NodeCalcResult(
                node_id=nid,
                node_type=self._node_type(nid),
                x=getattr(ent, "x", 0.0) if ent else 0.0,
                y=getattr(ent, "y", 0.0) if ent else 0.0,
                z=z,
                head_total=h,
                p_gauge=p_gauge,
                flow_in=demand.get(nid, 0.0),
                flow_out=demand.get(nid, 0.0),
                npsha=npsha,
                abs_altitude=self._abs_altitude(nid),
                atm_pressure=self._atm_pa_at(nid),
            ))

        # 배관 결과
        for pipe in self.em.pipes.values():
            q = pipe_q.get(pipe.entity_id, 0.0)
            d = pipe.diameter.value
            L = pipe.length
            if L <= 0:
                L = 1.0

            if self.em.fluid.friction_model == "HW":
                h_f, v = _hazen_williams(q, d, L, pipe.c_factor)
                formula = "FOR-HW-001"
            else:
                h_f, v, _ = _darcy_weisbach(q, d, L, pipe.roughness, self._nu)
                formula = "FOR-DW-001"

            h_k = _minor_loss(v, pipe.total_k)
            status = "OK"

            # 유속 검사
            v_min = self.em.constraints.velocity_min
            v_max = self.em.constraints.velocity_max
            if v > v_max:
                status = "WARNING"
                self._warn("WRN001",
                           f"배관 '{pipe.entity_id}': 유속 {v:.2f}m/s > 최대 {v_max}m/s",
                           pipe.span,
                           "관경을 키우거나 유량을 줄이세요.")
            elif 0 < v < v_min:
                self._warn("WRN001",
                           f"배관 '{pipe.entity_id}': 유속 {v:.2f}m/s < 최소 {v_min}m/s",
                           pipe.span,
                           "관경을 줄이세요.")

            # 수충격 위험 지수
            wave_v = 1200.0  # 기본 압력파 속도 (m/s)
            p_allow = 2.0e6  # 기본 허용 압력 (Pa)
            surge_idx = (self._rho * wave_v * v) / max(p_allow, 1.0)
            if surge_idx > 0.8:
                self._warn("WRN004",
                           f"배관 '{pipe.entity_id}': 수충격 위험 지수 {surge_idx:.2f} > 0.8",
                           pipe.span,
                           "관경을 키우거나 유속을 낮추세요.")

            pipe_results.append(PipeCalcResult(
                pipe_id=pipe.entity_id,
                start_id=pipe.start_id,
                end_id=pipe.end_id,
                flow=q,
                velocity=v,
                h_loss_f=h_f,
                h_loss_k=h_k,
                diameter=d,
                sizing_mode=pipe.diameter.mode,
                surge_index=surge_idx,
                formula_id=formula,
                status=status,
                k_total=pipe.total_k,
                k_auto=pipe.auto_k,
            ))

        return node_results, pipe_results

    # ------------------------------------------------------------------
    # 사양 산정
    # ------------------------------------------------------------------

    def _compute_summary(
        self,
        node_results: List[NodeCalcResult],
        pipe_results: List[PipeCalcResult],
        head: Dict[str, float],
        demand: Dict[str, float],
        sources: List[str],
    ) -> SystemSummary:
        summary = SystemSummary()

        # 총 유량 = 모든 터미널 요구유량 합산
        total_q = sum(t.required_q for t in self.em.terminals.values())
        summary.total_flow = total_q

        # 최불리 경로 탐색: 소스에서 각 터미널까지 경로 중 최대 요구 수두
        source_head = 0.0
        for src in sources:
            h = head.get(src, 0.0)
            if h > source_head:
                source_head = h

        # 배관 손실 / 상류 배관 조회 맵 (트리 가정: 노드당 진입 배관 1개)
        loss_by_pipe = {pr.pipe_id: abs(pr.h_loss_total) for pr in pipe_results}
        incoming_pipe: Dict[str, PipeEntity] = {}
        for p in self.em.pipes.values():
            incoming_pipe.setdefault(p.end_id, p)

        def _upstream_path(node_id: str) -> List[str]:
            """말단 → 소스 방향 경로(소스가 앞으로 오도록 정렬)"""
            path: List[str] = []
            seen: Set[str] = set()
            cur: Optional[str] = node_id
            while cur is not None and cur not in seen:
                path.append(cur)
                seen.add(cur)
                p = incoming_pipe.get(cur)
                cur = p.start_id if p else None
            return list(reversed(path))

        # 각 말단별: 정적 요구수두 + 경로 마찰손실 합이 최대인 경로 = 최불리 경로
        max_total_head = 0.0
        for tid, term in self.em.terminals.items():
            path = _upstream_path(tid)
            path_loss = sum(
                loss_by_pipe.get(incoming_pipe[n].entity_id, 0.0)
                for n in path if n in incoming_pipe
            )
            req_static = term.elevation + term.required_p / (self._rho * G)
            total_head = (req_static - source_head) + path_loss
            if total_head > max_total_head:
                max_total_head = total_head
                summary.worst_path = path

        summary.required_head = max(max_total_head, 0.0)

        sf = self.em.constraints.safety_factor_head
        summary.recommended_pump_flow = total_q
        summary.recommended_pump_head = summary.required_head * sf

        # 탱크 용량 (총유량 × 1시간)
        summary.recommended_tank_volume = total_q * 3600.0
        summary.converged = True

        # Provenance map
        for pr in pipe_results:
            summary.provenance_map[pr.pipe_id] = {
                "formula_id": pr.formula_id,
                "diameter_mode": pr.sizing_mode,
                "flow_m3s": pr.flow,
            }

        # 진공 한계 경고 — 노드 실제 해발의 대기압 기준(절대압 0 이하면 진공)
        for nr in node_results:
            if nr.p_gauge <= -self._atm_pa_at(nr.node_id):
                self._warn("WRN005",
                           f"노드 '{nr.node_id}': 압력이 진공 한계({nr.p_gauge:.0f}Pa)에 도달했습니다.",
                           SourceSpan(),
                           "극단적인 부압 원인을 확인하세요.")

        return summary

    # ------------------------------------------------------------------
    # 진단 헬퍼
    # ------------------------------------------------------------------

    def _err(self, code: str, msg: str, span: SourceSpan, action: str = ""):
        self._diags.append(DiagnosticItem(
            code=code, severity="ERROR", message=msg,
            source_span=span, suggested_action=action,
        ))

    def _warn(self, code: str, msg: str, span: SourceSpan, action: str = ""):
        self._diags.append(DiagnosticItem(
            code=code, severity="WARNING", message=msg,
            source_span=span, suggested_action=action,
        ))
