"""
FHDL 의미 분석기 (Semantic Analyzer).
입력: AST 노드 리스트
출력: (EntityMap, SemanticDiagnostics)
단위 정규화, 기본값 주입, 참조 무결성 검사를 수행한다.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from .fittings import is_known_fitting, parse_fittings, parse_fitting_placements, sum_fittings_k
from .language import BLOCK_ATTRS, DIMENSION_UNITS, ENUM_VALUES, VALUE_RANGES
from .geometry import pipe_route, polyline_length
from .materials import material_properties
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
    # 속도·온도·비율
    "m/s": 1.0, "mps": 1.0, "ft/s": 0.3048, "c": 1.0, "°c": 1.0, "degc": 1.0, "%": 1e-2,
    "": 1.0,  # 단위 없음: 무변환
}


# 입력이 없을 때 쓰는 기본값 (값은 아래 생성 코드의 기본 인자와 같아야 한다 — 기록·안내용)
_SYSTEM_DEFAULTS = (("유체", "water"), ("유체 온도", "20°C"), ("마찰 모델", "DW (Darcy-Weisbach)"),
                    ("기준 해발 altitude", "0 m"))
_CONSTRAINT_DEFAULTS = {
    "velocity_min": ("최소 유속", "0.3 m/s"), "velocity_max": ("최대 유속", "3.0 m/s"),
    "safety_factor_head": ("양정 안전율", "1.1"), "safety_factor_npsh": ("NPSH 안전율", "1.1"),
}
_ENTITY_DEFAULTS = {
    "tank": {"level_max": ("탱크 최고 수위 level_max", "2 m")},
    "pump": {"efficiency": ("펌프 효율", "0.75"), "npshr": ("필요 NPSH npshr", "0.5 m")},
    "terminal": {"required_p": ("말단 요구 압력", "0 (대기 방출)")},
    "pipe": {"material": ("배관 재질", "Steel")},
}

_DIM_KO = {"length": "길이", "flow": "유량", "pressure": "압력", "volume": "체적", "velocity": "유속",
           "temp": "온도", "ratio": "비율"}


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
    """library(LibraryDB, 선택): 재질 물성·부속 K·관경 표준을 라이브러리 DB 에서 먼저 찾는다(사용자 편집 반영).
    없거나 항목이 없으면 내장 단일 진실원(core.materials·fittings·pipe_sizes)을 쓴다."""

    def __init__(self, library=None):
        self._lib = library

    def _material(self, mat: str):
        if self._lib is not None:
            try:
                row = self._lib.get_material(mat)
            except Exception:
                row = None
            if row:
                return row
        return material_properties(mat)

    def _fitting_lookup(self, name: str):
        if self._lib is None:
            return None
        try:
            return self._lib.find_fitting_k(name)
        except Exception:
            return None

    def analyze(
        self, ast: List[ASTNode]
    ) -> Tuple[EntityMap, List[DiagnosticItem]]:
        self._diags: List[DiagnosticItem] = []
        self._datum = 0.0   # 프로젝트 기준 해발(altitude). 노드 z 는 이 기준 상대값.
        em = EntityMap()
        self._em = em
        has_system = any(isinstance(n, SystemASTNode) for n in ast)
        has_constraint = any(isinstance(n, ConstraintASTNode) for n in ast)

        # 1차: 엔티티 생성
        for node in ast:
            if isinstance(node, SystemASTNode):
                em.fluid = self._build_fluid(node)
                self._datum = em.fluid.altitude
            elif isinstance(node, ComponentASTNode):
                self._build_entity(node, em)
            elif isinstance(node, ConnectASTNode):
                self._collect_connections(node, em)
            elif isinstance(node, ConstraintASTNode):
                em.constraints = self._build_constraints(node)

        # 1.5차: connect 체인에 끼인 배관의 끝점 추론 (connect a -> pipe1 -> b)
        self._infer_pipe_endpoints(em)

        # 관경 표준 → Auto-sizing 후보 내경
        self._resolve_diameters(em)

        # 2차: 참조 무결성 + 중복 ID
        self._check_references(em)

        # 3차: 배관 길이 ↔ 끝점 좌표 기하 정합성
        self._check_pipe_geometry(em)

        if not has_system:
            for what, val in _SYSTEM_DEFAULTS:
                self._default("system", what, val)
        if not has_constraint:
            for what, val in _CONSTRAINT_DEFAULTS.values():
                self._default("constraint", what, val)
        for (what, val), ids in em.defaults_applied.items():
            shown = ", ".join(ids[:8]) + (f" 외 {len(ids) - 8}개" if len(ids) > 8 else "")
            self._diags.append(DiagnosticItem(
                code="DEF001", severity="INFO", message=f"기본값 적용 — {what}: {val} ({shown})",
                source_span=SourceSpan(), related_id=ids[0],
                suggested_action="설계 조건이 다르면 해당 속성을 직접 입력하세요."))
        return em, self._diags

    def _default(self, owner: str, what: str, val: str):
        ids = self._em.defaults_applied.setdefault((what, val), [])
        if owner not in ids:
            ids.append(owner)

    def _note_defaults(self, owner: str, attrs: Dict[str, Any], table):
        for key, (what, val) in table.items():
            if key not in attrs:
                self._default(owner, what, val)

    def _resolve_diameters(self, em: EntityMap):
        from .pipe_sizes import KS_DIAMETERS_M
        std = em.constraints.pipe_standard or "KS"
        sizes = []
        if self._lib is not None:
            try:
                sizes = [d for _, d in self._lib.get_standard_sizes(std)]
            except Exception:
                sizes = []
        if sizes:
            em.constraints.diameters = sorted(sizes)
            return
        em.constraints.diameters = list(KS_DIAMETERS_M)
        if std != "KS":
            self._warn("SEM016", f"관경 표준 '{std}' 이(가) 부품 라이브러리에 없어 KS 관경으로 Auto-sizing 합니다.",
                       SourceSpan(), "라이브러리(관경 표)에 해당 표준을 추가하거나 pipe_standard 를 확인하세요.")

    def _infer_pipe_endpoints(self, em: EntityMap):
        """start/end 가 비어 있는 배관을 connect 체인 위치에서 추론한다.

        예: `connect A -> pipe1 -> B` 이고 pipe1 에 start/end 미지정이면
        pipe1.start=A, pipe1.end=B 로 채운다.
        """
        node_ids = set(em.all_node_ids())
        for pid, pipe in em.pipes.items():
            if pipe.start_id and pipe.end_id:
                continue
            if not pipe.start_id:
                preds = [f for (f, t) in em.connections if t == pid and f in node_ids]
                if preds:
                    pipe.start_id = preds[0]
            if not pipe.end_id:
                succs = [t for (f, t) in em.connections if f == pid and t in node_ids]
                if succs:
                    pipe.end_id = succs[0]

    # ------------------------------------------------------------------
    # 시스템 설정
    # ------------------------------------------------------------------

    def _build_fluid(self, node: SystemASTNode) -> FluidConfig:
        a = node.attributes
        self._validate("system", a, node.span, node.name)
        self._note_defaults("system", a, {k: v for k, v in zip(("fluid", "temp", "friction_model", "altitude"),
                                                               _SYSTEM_DEFAULTS)})
        cfg = FluidConfig()
        cfg.fluid_type = str(a.get("fluid", "water")).lower()
        cfg.unit_system = str(a.get("unit_system", "METRIC")).upper()
        cfg.friction_model = str(a.get("friction_model", "DW")).upper()
        if cfg.friction_model not in ENUM_VALUES["friction_model"]:
            cfg.friction_model = "DW"
        if cfg.unit_system not in ENUM_VALUES["unit_system"]:
            cfg.unit_system = "METRIC"

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
        self._validate(ctype, a, span, cid)
        self._note_defaults(cid, a, _ENTITY_DEFAULTS.get(ctype, {}))
        if ctype == "pipe" and not any(k in a for k in ("fittings", "k_factor")):
            self._default(cid, "국부 손실(부속)", "미입력 → K=0, 경로 꺾임 자동 엘보만 반영")

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
            elev = self._elev(a)
            self._check_elevation(elev, span)
            em.tanks[cid] = TankEntity(
                entity_id=cid,
                elevation=elev,
                volume=self._as_si(a.get("volume", float("inf"))),
                level_max=self._as_si(a.get("level_max", (2.0, "m"))),
                x=self._as_float(a.get("x", 0.0), ""),
                y=self._as_float(a.get("y", 0.0), ""),
                has_xy=("x" in a or "y" in a),
                span=span,
            )

        elif ctype == "pump":
            elev = self._elev(a)
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
                has_xy=("x" in a or "y" in a),
                span=span,
            )

        elif ctype == "junction":
            elev = self._elev(a)
            self._check_elevation(elev, span)
            em.junctions[cid] = JunctionEntity(
                entity_id=cid,
                elevation=elev,
                x=self._as_float(a.get("x", 0.0), ""),
                y=self._as_float(a.get("y", 0.0), ""),
                has_xy=("x" in a or "y" in a),
                span=span,
            )

        elif ctype == "terminal":
            elev = self._elev(a)
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
                has_xy=("x" in a or "y" in a),
                span=span,
            )

        elif ctype == "pipe":
            # start/end 는 생략 가능 — connect 체인에서 추론(_infer_pipe_endpoints).
            # 추론 후에도 비어 있으면 _check_references 에서 SEM003.
            start = str(a.get("start", ""))
            end = str(a.get("end", ""))
            length_raw = a.get("length", (0.0, "m"))
            length = self._as_si(length_raw)
            if length < 0:
                self._err("SEM007", f"배관 '{cid}'의 길이 {length}m는 0 이하입니다.", span,
                          "length에 양수 값을 입력하세요.")
                return

            dia_raw = a.get("diameter", "auto")
            dia_state = self._sizing(dia_raw, "m")

            # 재질 → 물성 자동 적용 (라이브러리 정본). 명시적 roughness/c_factor 가 우선.
            mat = str(a.get("material", "Steel"))
            props = self._material(mat)
            mat = props["material_id"] if props else mat   # 정본 id 로 정규화
            def_rough = props["roughness_m"] if props else 0.045e-3
            def_c = props["c_factor_hw"] if props else 120.0
            roughness = self._as_si(a["roughness"]) if "roughness" in a else def_rough
            c_factor = self._as_float(a["c_factor"], "") if "c_factor" in a else def_c
            if not props and mat != "Steel":
                self._warn("SEM004",
                           f"배관 '{cid}'의 재질 '{mat}'이 라이브러리에 없어 기본(Steel) 물성을 사용합니다.",
                           span, "지원 재질을 사용하거나 roughness/c_factor 를 직접 지정하세요.")

            # 국부손실 K = 직접 지정(k_factor) + 명명 부속(fittings) 라이브러리 합산
            manual_k = self._as_float(a.get("k_factor", 0.0), "")
            fittings_spec = str(a.get("fittings", ""))
            if fittings_spec:
                manual_k += sum_fittings_k(fittings_spec, self._fitting_lookup)
                unknown = sorted({n for n, _ in parse_fittings(fittings_spec)
                                  if not is_known_fitting(n) and self._fitting_lookup(n) is None})
                if unknown:
                    self._warn("SEM015", f"배관 '{cid}'의 부속 {', '.join(unknown)} 이(가) 부속 라이브러리에 없어 "
                               "K=0 으로 계산됩니다.", span, "부속 이름을 확인하거나(help fittings) k_factor 로 직접 지정하세요.")

            via = self._parse_via(a.get("via", ""), cid, span)

            em.pipes[cid] = PipeEntity(
                entity_id=cid,
                start_id=start,
                end_id=end,
                length=length,
                diameter=dia_state,
                material=mat,
                roughness=roughness,
                c_factor=c_factor,
                wave_velocity=(props or {}).get("wave_velocity_ms") or 1200.0,
                max_pressure=(props or {}).get("max_pressure_pa") or 2.0e6,
                manual_k=manual_k,
                via=via,
                fittings=fittings_spec,
                span=span,
            )

    def _collect_connections(self, node: ConnectASTNode, em: EntityMap):
        chain = node.chain
        for i in range(len(chain) - 1):
            em.connections.append((chain[i], chain[i + 1]))

    def _build_constraints(self, node: ConstraintASTNode) -> ConstraintConfig:
        a = node.attributes
        self._validate("constraint", a, node.span, "constraint")
        self._note_defaults("constraint", a, _CONSTRAINT_DEFAULTS)
        cfg = ConstraintConfig()
        cfg.velocity_min = self._as_si(a.get("velocity_min", (0.3, "m/s")))
        cfg.velocity_max = self._as_si(a.get("velocity_max", (3.0, "m/s")))
        cfg.safety_factor_head = self._as_float(a.get("safety_factor_head", 1.1), "")
        cfg.safety_factor_npsh = self._as_float(a.get("safety_factor_npsh", 1.1), "")
        cfg.pipe_standard = str(a.get("pipe_standard", "KS")).upper()
        return cfg

    # ------------------------------------------------------------------
    # 참조 무결성 검사
    # ------------------------------------------------------------------

    def _check_references(self, em: EntityMap):
        all_node_ids = set(em.all_node_ids())

        # 배관의 start/end 참조 검사 (추론 이후)
        for pipe in em.pipes.values():
            if not pipe.start_id or not pipe.end_id:
                self._err("SEM003",
                          f"배관 '{pipe.entity_id}'에 start/end 가 누락됩니다.",
                          pipe.span,
                          "start = NodeA; end = NodeB; 를 추가하거나 connect 체인에 배치하세요.")
                continue
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

    def _check_pipe_geometry(self, em: EntityMap):
        """배관 길이를 끝점 좌표·경유점(via) 경로와 대조한다.

        - SEM008: 경로가 정의됐는데 length < 경로 길이 (via 없으면 3D 직선거리) — 불가능
        - SEM009: length 생략(좌표 추정)인데 끝점 x/y 미지정 → 0 좌표로 잘못 추정됨
        - SEM010: via 를 줬지만 끝점 x/y 가 없어 경로를 만들 수 없음 → via 무시
        - SEM011: 부속 위치(@)가 배관 길이를 벗어남
        length 를 생략하고 경로가 정의되면 length = 경로 길이로 채운다.
        """
        for pipe in em.pipes.values():
            a = em.get_node_entity(pipe.start_id)
            b = em.get_node_entity(pipe.end_id)
            if a is None or b is None:
                continue
            route = pipe_route(em, pipe)
            if route is None:
                missing = [n.entity_id for n in (a, b) if not n.has_xy]
                if pipe.via:
                    self._warn("SEM010",
                               f"배관 '{pipe.entity_id}'에 via 가 있지만 끝점 "
                               f"{', '.join(missing)} 의 x/y 좌표가 없어 경로를 만들 수 없습니다.",
                               pipe.span, "끝점 노드에 x, y 를 지정하세요.")
                    pipe.via = []
                if pipe.length <= 0:
                    self._warn("SEM009",
                               f"배관 '{pipe.entity_id}'의 length 가 생략됐지만 끝점 "
                               f"{', '.join(missing)} 의 x/y 좌표가 없어 길이 추정이 부정확합니다.",
                               pipe.span, "length 를 지정하거나 끝점에 x, y 를 지정하세요.")
            else:
                route_len = polyline_length(route)
                if pipe.length <= 0:
                    pipe.length = max(route_len, 0.1)
                elif pipe.length < route_len * (1 - 1e-3):
                    what = "경유점(via) 경로 길이" if pipe.via else "끝점 사이 3D 직선거리"
                    self._warn("SEM008",
                               f"배관 '{pipe.entity_id}'의 length {pipe.length:.2f}m 가 "
                               f"{what} {route_len:.2f}m 보다 짧습니다.",
                               pipe.span, "length 또는 끝점 좌표(x, y, z)·via 를 확인하세요.")
            if pipe.length > 0:
                for fp in parse_fitting_placements(pipe.fittings):
                    if fp.at_m is not None and fp.at_m > pipe.length * (1 + 1e-3):
                        self._warn("SEM011",
                                   f"배관 '{pipe.entity_id}'의 부속 {fp.name}@{fp.at_m:g}m 가 "
                                   f"배관 길이 {pipe.length:.2f}m 를 벗어납니다.",
                                   pipe.span, "위치를 배관 길이 이내로 지정하세요.")

    def _parse_via(self, raw: Any, cid: str, span: SourceSpan) -> list:
        """via = [(x, y, z), ...] → [(x, y, z) m]. 형식 오류 항목은 SEM010 으로 버린다."""
        if not raw or not isinstance(raw, str):
            return []
        pts = []
        for grp in re.findall(r"\(([^()]*)\)", raw):
            vals = [v.strip() for v in grp.split(",")]
            try:
                xyz = tuple(float(re.sub(r"m$", "", v)) for v in vals)
            except ValueError:
                xyz = ()
            if len(xyz) != 3:
                self._warn("SEM010", f"배관 '{cid}'의 via 항목 '({grp})' 은 (x, y, z) 형식이 아닙니다.",
                           span, "via = [(x, y, z), ...] 형식으로 지정하세요 (단위 m).")
                continue
            pts.append((xyz[0], xyz[1], xyz[2]))
        return pts

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
            return float(raw[0]) / (100.0 if raw[1] == "%" else 1.0)
        try:
            return float(str(raw))
        except Exception:
            return 0.0

    def _sizing(self, raw: Any, default_unit: str) -> SizingState:
        if isinstance(raw, str) and raw.strip().lower() == "auto":
            return SizingState(mode="AUTO", value=0.0)
        val = self._as_si(raw) if isinstance(raw, tuple) else self._as_si((raw, default_unit))
        return SizingState(mode="MANUAL", value=val)

    def _elev(self, attrs: dict) -> float:
        """노드 고도(z) 추출.

        명세 좌표 키는 (x, y, z)이며 z가 고도이다.
        'z'를 1차 키로 받고 'elevation'은 하위호환 별칭으로 허용한다.
        """
        raw = attrs.get("z", attrs.get("elevation", (0.0, "m")))
        return self._as_si(raw)

    def _check_elevation(self, rel_z: float, span: SourceSpan):
        """노드 z 는 프로젝트 datum(해발) 기준 상대값. 절대 해발로 가드 검사한다."""
        abs_alt = self._datum + rel_z
        if not (-500 <= abs_alt <= 10000):
            self._warn("SEM005",
                       f"노드 절대 해발 {abs_alt:g}m (= datum {self._datum:g}m + z {rel_z:g}m)가 "
                       f"허용 범위(-500~10000m)를 벗어납니다.", span,
                       "altitude(기준 해발) 또는 노드 z 값을 확인하세요.")

    # ------------------------------------------------------------------
    # 속성 검증 (language.BLOCK_ATTRS 기준)
    # ------------------------------------------------------------------

    @staticmethod
    def _split_unit(raw: Any) -> Optional[Tuple[float, str]]:
        """값 → (수치, 단위 소문자) — 수치가 아니면 None."""
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return float(raw), ""
        if isinstance(raw, tuple):
            return float(raw[0]), str(raw[1]).lower().replace(" ", "")
        if isinstance(raw, str):
            m = re.match(r'^([+-]?\d[\d.]*(?:[eE][+-]?\d+)?)\s*(\S*)$', raw.strip())
            if m:
                return float(m.group(1)), m.group(2).lower()
        return None

    def _validate(self, block: str, attrs: Dict[str, Any], span: SourceSpan, owner: str):
        """SEM012 단위 오류 · SEM013 모르는 속성 · SEM014 선택지·범위 밖 값."""
        spec = BLOCK_ATTRS.get(block, {})
        for key, raw0 in attrs.items():
            raw = f"{raw0[0]:g}{raw0[1]}" if isinstance(raw0, tuple) else raw0
            dim = spec.get(key)
            if dim is None:
                self._warn("SEM013", f"'{owner}' 의 '{key}' 는 {block} 블록에 없는 속성이라 무시됩니다.", span,
                           f"{block} 속성: {', '.join(spec)}")
                continue
            if dim == "enum":
                allowed = ENUM_VALUES[key]
                val = str(raw)
                if val.lower() not in {x.lower() for x in allowed}:
                    if key == "fluid":
                        self._warn("SEM014", f"유체 '{val}' 물성이 없어 물(water) 물성으로 계산합니다.", span,
                                   "현재 지원 유체: water")
                    else:
                        self._err("SEM014", f"'{owner}' 의 {key} = {val} 은(는) 선택지 밖입니다 "
                                  f"(가능: {', '.join(allowed)}).", span, f"{key} 를 {allowed[0]} 등으로 지정하세요.")
                continue
            if dim in ("id", "text"):
                continue
            if isinstance(raw, str) and raw.strip().lower() in ("auto", "inf"):
                continue
            vu = self._split_unit(raw0)
            if vu is None:
                self._err("SEM012", f"'{owner}' 의 {key} = {raw} 은(는) 수치가 아닙니다.", span,
                          "수치와 단위로 지정하세요 (예: 10m, 100lpm).")
                continue
            val, unit = vu
            if dim == "number":
                if unit and unit != "%":
                    self._err("SEM012", f"'{owner}' 의 {key} 는 무차원 수인데 단위 '{unit}' 가 붙었습니다.", span)
            elif dim == "velocity" and unit == "m":
                self._warn("SEM012", f"'{owner}' 의 {key} = {val:g}m 를 {val:g}m/s 로 해석합니다.", span,
                           "유속 단위는 m/s 로 쓰세요.")
            elif unit and unit not in DIMENSION_UNITS[dim]:
                other = next((d for d, us in DIMENSION_UNITS.items() if unit in us), None)
                why = f"{_DIM_KO[other]} 단위" if other else "알 수 없는 단위"
                self._err("SEM012", f"'{owner}' 의 {key} = {raw}: '{unit}' 는 {why}입니다 — {key} 는 {_DIM_KO[dim]} "
                          f"(가능: {', '.join(DIMENSION_UNITS[dim])}).", span,
                          "단위를 고치세요. 모르는 단위는 1배로 가정하지 않습니다.")
                continue
            rng = VALUE_RANGES.get(key)
            if rng:
                v = val / 100.0 if unit == "%" else val
                if not (rng[0] <= v <= rng[1]):
                    self._warn("SEM014", f"'{owner}' 의 {key} = {raw} 이(가) 통상 범위({rng[0]:g}~{rng[1]:g}) 밖입니다.",
                               span, "값과 단위(비율은 0.75 또는 75%)를 확인하세요.")

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
