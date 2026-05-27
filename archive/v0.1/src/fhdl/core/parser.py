import re
import os
from typing import Optional, Dict, List
from src.fhdl.core.models import FluidSystem, Node, Pipe, Material, NodeType, ValveType, PumpCurve
from src.fhdl.core.library_manager import LibraryManager, UnitConverter

class FHDLSerializer:
    """FluidSystem 객체를 .fhd 텍스트로 변환 (데이터 무결성 강화)"""
    @staticmethod
    def serialize(system: FluidSystem) -> str:
        u = system.units; lines = []
        lines.append("System_Setup {")
        lines.append(f"    Units = {u};")
        lines.append(f"    Fluid_Type = {system.fluid_type};")
        t_user = system.temp if u == "METRIC" else (system.temp * 9/5 + 32)
        lines.append(f"    Temp = {t_user};")
        alt_user = UnitConverter.from_m(system.altitude, u)
        lines.append(f"    Altitude = {alt_user};")
        lines.append(f"    Step = {system.step};")
        lines.append("}\n")
        
        if system.materials or system.presets or system.pump_curves:
            lines.append("Component_Library {")
            for mat in system.materials.values():
                szs = ", ".join([f"{k}:{v}" for k, v in mat.size_map.items()])
                lines.append(f"    Material {mat.id}({mat.roughness}, [{szs}], {mat.max_pressure}, {mat.wave_velocity});")
            for pid, pre in system.presets.items():
                lines.append(f"    Preset {pid}({pre['type']}, {pre['k_factor']});")
            for cid, curve in system.pump_curves.items():
                hq_pts = ", ".join([f"({p[0]}, {p[1]})" for p in curve.hq_points])
                npshr_pts = ", ".join([f"({p[0]}, {p[1]})" for p in curve.npshr_points])
                lines.append(f"    PumpCurve {cid}([{hq_pts}], [{npshr_pts}], {curve.static_npshr});")
            lines.append("}\n")
            
        lines.append("Topology {")
        for node in system.nodes.values():
            x = UnitConverter.from_m(node.x, u); y = UnitConverter.from_m(node.y, u); z = UnitConverter.from_m(node.z, u)
            ps = [repr(x), repr(y), repr(z), node.type.name]
            if node.required_q != 0 or node.required_p != 0 or node.k_factor != 0:
                val = node.k_factor if node.k_factor != 0 else node.required_q
                q_u = UnitConverter.from_m3s(val/60000.0, u) if u == "METRIC" else UnitConverter.from_m3s(UnitConverter.to_m3s(val, "METRIC"), u)
                p_u = UnitConverter.from_pa(node.required_p*1000000, u)
                ps.extend([repr(q_u), repr(p_u)])
            lines.append(f"    node {node.id}({', '.join(ps)});")
            
        for pipe in system.pipes.values():
            sz = pipe.nominal_size if pipe.nominal_size else str(pipe.diameter)
            ps = [pipe.start_node, pipe.end_node, sz, pipe.material_id]
            # 감사 지적 반영: 오직 수동 입력 피팅값만 저장하여 누적 방지
            if pipe.manual_fittings_k != 0: ps.append(repr(pipe.manual_fittings_k))
            lines.append(f"    pipe {pipe.id}({', '.join(ps)});")
            if pipe.valve_type:
                st = "OPEN" if pipe.is_open else "CLOSED"
                v_name = pipe.valve_id if pipe.valve_id else f"{pipe.id}_v"
                lines.append(f"    valve {v_name}({pipe.id}, {pipe.valve_type.name}, {st});")
        lines.append("}")
        return "\n".join(lines)

class FHDLParserError(Exception):
    def __init__(self, code: str, message: str, line: int, col: int):
        self.code = code; self.message = message; self.line = line; self.col = col
        super().__init__(f"[{code}] Line {line}, Col {col}: {message}")

class FHDLParser:
    def __init__(self):
        self.system = FluidSystem()

    def strip_comments(self, text: str) -> str:
        text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), text, flags=re.DOTALL)
        return re.sub(r'//.*', '', text)

    def _get_line_at_index(self, original_text: str, index: int) -> int:
        return original_text[:index].count('\n') + 1

    def _clean_params(self, params_str: str) -> List[str]:
        clean_str = re.sub(r'/\*.*?\*/', '', params_str)
        return [p.strip() for p in clean_str.split(',') if p.strip()]

    def parse(self, text: str) -> FluidSystem:
        self.system = FluidSystem(); self._valve_ids = set(); self._library_ids = {} # 감사 지적 반영: 라이브러리 ID 추적 (ID: Line)
        clean_text = self.strip_comments(text)
        self._parse_library_block(text, clean_text)
        self._parse_setup_block(text, clean_text)
        self._parse_topology_block(text, clean_text)
        self._parse_sequence_block(text, clean_text) # 감사 지적 반영: 시퀀스 파싱 추가
        self._apply_auto_fitting()
        return self.system

    def _parse_sequence_block(self, raw_text: str, clean_text: str):
        """시계열 해석을 위한 이벤트 시퀀스 파싱 (감사 지적 반영)"""
        match = re.search(r'Sequence\s*\{(.*?)\}', clean_text, re.IGNORECASE | re.DOTALL)
        if not match: return
        block_start = match.start(1); content = match.group(1)
        for i, line in enumerate(content.split('\n')):
            ln = self._get_line_at_index(raw_text, block_start) + i; line = line.strip().rstrip(';')
            if not line or not line.lower().startswith('event'): continue

            # event Time(TargetID, Action, Params...)
            m = re.search(r'event\s+([\d.]+)\s*\(\s*(.*?)\s*\)', line, re.IGNORECASE)
            if m:
                time_s = float(m.group(1)); ps = self._clean_params(m.group(2))
                if len(ps) < 2: continue
                target, action = ps[0], ps[1].upper()
                params = ps[2:] if len(ps) > 2 else []
                from src.fhdl.core.models import Event
                self.system.sequence.append(Event(time=time_s, target_id=target, action=action, params={"args": params}))


    def _apply_auto_fitting(self):
        for nid, node in self.system.nodes.items():
            conn = [p for p in self.system.pipes.values() if nid in [p.start_node, p.end_node]]
            # 1. 분기점 (Tee/Cross) 손실 (K=1.8)
            if len(conn) >= 3:
                for p in conn: p.auto_fittings_k = 1.8
            # 2. 엘보우(Elbow) 및 리듀서(Reducer) 손실
            if len(conn) == 2:
                p1, p2 = conn
                n1_o = p1.end_node if p1.start_node == nid else p1.start_node
                n2_o = p2.end_node if p2.start_node == nid else p2.start_node
                if n1_o in self.system.nodes and n2_o in self.system.nodes:
                    # 방향 벡터 계산 (각도 손실용)
                    v1 = (self.system.nodes[n1_o].x - self.system.nodes[nid].x, self.system.nodes[n1_o].y - self.system.nodes[nid].y, self.system.nodes[n1_o].z - self.system.nodes[nid].z)
                    v2 = (self.system.nodes[n2_o].x - self.system.nodes[nid].x, self.system.nodes[n2_o].y - self.system.nodes[nid].y, self.system.nodes[n2_o].z - self.system.nodes[nid].z)
                    k_angle = LibraryManager.calculate_angle_k(v1, v2)
                    
                    # 감사 지적 반영: 리듀서(관경 변화) 손실 자동 계산
                    d1, d2 = p1.diameter, p2.diameter
                    k_reducer = 0.0
                    if abs(d1 - d2) > 0.1:
                        # 흐름 방향(p1->p2 가정)에 따른 확대/축소 판별
                        # (엄밀하게는 유향 그래프를 따라야 하나, 여기서는 보수적으로 더 큰 손실값 적용)
                        beta = min(d1, d2) / max(d1, d2)
                        k_exp = (1 - beta**2)**2
                        k_con = 0.5 * (1 - beta**2)
                        k_reducer = max(k_exp, k_con)
                    
                    p1.auto_fittings_k = (k_angle / 2) + (k_reducer / 2)
                    p2.auto_fittings_k = (k_angle / 2) + (k_reducer / 2)

    def _check_lib_id(self, entity_id: str, line_no: int):
        """라이브러리 엔티티 간 ID 중복 체크 (Material vs Preset vs PumpCurve)"""
        if entity_id in self._library_ids:
            old_ln = self._library_ids[entity_id]
            raise FHDLParserError("FHDL_ID_DUPLICATE", f"Library ID '{entity_id}' collision (First defined at line {old_ln})", line_no, 0)
        self._library_ids[entity_id] = line_no

    def _parse_library_block(self, raw_text: str, clean_text: str):
        match = re.search(r'Component_Library\s*\{(.*?)\}', clean_text, re.IGNORECASE | re.DOTALL)
        if not match: return
        block_start = match.start(1); content = match.group(1)
        for i, line in enumerate(content.split('\n')):
            ln = self._get_line_at_index(raw_text, block_start) + i; line = line.strip().rstrip(';')
            if not line: continue
            if line.lower().startswith('material'):
                m = re.search(r'Material\s+(\w+)\s*\(\s*(.*?)\s*\)', line, re.IGNORECASE)
                if m:
                    name, ps_str = m.groups()
                    self._check_lib_id(name, ln) # 중복 체크
                    sz_m = re.search(r'\[(.*?)\]', ps_str)
                    if not sz_m: raise FHDLParserError("FHDL_SYNTAX_ERROR", f"Material '{name}' missing map", ln, 0)
                    others = [p.strip() for p in re.sub(r'\[.*?\]', 'SZ_MAP', ps_str).split(',')]
                    try:
                        sz_map = {k.strip(): float(v.strip()) for pair in sz_m.group(1).split(',') if ':' in pair for k, v in [pair.split(':')]}
                        rough = float(others[0]); idx = others.index('SZ_MAP'); extra = others[idx+1:]
                        self.system.add_material(Material(id=name, roughness=rough, size_map=sz_map, max_pressure=float(extra[0]) if len(extra)>0 else 2.0, wave_velocity=float(extra[1]) if len(extra)>1 else 1200.0))
                    except Exception as e: raise FHDLParserError("FHDL_INVALID_PARAM", str(e), ln, 0)
            elif line.lower().startswith('preset'):
                m = re.search(r'Preset\s+(\w+)\s*\(\s*(.*?)\s*\)', line, re.IGNORECASE)
                if m:
                    pid, ps_str = m.groups(); ps = self._clean_params(ps_str)
                    self._check_lib_id(pid, ln) # 중복 체크
                    if len(ps) >= 2: self.system.presets[pid] = {"type": ps[0].upper(), "k_factor": float(ps[1])}
            elif line.lower().startswith('pumpcurve'):
                # 감사 지적 반영: NPSHr 곡선 및 고정 NPSHr 지원 (greedy match for nested parens)
                m = re.search(r'PumpCurve\s+(\w+)\s*\((.*)\)', line, re.IGNORECASE)
                if m:
                    cid, ps_str = m.groups()
                    self._check_lib_id(cid, ln) # 중복 체크
                    lists = re.findall(r'\[(.*?)\]', ps_str)
                    hq = []; npshr_pts = []; static_npshr = 0.5
                    if len(lists) >= 1:
                        hq = [(float(p.group(1)), float(p.group(2))) for p in re.finditer(r'\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', lists[0])]
                    if len(lists) >= 2:
                        npshr_pts = [(float(p.group(1)), float(p.group(2))) for p in re.finditer(r'\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', lists[1])]
                    
                    others = re.sub(r'\[.*?\]', '', ps_str).split(',')
                    others = [o.strip() for o in others if o.strip()]
                    if others:
                        try: static_npshr = float(others[0])
                        except: pass
                    self.system.pump_curves[cid] = PumpCurve(id=cid, hq_points=hq, npshr_points=npshr_pts, static_npshr=static_npshr)

    def _parse_setup_block(self, raw_text: str, clean_text: str):
        match = re.search(r'System_Setup\s*\{(.*?)\}', clean_text, re.IGNORECASE | re.DOTALL)
        if not match: return
        content = match.group(1); u_m = re.search(r'Units\s*=\s*(\w+)', content, re.IGNORECASE); u = u_m.group(1).upper() if u_m else "METRIC"
        self.system.units = u
        f_m = re.search(r'Fluid_Type\s*=\s*(\w+)', content, re.IGNORECASE)
        if f_m: self.system.fluid_type = f_m.group(1)
        t_m = re.search(r'Temp\s*=\s*([\d.]+)', content, re.IGNORECASE)
        if t_m: self.system.temp = UnitConverter.to_c(float(t_m.group(1)), u)
        a_m = re.search(r'Altitude\s*=\s*([\d.-]+)', content, re.IGNORECASE)
        if a_m: self.system.altitude = UnitConverter.to_m(float(a_m.group(1)), u)
        s_m = re.search(r'Step\s*=\s*([\d.]+)', content, re.IGNORECASE)
        if s_m: self.system.step = float(s_m.group(1))

    def _parse_topology_block(self, raw_text: str, clean_text: str):
        match = re.search(r'Topology\s*\{(.*?)\}', clean_text, re.IGNORECASE | re.DOTALL)
        if not match: return
        block_start = match.start(1); content = match.group(1)
        for i, line in enumerate(content.split('\n')):
            ln = self._get_line_at_index(raw_text, block_start) + i; line = line.strip().rstrip(';')
            if not line: continue
            if line.lower().startswith('node'):
                m = re.search(r'node\s+(\w+)\s*\((.*?)\)', line, re.IGNORECASE)
                if m:
                    nid, ps_str = m.groups(); ps = self._clean_params(ps_str)
                    node = Node(id=nid, x=UnitConverter.to_m(float(ps[0]), self.system.units), y=UnitConverter.to_m(float(ps[1]), self.system.units), z=UnitConverter.to_m(float(ps[2]), self.system.units), type=NodeType[ps[3].upper()])
                    if len(ps) > 4:
                        val = ps[4]
                        if val in self.system.presets: node.k_factor = self.system.presets[val]["k_factor"]
                        elif node.type == NodeType.PUMP and val in self.system.pump_curves: 
                            node.pump_curve = self.system.pump_curves[val]
                        else:
                            try: qv = float(val); node.required_q = UnitConverter.to_m3s(qv, self.system.units)*60000.0 if node.type != NodeType.PUMP else 0
                            except: pass
                    if len(ps) > 5: node.required_p = UnitConverter.to_pa(float(ps[5]), self.system.units)/1_000_000.0
                    self.system.add_node(node)
            elif line.lower().startswith('pipe'):
                m = re.search(r'pipe\s+(\w+)\s*\((.*?)\)', line, re.IGNORECASE)
                if m:
                    pid, ps_str = m.groups(); ps = self._clean_params(ps_str)
                    start, end, sz_id, mat_id = ps[0:4]
                    if start not in self.system.nodes or end not in self.system.nodes:
                        missing = start if start not in self.system.nodes else end
                        raise FHDLParserError("FHDL_UNDEFINED_REF", f"Pipe '{pid}' references undefined node: '{missing}'", ln, 0)
                    
                    # 감사 지적 반영: 관경 유효성(양수) 검증
                    try:
                        actual_dia = float(sz_id) if re.match(r'^[\d.]+$', sz_id) else LibraryManager.get_actual_id(mat_id, sz_id, self.system)
                        if actual_dia <= 0: raise ValueError("Diameter must be positive")
                    except Exception as e: raise FHDLParserError("FHDL_INVALID_VALUE", str(e), ln, 0)
                    
                    pipe = Pipe(id=pid, start_node=start, end_node=end, diameter=actual_dia, material_id=mat_id, nominal_size="" if re.match(r'^[\d.]+$', sz_id) else sz_id)
                    if len(ps) > 4: pipe.manual_fittings_k = float(ps[4])
                    self.system.add_pipe(pipe)
            elif line.lower().startswith('valve'):
                m = re.search(r'valve\s+(\w+)\s*\((.*?)\)', line, re.IGNORECASE)
                if m:
                    vid, ps_str = m.groups(); ps = self._clean_params(ps_str)
                    # 감사 지적 반영: 밸브 ID 중복 체크
                    if vid in self._valve_ids: raise FHDLParserError("FHDL_ID_DUPLICATE", f"Valve ID '{vid}' collision", ln, 0)
                    self._valve_ids.add(vid)
                    if len(ps) == 3:
                        pid, vtype, status = ps; p = self.system.pipes.get(pid)
                        if p: p.valve_type = ValveType[vtype.upper()]; p.valve_id = vid; p.is_open = (status == "OPEN")
                    elif len(ps) == 4:
                        start, end, vtype, status = ps
                        if start not in self.system.nodes or end not in self.system.nodes: raise FHDLParserError("FHDL_UNDEFINED_REF", f"Valve '{vid}' nodes error", ln, 0)
                        for p in self.system.pipes.values():
                            if p.start_node == start and p.end_node == end:
                                p.valve_type = ValveType[vtype.upper()]; p.valve_id = vid; p.is_open = (status == "OPEN")
