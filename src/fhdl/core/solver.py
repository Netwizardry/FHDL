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
from .geometry import bend_angles, pipe_route, route_end_dirs
from .pipe_sizes import KS_DIAMETERS_M
from .models import (
    AnalysisResult, ConstraintConfig, DiagnosticItem, EntityMap,
    FluidConfig, NodeCalcResult, PipeCalcResult, PipeEntity,
    SourceSpan, SystemSummary,
)

G = 9.80665  # m/s²

# 표준 관경 테이블 (KS, 내경 m) — 단일 진실원은 core.pipe_sizes
_KS_DIAMETERS_M = KS_DIAMETERS_M


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
        self._diameters = list(em.constraints.diameters) or list(_KS_DIAMETERS_M)
        self.cancelled = False
        self.converged = True        # 반복 계산을 돌리지 않는 경로(빈 망 등)는 수렴으로 본다
        self.iterations = 0
        self.residual = 0.0
        self._diags: List[DiagnosticItem] = []
        self._pump_suction: Dict[str, float] = {}       # 운전 흡입수두 (탱크 최고 수위 level_max 기준)
        self._pump_suction_min: Dict[str, float] = {}   # 설계 흡입수두 (최저 수위 level_min 기준 — NPSHa·요구 양정)
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

        # 펌프 공급 수두(흡입수두 − 흡입관손실 + 양정/커브운전점) 사전 계산
        pump_init = self._pump_supply_heads(rev_adj, pipe_q, node_demand)

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

    @staticmethod
    def _curve_head(points, q: float) -> float:
        """펌프 커브 [(flow, head, eff)] 에서 유량 q 의 양정을 선형 보간(운전점)."""
        pts = sorted((p[0], p[1]) for p in points)
        if not pts:
            return 0.0
        if q <= pts[0][0]:
            return pts[0][1]
        if q >= pts[-1][0]:
            return pts[-1][1]
        for (q0, h0), (q1, h1) in zip(pts, pts[1:]):
            if q0 <= q <= q1:
                t = (q - q0) / (q1 - q0) if q1 > q0 else 0.0
                return h0 + (h1 - h0) * t
        return pts[-1][1]

    def _pump_boost(self, pump, q: float) -> float:
        """펌프 양정 결정: 커브가 있으면 운전점(유량 q)의 양정, 없으면 MANUAL head."""
        if pump.curve_points:
            return self._curve_head(pump.curve_points, q)
        return pump.head.value if pump.head.mode == "MANUAL" else 0.0

    def _pump_supply_heads(self, rev_adj: Dict[str, List[str]],
                           pipe_q: Dict[str, float],
                           node_demand: Dict[str, float]) -> Dict[str, float]:
        """펌프별 공급 수두 = 흡입 가용수두 + 양정.

        흡입수두 = (상류 탱크 수면 수두) − (흡입관 마찰·국부손실). 상류 탱크가 없으면
        펌프 고도를 흡입수두로 본다. 양정은 펌프 커브가 있으면 운전점(통과 유량)의 값,
        없으면 MANUAL head(AUTO 는 0, 사양 선정 대상)를 쓴다.
        """
        res: Dict[str, float] = {}
        for pid, pump in self.em.pumps.items():
            suction = pump.elevation
            # 상류로 거슬러 올라가 공급 탱크를 찾는다 (접합점을 거쳐도) — 흡입수두 = 탱크 수면 − 경로 손실
            suction_min = pump.elevation
            cur, loss, seen = pid, 0.0, {pid}
            while True:
                ups = [u for u in rev_adj.get(cur, []) if u not in seen]
                if not ups:
                    break
                up = ups[0]
                seen.add(up)
                p_ = self._get_pipe(up, cur)
                if p_ is not None:
                    loss += self._pipe_loss(p_, pipe_q.get(p_.entity_id, 0.0))
                if up in self.em.tanks:
                    tk = self.em.tanks[up]
                    suction = tk.elevation + tk.level_max - loss
                    suction_min = tk.elevation + tk.level_min - loss
                    break
                if up in self.em.pumps:                      # 직렬 펌프: 앞 펌프 토출까지만
                    break
                cur = up
            self._pump_suction[pid] = suction
            self._pump_suction_min[pid] = suction_min if suction_min != pump.elevation else suction
            boost = self._pump_boost(pump, node_demand.get(pid, 0.0))
            res[pid] = suction + boost
        return res

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
        """경로 꺾임각으로 각 배관의 자동 엘보 K(auto_k)를 산정한다.

        1) 배관 내부: 경유점(via)마다 꺾임각의 엘보 K 를 더한다.
        2) 노드: (들어오는 배관의 마지막 방향 ↔ 나가는 배관의 첫 방향) 사이 각도를 구해,
           가장 잘 정렬된(직진에 가까운) 진입 배관 기준 엘보 K 를 나가는 배관에 더한다.
        좌표(x/y)가 없어 방향을 알 수 없으면 0(영향 없음).
        """
        routes = {}
        for pipe in self.em.pipes.values():
            route = pipe_route(self.em, pipe)
            routes[pipe.entity_id] = route
            pipe.auto_k = sum(elbow_k_for_angle(a) for a in bend_angles(route)) if route else 0.0
        for nid in self.em.all_node_ids():
            ups = rev_adj.get(nid, [])
            downs = adj.get(nid, [])
            if not ups or not downs:
                continue
            for dn in downs:
                out_pipe = self._get_pipe(nid, dn)
                if out_pipe is None or routes.get(out_pipe.entity_id) is None:
                    continue
                v_out = route_end_dirs(routes[out_pipe.entity_id])[0]
                best_angle = None
                for up in ups:
                    in_pipe = self._get_pipe(up, nid)
                    if in_pipe is None or routes.get(in_pipe.entity_id) is None:
                        continue
                    v_in = route_end_dirs(routes[in_pipe.entity_id])[1]
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

        # 역위상 순서(하류가 모두 끝난 노드부터) 누적 — 깊이가 다른 가지의 유량도 빠짐없이 상류로 전달
        pending: Dict[str, int] = {}
        for nid, ups in rev_adj.items():
            for up in ups:
                pending[up] = pending.get(up, 0) + 1          # 하류로 나가는 연결 수(병렬 배관은 중복 포함)
        nodes = set(rev_adj) | set(pending) | set(terminals)
        ready = [n for n in nodes if pending.get(n, 0) == 0]
        done: Set[str] = set()
        while ready:
            nid = ready.pop()
            done.add(nid)
            upstreams = rev_adj.get(nid, [])
            total_q = demand.get(nid, 0.0)
            n_up = len(upstreams)
            for up in upstreams:
                demand[up] = demand.get(up, 0.0) + total_q / max(n_up, 1)
                pending[up] -= 1
                if pending[up] == 0:
                    ready.append(up)
        # 순환(NET004 경고)으로 남은 노드는 기존 방식대로 한 번 더 전달
        for nid in nodes - done:
            ups = rev_adj.get(nid, [])
            for up in ups:
                if up in done:
                    continue
                demand[up] = demand.get(up, 0.0) + demand.get(nid, 0.0) / max(len(ups), 1)

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
                    pipe.diameter.value = self._diameters[min(2, len(self._diameters) - 1)]  # 기본 최소값
                    pipe.diameter.mode = "AUTO"

        self._split_parallel(pipe_q)
        return demand, pipe_q

    def _split_parallel(self, pipe_q: Dict[str, float]) -> None:
        """같은 두 노드 사이 병렬 배관 — 손실수두가 같아지도록 유량을 나눈다 (h ≈ R·Q^n 반복)."""
        groups: Dict[Tuple[str, str], List] = {}
        for p in self.em.pipes.values():
            groups.setdefault((p.start_id, p.end_id), []).append(p)
        n = 1.852 if self.em.fluid.friction_model == "HW" else 2.0
        for ps in groups.values():
            if len(ps) < 2:
                continue
            total = sum(pipe_q.get(p.entity_id, 0.0) for p in ps)
            if total <= 0:
                continue
            q = {p.entity_id: total / len(ps) for p in ps}
            for _ in range(20):
                w = {}
                for p in ps:
                    qi = max(q[p.entity_id], total * 1e-6)
                    R = self._pipe_loss(p, qi) / qi ** n
                    w[p.entity_id] = R ** (-1.0 / n) if R > 0 else 1.0
                sw = sum(w.values())
                new = {k: total * v / sw for k, v in w.items()}
                diff = max(abs(new[k] - q[k]) for k in q)
                q = new
                if diff < total * 1e-6:
                    break
            pipe_q.update(q)

    def _select_diameter(self, q: float) -> float:
        """유속 제약(v_max)을 만족하는 최소 표준 관경 선정"""
        v_max = self.em.constraints.velocity_max
        for d in self._diameters:
            A = math.pi * (d / 2) ** 2
            v = q / max(A, 1e-12)
            if v <= v_max:
                return d
        # 최대 관경으로도 불가
        self._err("CAL005",
                  f"요구 유량 {q*1e3:.1f} L/s 에 대해 유속 제약({v_max}m/s)을 만족하는 표준 관경이 없습니다.",
                  SourceSpan(),
                  "velocity_max 제한을 완화하거나 요구 유량을 줄이세요.")
        return self._diameters[-1]

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

        delta_max = 0.0
        iteration = -1
        for iteration in range(max_iter):
            if self.cancel_fn and self.cancel_fn():
                self.cancelled = True
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

        self.converged = converged
        self.iterations = iteration + 1
        self.residual = delta_max
        if self.cancelled:
            self._err("CAL004", "사용자가 해석을 중단했습니다 — 결과는 유효하지 않습니다.", SourceSpan(),
                      "다시 해석(F5)하세요.")
        elif not converged:
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
                # NPSHa 는 최저 운전 수위 기준 (HI 관행 — 최고 수위로 보면 과대 평가)
                h_s = self._pump_suction_min.get(nid, pump.elevation) - pump.elevation
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
            wave_v = pipe.wave_velocity      # 재질별 압력파 속도 (m/s, 라이브러리·재질 표)
            p_allow = pipe.max_pressure      # 재질별 허용 압력 (Pa)
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
                length=pipe.length,
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

        # 최불리 경로 탐색: 각 말단은 '그 말단에 물을 대는' 경로 시작점(탱크 수면 또는 흡입 측 펌프)을 기준으로 한다
        def _root_head(nid: str) -> float:
            if nid in self.em.tanks:
                tk = self.em.tanks[nid]
                return tk.elevation + tk.level_min            # 요구 양정은 최저 수위에서 (불리한 쪽)
            if nid in self.em.pumps:
                return self._pump_suction_min.get(nid, self.em.pumps[nid].elevation)
            return self._node_elevation(nid)

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
            # 경로의 펌프 양정은 빼지 않는다 → '필요한 펌프 양정' (수동 양정 펌프의 흡입 손실 이중 계산 방지)
            total_head = (req_static - _root_head(path[0])) + path_loss
            if total_head > max_total_head:
                max_total_head = total_head
                summary.worst_path = path

        summary.required_head = max(max_total_head, 0.0)

        sf = self.em.constraints.safety_factor_head
        summary.recommended_pump_flow = total_q
        summary.recommended_pump_head = summary.required_head * sf

        # 탱크 용량 (총유량 × 1시간)
        summary.recommended_tank_volume = total_q * 3600.0
        summary.converged = self.converged and not self.cancelled
        summary.solve_iterations = self.iterations
        summary.residual = self.residual

        # Provenance map
        assumed = {}
        for (what, val), ids in self.em.defaults_applied.items():
            for i in ids:
                assumed.setdefault(i, []).append(f"{what}: {val}")
        for pr in pipe_results:
            pipe = self.em.pipes.get(pr.pipe_id)
            summary.provenance_map[pr.pipe_id] = {
                "formula_id": pr.formula_id,
                "diameter_mode": pr.sizing_mode,
                "flow_m3s": pr.flow,
                "source_line": pipe.span.line if pipe else 0,
                "inputs": [pr.start_id, pr.end_id],
                "assumptions": assumed.get(pr.pipe_id, []),
            }

        # AUTO 펌프(양정 미정·커브 없음) 하류 노드: 양정이 0 으로 주입된 사양 선정 전 상태라
        # 부압·요구압 미달은 펌프 양정으로 채울 몫 → WRN005/WRN006 대상에서 제외한다.
        sized_later: Set[str] = set()
        stack = [pid for pid, p in self.em.pumps.items()
                 if p.head.mode != "MANUAL" and not p.curve_points]
        while stack:
            nid = stack.pop()
            for p in self.em.pipes.values():
                if p.start_id == nid and p.end_id not in sized_later:
                    sized_later.add(p.end_id)
                    stack.append(p.end_id)

        # 진공 한계 경고 — 노드 실제 해발의 대기압 기준(절대압 0 이하면 진공)
        # 계산 압력이 증기압(절대) 아래면 물리적으로 불가능 → 표시값은 증기압 한계로 묶는다(S-SOL-007).
        pv = self.fluid.vapor_pressure
        for nr in node_results:
            floor = -self._atm_pa_at(nr.node_id) + pv
            raw = nr.p_gauge
            if raw < floor:
                nr.p_gauge = floor
            if nr.node_id in sized_later:
                continue
            if raw <= -self._atm_pa_at(nr.node_id) + pv:
                self._warn("WRN005",
                           f"노드 '{nr.node_id}': 계산 압력 {raw / 1e3:.0f} kPa(게이지)가 진공(증기압) 한계 "
                           f"{floor / 1e3:.1f} kPa 아래입니다 — 표시값은 한계로 제한했습니다.",
                           SourceSpan(),
                           "흡입 높이·관경·펌프 위치 등 극단적인 부압 원인을 확인하세요.")

        # 말단 요구압 미달 — 채울 펌프가 없으므로 실제 설계 결함이다.
        p_by_node = {nr.node_id: nr.p_gauge for nr in node_results}
        for tid, term in self.em.terminals.items():
            p = p_by_node.get(tid)
            if tid in sized_later or p is None:
                continue
            if p < term.required_p * (1 - 1e-3):
                self._warn("WRN006",
                           f"말단 '{tid}': 압력 {p:.0f}Pa 가 요구 압력 "
                           f"{term.required_p:.0f}Pa 에 미달합니다.",
                           term.span,
                           "펌프를 추가하거나(head=auto) 관경·공급 수두를 늘리세요.")

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
