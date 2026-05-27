import math
from typing import Dict, List, Tuple, Optional, Set, Callable
from src.fhdl.core.models import FluidSystem, Node, Pipe, NodeType, ValveType
from src.fhdl.core.library_manager import UnitConverter

class FHDLSolverError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code; self.message = message
        super().__init__(f"[{code}] {message}")

class Solver:
    def __init__(self, system: FluidSystem, verbose: bool = False, 
                 interruption_check: Optional[Callable[[], bool]] = None):
        self.system = system
        self.g = 9.80665
        self.rho = system.actual_density
        self.max_iter = 500 # 반복 횟수 상향
        self.tol = 1e-6
        self.verbose = verbose
        self.interruption_check = interruption_check
        self._node_demands: Dict[str, float] = {}
        self._pre_calc_velocities: Dict[str, float] = {}

    def _log(self, msg: str):
        if self.verbose: print(f"[Solver Log] {msg}")

    def _check_abort(self):
        if self.interruption_check and self.interruption_check():
            raise InterruptedError("Solver aborted by user.")

    def _get_dw_params(self, pipe: Pipe, velocity: float) -> Tuple[float, float]:
        n1 = self.system.nodes.get(pipe.start_node); n2 = self.system.nodes.get(pipe.end_node)
        l = max(math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2 + (n1.z - n2.z)**2), 0.001)
        d_m = UnitConverter.mm_to_m(pipe.diameter)
        mat = self.system.materials.get(pipe.material_id); c_or_eps = mat.roughness if mat else 120.0
        epsilon_m = (0.045 / 1000.0) if c_or_eps > 1.0 else (c_or_eps / 1000.0)
        visc = UnitConverter.calculate_viscosity(self.system.temp, self.system.fluid_type)
        v_abs = max(abs(velocity), 1e-6); re = (v_abs * d_m) / visc
        
        def calc_turb_f(re_val):
            term = (epsilon_m / (3.7 * d_m)) + (5.74 / (re_val**0.9))
            return 0.25 / (math.log10(max(term, 1e-10))**2)

        if re < 2000: f = 64 / re
        elif re < 4000:
            f_l = 64 / 2000.0; f_t = calc_turb_f(4000.0); s = (re - 2000.0) / 2000.0; weight = 3 * s**2 - 2 * s**3
            f = f_l * (1 - weight) + f_t * weight
        else: f = calc_turb_f(re)
        k_dw = f * (l / d_m) / (2 * self.g)
        return l, k_dw

    def _get_total_loss(self, pipe: Pipe, q_m3s: float) -> float:
        d_m = UnitConverter.mm_to_m(pipe.diameter); area = math.pi * (d_m / 2)**2
        velocity = q_m3s / area; l, k_dw = self._get_dw_params(pipe, velocity)
        h_f = k_dw * (velocity**2); h_m = pipe.total_k * (velocity**2) / (2 * self.g)
        pipe.length = l; pipe.velocity = velocity; pipe.head_loss = h_f + h_m
        pipe.flow = UnitConverter.from_m3s(q_m3s, "METRIC"); return pipe.head_loss

    def solve_pass1(self) -> bool:
        node_flow = {nid: n.required_q for nid, n in self.system.nodes.items()}
        out_deg = {nid: len(self.system.get_downstream(nid)) for nid in self.system.nodes}
        queue = [nid for nid, deg in out_deg.items() if deg == 0]
        processed = 0
        while queue:
            self._check_abort(); curr_id = queue.pop(0); processed += 1
            up_ids = self.system.get_upstream(curr_id)
            if up_ids:
                in_pipes = [p for p in self.system.pipes.values() if p.end_node == curr_id and p.start_node in up_ids]
                total_d2 = sum(p.diameter**2 for p in in_pipes)
                for pipe in in_pipes:
                    q_share = node_flow[curr_id] * (pipe.diameter**2 / max(total_d2, 1e-6))
                    node_flow[pipe.start_node] += q_share; out_deg[pipe.start_node] -= 1
                    if out_deg[pipe.start_node] == 0: queue.append(pipe.start_node)
        if processed < len(self.system.nodes): return False 
        for node in self.system.nodes.values():
            if node.head == 0: node.head = node.z
        terminals = [n for n in self.system.nodes.values() if n.type == NodeType.TERMINAL]
        for tid in [t.id for t in terminals]:
            t = self.system.nodes[tid]; p_pa = UnitConverter.to_pa(t.required_p, "METRIC")
            t.head = (p_pa / (self.rho * self.g)) + t.z
            up_ids = self.system.get_upstream(tid)
            if not up_ids: continue
            in_pipes = [p for p in self.system.pipes.values() if p.end_node == tid and p.start_node in up_ids]
            for pipe in in_pipes:
                up_id = pipe.start_node; up_node = self.system.nodes[up_id]
                hf = self._get_total_loss(pipe, UnitConverter.to_m3s(node_flow[tid]/len(in_pipes), "METRIC"))
                if t.head + hf > up_node.head and up_node.type != NodeType.TANK: up_node.head = t.head + hf
        return True

    def solve_pass2(self):
        for pid, pipe in self.system.pipes.items(): self._pre_calc_velocities[pid] = pipe.velocity
        damping = 0.5; p_vap = UnitConverter.calculate_vapor_pressure(self.system.temp, self.system.fluid_type)
        vacuum_warned = set()
        
        for iteration in range(self.max_iter):
            self._check_abort(); max_delta_h = 0.0
            # 1. 펌프 토출 수두 업데이트 (흡입 수두 + 양정 곡선)
            for nid, node in self.system.nodes.items():
                if node.type == NodeType.PUMP and node.pump_curve:
                    in_pipes = [p for p in self.system.pipes.values() if p.end_node == nid]
                    h_s = sum(self.system.nodes[p.start_node].head - p.head_loss for p in in_pipes)/len(in_pipes) if in_pipes else node.z
                    q_out = sum(p.flow for p in self.system.pipes.values() if p.start_node == nid)
                    target_h = h_s + node.pump_curve.get_head(abs(q_out))
                    node.head += (target_h - node.head) * 0.3
            
            # 2. 질량 평형 (JUNCTION, TERMINAL, PUMP 모두 포함)
            for nid, node in self.system.nodes.items():
                if node.type == NodeType.TANK: continue
                if node.type == NodeType.TERMINAL and node.k_factor > 0:
                    p_mpa = max((node.head - node.z) * self.rho * self.g / 1_000_000.0, 1e-6)
                    q_t = node.k_factor * math.sqrt(p_mpa); node.actual_q = q_t; sq = -UnitConverter.to_m3s(q_t, "METRIC")
                    sdq = (node.k_factor / 60000.0) * (1.0 / (2 * math.sqrt(p_mpa))) * (self.rho * self.g / 1_000_000.0)
                else: sq = -UnitConverter.to_m3s(node.required_q, "METRIC"); sdq = 0
                
                for pipe in self.system.pipes.values():
                    if nid not in [pipe.start_node, pipe.end_node]: continue
                    is_start = (pipe.start_node == nid); other = self.system.nodes[pipe.end_node if is_start else pipe.start_node]
                    d_m = UnitConverter.mm_to_m(pipe.diameter); area = math.pi * (d_m / 2)**2
                    dh = other.head - node.head; abs_dh = abs(dh)
                    _, k_dw = self._get_dw_params(pipe, 0.1); k_t = k_dw + (pipe.total_k / (2 * self.g))
                    if abs_dh > 1e-5:
                        q = math.copysign(area * math.sqrt(abs_dh / max(k_t, 1e-10)), dh)
                        dq = (area / 2.0) * (1.0 / math.sqrt(max(abs_dh * k_t, 1e-12)))
                    else:
                        slope = (area / 2.0) * (1.0 / math.sqrt(1e-5 * max(k_t, 1e-10)))
                        q = dh * slope; dq = slope
                    
                    if not pipe.is_open or (pipe.valve_type == ValveType.CHECK and ((dh > 0) if is_start else (dh < 0))):
                        q, dq = 0.0, 1e-10
                    sq += q; sdq += dq
                
                if sdq > 0:
                    delta = (sq / sdq) * damping; node.head += delta; max_delta_h = max(max_delta_h, abs(delta))
                
                p_abs = self.system.actual_p_atm + (node.head - node.z) * self.rho * self.g
                if p_abs < p_vap and nid not in vacuum_warned:
                    self._log(f"!!! VACUUM WARNING at Node {nid}: {p_abs/1000:.1f}kPa"); vacuum_warned.add(nid)
            
            if max_delta_h < self.tol: break

        for pipe in self.system.pipes.values():
            n1, n2 = self.system.nodes[pipe.start_node], self.system.nodes[pipe.end_node]
            dh = n1.head - n2.head; d_m = UnitConverter.mm_to_m(pipe.diameter); area = math.pi * (d_m / 2)**2
            _, k_dw = self._get_dw_params(pipe, 0.1); k_t = k_dw + (pipe.total_k / (2 * self.g))
            if not pipe.is_open or (pipe.valve_type == ValveType.CHECK and dh < 0): q_si = 0.0
            else: q_si = math.copysign(area * math.sqrt(max(abs(dh), 1e-7) / max(k_t, 1e-10)), dh)
            self._get_total_loss(pipe, q_si)

        for nid, node in self.system.nodes.items():
            q_in = sum(p.flow for p in self.system.pipes.values() if p.end_node == nid)
            q_out = sum(p.flow for p in self.system.pipes.values() if p.start_node == nid)
            if node.type in [NodeType.PUMP, NodeType.TANK]: node.actual_q = max(abs(q_in), abs(q_out))
            elif node.type != NodeType.TERMINAL: node.actual_q = abs(q_out - q_in)

    def calculate_water_hammer(self):
        for pid, pipe in self.system.pipes.items():
            if pipe.valve_type and not pipe.is_open:
                v = self._pre_calc_velocities.get(pid, 0.0)
                if v > 0:
                    mat = self.system.materials.get(pipe.material_id); a = mat.wave_velocity if mat else 1200.0
                    p_m = (self.rho * a * v) / 1_000_000.0; up = self.system.nodes.get(pipe.start_node)
                    if up: up.surge_pressure = max(up.surge_pressure, p_m)

    def calculate_npsha(self):
        p_vap = UnitConverter.calculate_vapor_pressure(self.system.temp, self.system.fluid_type); rho_g = self.rho * self.g
        for nid, node in self.system.nodes.items():
            if node.type == NodeType.PUMP:
                in_pipes = [p for p in self.system.pipes.values() if p.end_node == nid]
                h_s = sum(self.system.nodes[p.start_node].head - p.head_loss for p in in_pipes)/len(in_pipes) if in_pipes else node.head
                p_g = (h_s - node.z) * rho_g; npsha = (self.system.actual_p_atm + p_g - p_vap) / rho_g; node.npsha = npsha
                npshr = node.pump_curve.get_npshr(node.actual_q) if node.pump_curve else 0.5
                if npsha < npshr: print(f"[CRITICAL] !!! CAVITATION WARNING: Pump {nid} NPSHa({npsha:.2f}m) < NPSHr({npshr:.2f}m)!")

    def _apply_events(self, t: float):
        events = [e for e in self.system.sequence if abs(e.time - t) < self.system.step / 2]
        for e in events:
            self._log(f"Event at t={t}s: {e.target_id} -> {e.action}")
            if e.target_id in self.system.pipes:
                p = self.system.pipes[e.target_id]; p.is_open = (e.action == "OPEN")
            elif e.target_id in self.system.nodes:
                n = self.system.nodes[e.target_id]
                if e.action == "STOP": n.pump_curve = None
                elif e.action == "SET_P": n.required_p = float(e.params["args"][0])

    def run(self):
        try:
            if not self.solve_pass1():
                for n in self.system.nodes.values():
                    if n.type not in [NodeType.TANK, NodeType.PUMP]: n.head = 10.0
            max_t = max([e.time for e in self.system.sequence]) if self.system.sequence else 0.0; t = 0.0
            while t <= max_t:
                self._check_abort(); self._apply_events(t); self.solve_pass2()
                if t == 0 or any(abs(e.time - t) < self.system.step / 2 for e in self.system.sequence):
                    self.calculate_npsha(); self.calculate_water_hammer()
                if max_t == 0: break
                t += self.system.step
            return True
        except Exception as e: raise FHDLSolverError("FHDL_SOLVER_CRITICAL", str(e))
