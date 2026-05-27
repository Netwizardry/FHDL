"""
FHDL 수리 해석 솔버.
2-Pass Newton-Raphson 기반 정상상태 수압 평형 계산.
입력: EntityMap (정규화 완료)
출력: (node_results, pipe_results, summary, diagnostics)
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Set, Tuple

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

        terminals = list(self.em.terminals)
        if not terminals:
            self._warn("NET001", "말단 장치(terminal)가 없습니다.", SourceSpan())

        # Pass 1: 유량 역산
        q_map = self._pass1_flow_synthesis(adj, rev_adj, sources, terminals)

        # Pass 2: 수압 평형 (Newton-Raphson)
        head_map = self._pass2_hydraulic_balance(adj, q_map, sources)

        # 결과 수집
        node_results, pipe_results = self._collect_results(q_map, head_map)

        # 사양 산정
        summary = self._compute_summary(node_results, pipe_results, head_map, q_map, sources)

        return node_results, pipe_results, summary

    @property
    def diagnostics(self) -> List[DiagnosticItem]:
        return self._diags

    # ------------------------------------------------------------------
    # 인접 맵 구성
    # ------------------------------------------------------------------

    def _build_adj(self) -> Tuple[Dict, Dict]:
        adj: Dict[str, List[str]] = {}
        rev_adj: Dict[str, List[str]] = {}

        for nid in self.em.all_node_ids():
            adj[nid] = []
            rev_adj[nid] = []

        for pipe in self.em.pipes.values():
            s, e = pipe.start_id, pipe.end_id
            if s not in adj:
                adj[s] = []
            if e not in rev_adj:
                rev_adj[e] = []
            if e not in adj[s]:
                adj[s].append(e)
            if s not in rev_adj[e]:
                rev_adj[e].append(s)

        # 연결(connect) 구문으로 추가된 엣지
        # 파이프 ID는 물리적 배관이므로 노드 ID만 처리한다
        node_ids_set = set(self.em.all_node_ids())
        pipe_edges = {(p.start_id, p.end_id) for p in self.em.pipes.values()}
        for from_id, to_id in self.em.connections:
            # 양쪽 모두 노드 ID인 경우만 엣지 추가
            if from_id not in node_ids_set or to_id not in node_ids_set:
                continue
            if (from_id, to_id) not in pipe_edges:
                if from_id not in adj:
                    adj[from_id] = []
                if to_id not in rev_adj:
                    rev_adj[to_id] = []
                if to_id not in adj[from_id]:
                    adj[from_id].append(to_id)
                if from_id not in rev_adj[to_id]:
                    rev_adj[to_id].append(from_id)

        return adj, rev_adj

    def _get_pipe(self, from_id: str, to_id: str) -> Optional[PipeEntity]:
        for p in self.em.pipes.values():
            if p.start_id == from_id and p.end_id == to_id:
                return p
        return None

    def _node_elevation(self, nid: str) -> float:
        entity = self.em.get_node_entity(nid)
        if entity:
            return entity.elevation
        return 0.0

    # ------------------------------------------------------------------
    # Pass 1: 유량 역산
    # ------------------------------------------------------------------

    def _pass1_flow_synthesis(
        self,
        adj: Dict, rev_adj: Dict,
        sources: List[str], terminals: List[str],
    ) -> Dict[str, float]:
        """말단 요구유량을 역방향으로 집계하여 각 배관 q_design (m³/s) 결정"""
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

        # 배관별 유량 결정 (start_node demand 기반)
        pipe_q: Dict[str, float] = {}
        for pipe in self.em.pipes.values():
            pipe_q[pipe.entity_id] = demand.get(pipe.start_id, 0.0)

        # 배관 관경 자동 선정
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

        return demand

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
        adj: Dict, q_map: Dict[str, float],
        sources: List[str],
    ) -> Dict[str, float]:
        """노드별 수두 H (m) 계산"""
        all_ids = self.em.all_node_ids()

        # 초기 수두: 탱크는 고도+수위, 나머지는 고도
        head: Dict[str, float] = {}
        for nid in all_ids:
            if nid in self.em.tanks:
                tank = self.em.tanks[nid]
                head[nid] = tank.elevation + tank.level_max
            elif nid in self.em.pumps:
                head[nid] = self.em.pumps[nid].elevation
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

                    q = q_map.get(pipe.entity_id, 0.0)
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
                h_s = h - pump.elevation
                h_fs = max(0.0, (self._p_atm - p_gauge) / (self._rho * G))
                npsha = self._h_atm - (self._p_vap / (self._rho * G)) + h_s - h_fs
                if npsha < pump.npshr * self.em.constraints.safety_factor_npsh:
                    self._warn("WRN003",
                               f"펌프 '{nid}': NPSHa({npsha:.2f}m) < NPSHr({pump.npshr:.2f}m) × SF({self.em.constraints.safety_factor_npsh})",
                               pump.span,
                               "수조 수위를 높이거나 흡입관 손실을 줄이세요.")

            node_results.append(NodeCalcResult(
                node_id=nid,
                head_total=h,
                p_gauge=p_gauge,
                flow_in=demand.get(nid, 0.0),
                flow_out=demand.get(nid, 0.0),
                npsha=npsha,
            ))

        # 배관 결과
        for pipe in self.em.pipes.values():
            q = demand.get(pipe.entity_id, demand.get(pipe.start_id, 0.0))
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
                flow=q,
                velocity=v,
                h_loss_f=h_f,
                h_loss_k=h_k,
                diameter=d,
                sizing_mode=pipe.diameter.mode,
                surge_index=surge_idx,
                formula_id=formula,
                status=status,
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

        max_req_head = 0.0
        for tid, term in self.em.terminals.items():
            t_head = head.get(tid, term.elevation)
            req_head = (term.elevation + term.required_p / (self._rho * G)) - source_head
            if req_head > max_req_head:
                max_req_head = req_head
                summary.worst_path = [sources[0] if sources else "", tid]

        # 최불리 경로 손실 합산
        path_loss = sum(abs(pr.h_loss_total) for pr in pipe_results)
        summary.required_head = max(max_req_head + path_loss, 0.0)

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

        # 진공 한계 경고
        for nr in node_results:
            if nr.p_gauge < -1e5:
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
