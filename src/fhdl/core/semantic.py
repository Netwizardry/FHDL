"""
FHDL 의미 분석기 (Semantic Analyzer).
입력: AST 노드 리스트
출력: (EntityMap, SemanticDiagnostics)
단위 정규화, 기본값 주입, 참조 무결성 검사를 수행한다.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ASTNode, ComponentASTNode, ConnectASTNode, ConstraintASTNode,
    ConstraintConfig, DiagnosticItem, EntityMap, FluidConfig,
    JunctionEntity, PipeEntity, PumpEntity, SizingState,
    SourceSpan, SystemASTNode, TankEntity, TerminalEntity,
)


# ---------------------------------------------------------------------------
# 단위 변환 상수
# ---------------------------------------------------------------------------

_UNIT_TO_SI: Dict[str, float] = {
    # 길이
    "m": 1.0, "mm": 1e-3, "cm": 1e-2, "km": 1e3,
    "ft": 0.3048, "in": 0.0254, "inch": 0.0254,
    # 유량
    "m3s": 1.0, "m3/s": 1.0,
    "m3h": 1 / 3600.0, "m3/h": 1 / 3600.0,
    "lpm": 1 / 60000.0, "l/min": 1 / 60000.0, "lmin": 1 / 60000.0,
    "ls": 1e-3, "l/s": 1e-3,
    "gpm": 6.30902e-5, "gal/min": 6.30902e-5,
    # 압력
    "pa": 1.0,
    "kpa": 1e3, "mpa": 1e6, "bar": 1e5, "psi": 6894.76,
    "mwg": 9806.65,  # m수두
    # 체적
    "m3": 1.0, "l": 1e-3, "gal": 3.78541e-3,
    "": 1.0,  # 단위 없음: 무변환
}


def _to_si(value: float, unit: str) -> float:
    key = unit.lower().replace(" ", "")
    factor = _UNIT_TO_SI.get(key)
    if factor is None:
        return value
    return value * factor


# ---------------------------------------------------------------------------
# 의미 분석기
# ---------------------------------------------------------------------------

class SemanticAnalyzer:

    def analyze(
        self, ast: List[ASTNode]
    ) -> Tuple[EntityMap, List[DiagnosticItem]]:
        self._diags: List[DiagnosticItem] = []
        em = EntityMap()

        # 1차: 엔티티 생성
        for node in ast:
            if isinstance(node, SystemASTNode):
                em.fluid = self._build_fluid(node)
            elif isinstance(node, ComponentASTNode):
                self._build_entity(node, em)
            elif isinstance(node, ConnectASTNode):
                self._collect_connections(node, em)
            elif isinstance(node, ConstraintASTNode):
                em.constraints = self._build_constraints(node)

        # 2차: 참조 무결성 + 중복 ID
        self._check_references(em)

        return em, self._diags

    # ------------------------------------------------------------------
    # 시스템 설정
    # ------------------------------------------------------------------

    def _build_fluid(self, node: SystemASTNode) -> FluidConfig:
        a = node.attributes
        cfg = FluidConfig()
        cfg.fluid_type = str(a.get("fluid", "water")).lower()
        cfg.unit_system = str(a.get("unit_system", "METRIC")).upper()
        cfg.friction_model = str(a.get("friction_model", "DW")).upper()

        temp_raw = a.get("temp", 20.0)
        cfg.temp = self._as_float(temp_raw, "")
        if not (0 <= cfg.temp <= 100):
            self._warn("SEM006", f"유체 온도 {cfg.temp}°C는 허용 범위(0~100°C)를 벗어납니다.",
                       node.span, "temp를 0~100 사이로 설정하세요.")

        alt_raw = a.get("altitude", (0.0, "m"))
        cfg.altitude = self._as_si(alt_raw)
        if not (-500 <= cfg.altitude <= 10000):
            self._warn("SEM005", f"고도 {cfg.altitude}m는 허용 범위(-500~10000m)를 벗어납니다.",
                       node.span)

        return cfg

    # ------------------------------------------------------------------
    # 컴포넌트 엔티티 생성
    # ------------------------------------------------------------------

    def _build_entity(self, node: ComponentASTNode, em: EntityMap):
        a = node.attributes
        ctype = node.comp_type
        cid = node.comp_id
        span = node.span

        # 중복 ID 검사
        all_ids = (
            list(em.tanks) + list(em.pumps) + list(em.junctions)
            + list(em.terminals) + list(em.pipes)
        )
        if cid in all_ids:
            self._err("SEM001", f"ID '{cid}'가 중복 정의됩니다.", span,
                      "각 컴포넌트는 고유한 ID를 가져야 합니다.")
            return

        if ctype == "tank":
            elev = self._as_si(a.get("elevation", (0.0, "m")))
            self._check_elevation(elev, span)
            em.tanks[cid] = TankEntity(
                entity_id=cid,
                elevation=elev,
                volume=self._as_si(a.get("volume", float("inf"))),
                level_max=self._as_si(a.get("level_max", (2.0, "m"))),
                x=self._as_float(a.get("x", 0.0), ""),
                y=self._as_float(a.get("y", 0.0), ""),
                span=span,
            )

        elif ctype == "pump":
            elev = self._as_si(a.get("elevation", (0.0, "m")))
            self._check_elevation(elev, span)
            flow_raw = a.get("flow", "auto")
            head_raw = a.get("head", "auto")
            pump_type = str(a.get("pump_type", "normal")).lower()
            em.pumps[cid] = PumpEntity(
                entity_id=cid,
                elevation=elev,
                flow=self._sizing(flow_raw, "m3/s"),
                head=self._sizing(head_raw, "m"),
                efficiency=self._as_float(a.get("efficiency", 0.75), ""),
                npshr=self._as_si(a.get("npshr", (0.5, "m"))),
                curve_id=str(a.get("curve_id", "")),
                pump_type=pump_type,
                min_level=self._as_si(a.get("min_level", (0.0, "m"))),
                submerge_ref=str(a.get("submerge_ref", "")),
                x=self._as_float(a.get("x", 0.0), ""),
                y=self._as_float(a.get("y", 0.0), ""),
                span=span,
            )

        elif ctype == "junction":
            elev = self._as_si(a.get("elevation", (0.0, "m")))
            self._check_elevation(elev, span)
            em.junctions[cid] = JunctionEntity(
                entity_id=cid,
                elevation=elev,
                x=self._as_float(a.get("x", 0.0), ""),
                y=self._as_float(a.get("y", 0.0), ""),
                span=span,
            )

        elif ctype == "terminal":
            elev = self._as_si(a.get("elevation", (0.0, "m")))
            self._check_elevation(elev, span)
            em.terminals[cid] = TerminalEntity(
                entity_id=cid,
                elevation=elev,
                required_q=self._as_si(a.get("required_q", (0.0, "m3/s"))),
                required_p=self._as_si(a.get("required_p", (0.0, "pa"))),
                k_factor=self._as_float(a.get("k_factor", 0.0), ""),
                preset_id=str(a.get("preset_id", "")),
                x=self._as_float(a.get("x", 0.0), ""),
                y=self._as_float(a.get("y", 0.0), ""),
                span=span,
            )

        elif ctype == "pipe":
            start = str(a.get("start", ""))
            end = str(a.get("end", ""))
            if not start or not end:
                self._err("SEM003", f"배관 '{cid}'에 start/end가 누락됩니다.", span,
                          "start = NodeA; end = NodeB; 를 추가하세요.")
                return
            length_raw = a.get("length", (0.0, "m"))
            length = self._as_si(length_raw)
            if length < 0:
                self._err("SEM007", f"배관 '{cid}'의 길이 {length}m는 0 이하입니다.", span,
                          "length에 양수 값을 입력하세요.")
                return

            dia_raw = a.get("diameter", "auto")
            dia_state = self._sizing(dia_raw, "m")

            mat = str(a.get("material", "Steel"))
            roughness = self._as_si(a.get("roughness", (0.045, "mm")))
            c_factor = self._as_float(a.get("c_factor", 120.0), "")

            em.pipes[cid] = PipeEntity(
                entity_id=cid,
                start_id=start,
                end_id=end,
                length=length,
                diameter=dia_state,
                material=mat,
                roughness=roughness,
                c_factor=c_factor,
                manual_k=self._as_float(a.get("k_factor", 0.0), ""),
                span=span,
            )

    def _collect_connections(self, node: ConnectASTNode, em: EntityMap):
        chain = node.chain
        for i in range(len(chain) - 1):
            em.connections.append((chain[i], chain[i + 1]))

    def _build_constraints(self, node: ConstraintASTNode) -> ConstraintConfig:
        a = node.attributes
        cfg = ConstraintConfig()
        cfg.velocity_min = self._as_si(a.get("velocity_min", (0.3, "m/s")))
        cfg.velocity_max = self._as_si(a.get("velocity_max", (3.0, "m/s")))
        cfg.safety_factor_head = self._as_float(a.get("safety_factor_head", 1.1), "")
        cfg.safety_factor_npsh = self._as_float(a.get("safety_factor_npsh", 1.1), "")
        return cfg

    # ------------------------------------------------------------------
    # 참조 무결성 검사
    # ------------------------------------------------------------------

    def _check_references(self, em: EntityMap):
        all_node_ids = set(em.all_node_ids())

        # 배관의 start/end 참조 검사
        for pipe in em.pipes.values():
            for ref_id, attr in [(pipe.start_id, "start"), (pipe.end_id, "end")]:
                if ref_id and ref_id not in all_node_ids:
                    self._err("SEM002",
                              f"배관 '{pipe.entity_id}'의 {attr}='{ref_id}'가 정의되지 않은 ID입니다.",
                              pipe.span,
                              f"'{ref_id}' 노드를 먼저 정의하세요.")

        # connect 체인의 ID 검사
        all_ids = all_node_ids | set(em.pipes.keys())
        for from_id, to_id in em.connections:
            for cid in (from_id, to_id):
                if cid not in all_ids:
                    self._err("SEM002",
                              f"connect 구문의 '{cid}'가 정의되지 않은 ID입니다.", SourceSpan(),
                              f"'{cid}'를 먼저 선언하세요.")

    # ------------------------------------------------------------------
    # 값 변환 헬퍼
    # ------------------------------------------------------------------

    def _as_si(self, raw: Any) -> float:
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, tuple):
            val, unit = raw
            return _to_si(float(val), unit)
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.lower() == "auto":
                return 0.0
            if raw.lower() == "inf":
                return float("inf")
            import re
            m = re.match(r'^([+-]?[\d.]+)\s*(.*)$', raw)
            if m:
                return _to_si(float(m.group(1)), m.group(2))
        return 0.0

    def _as_float(self, raw: Any, _unit: str) -> float:
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, tuple):
            return float(raw[0])
        try:
            return float(str(raw))
        except Exception:
            return 0.0

    def _sizing(self, raw: Any, default_unit: str) -> SizingState:
        if isinstance(raw, str) and raw.strip().lower() == "auto":
            return SizingState(mode="AUTO", value=0.0)
        val = self._as_si(raw) if isinstance(raw, tuple) else self._as_si((raw, default_unit))
        return SizingState(mode="MANUAL", value=val)

    def _check_elevation(self, elev: float, span: SourceSpan):
        if not (-100 <= elev <= 10000):
            self._warn("SEM005",
                       f"고도 {elev}m는 허용 범위(-100~10000m)를 벗어납니다.", span,
                       "실제 지형 고도를 확인하세요.")

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
