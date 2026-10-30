"""FHDL 언어 정의 단일 진실원 — 블록/노드 키워드·속성·단위.

parser(파싱)·highlighter(구문강조)·gui(노드 추가 다이얼로그)가 모두 이 정의를
참조하여 키워드가 어긋나지 않도록 한다.
"""
from __future__ import annotations

# 노드 블록 타입 (system/pipe/connect/constraint 제외한 '노드')
NODE_TYPES = ("tank", "pump", "junction", "terminal")

# 노드 + 배관 (GUI 노드 추가 다이얼로그 드롭다운용)
COMPONENT_TYPES = ("tank", "pump", "terminal", "junction", "pipe")

# 최상위 블록/문 키워드
BLOCK_KEYWORDS = (
    "system", "tank", "pump", "pipe", "junction", "terminal",
    "connect", "constraint",
)

# 속성 키워드 (구문 강조용)
ATTR_KEYWORDS = (
    "z", "elevation", "x", "y",
    "flow", "head", "length", "diameter", "material", "fittings",
    "required_q", "required_p", "k_factor", "c_factor", "roughness",
    "volume", "level_max", "level_min", "efficiency", "npshr",
    "pump_type", "min_level", "submerge_ref",
    "temp", "altitude", "unit_system", "fluid", "friction_model",
    "velocity_min", "velocity_max", "safety_factor_head", "safety_factor_npsh",
    "start", "end", "via", "curve_id", "preset_id", "pipe_standard",
)

# 지원 단위 (구문 강조 / 검증용)
UNITS = (
    "m3s", "m3h", "m3/s", "m3/h", "lpm", "gpm", "ls",
    "mpa", "kpa", "bar", "psi", "pa",
    "mm", "m", "ft", "inch", "in", "m3",
)

# ---------------------------------------------------------------------------
# 블록별 허용 속성 → 값 차원 (의미 분석 검증 SEM012~014 의 단일 진실원)
#   length·flow·pressure·volume·velocity: 단위 차원 / temp: ℃ / ratio: 0~1 또는 %
#   number: 무차원 수 / id: 참조 ID / enum: ENUM_VALUES / text: 자유 문자열
# ---------------------------------------------------------------------------
_XYZ = {"x": "number", "y": "number", "z": "length", "elevation": "length"}

BLOCK_ATTRS = {
    "system": {"unit_system": "enum", "fluid": "enum", "temp": "temp", "altitude": "length",
               "friction_model": "enum"},
    "tank": {**_XYZ, "volume": "volume", "level_max": "length", "level_min": "length"},
    "pump": {**_XYZ, "flow": "flow", "head": "length", "efficiency": "ratio", "npshr": "length",
             "curve_id": "text", "pump_type": "enum", "min_level": "length", "submerge_ref": "id"},
    "junction": dict(_XYZ),
    "terminal": {**_XYZ, "required_q": "flow", "required_p": "pressure", "k_factor": "number",
                 "preset_id": "text"},
    "pipe": {"start": "id", "end": "id", "length": "length", "diameter": "length", "material": "text",
             "roughness": "length", "c_factor": "number", "k_factor": "number", "fittings": "text",
             "via": "text"},
    "constraint": {"velocity_min": "velocity", "velocity_max": "velocity", "safety_factor_head": "number",
                   "safety_factor_npsh": "number", "pipe_standard": "text"},
}

ENUM_VALUES = {
    "unit_system": ("METRIC", "IMPERIAL"),
    "fluid": ("water",),
    "friction_model": ("DW", "HW"),
    "pump_type": ("normal", "submersible"),
}

# 차원별 허용 단위 (소문자, 공백 제거) — 값이 단위 없이 오면 기본 SI 단위로 본다
DIMENSION_UNITS = {
    "length": ("m", "mm", "cm", "km", "ft", "in", "inch"),
    "flow": ("m3s", "m3/s", "m3h", "m3/h", "lpm", "l/min", "lmin", "ls", "l/s", "gpm", "gal/min"),
    "pressure": ("pa", "kpa", "mpa", "bar", "psi", "mwg"),
    "volume": ("m3", "l", "gal"),
    "velocity": ("m/s", "mps", "ft/s"),
    "temp": ("c", "°c", "degc"),
    "ratio": ("%",),
}

# 수치 범위 점검 (벗어나면 경고 SEM014): (최소, 최대) — 내부 단위 기준
VALUE_RANGES = {
    "efficiency": (0.05, 1.0),
    "c_factor": (40.0, 160.0),
    "safety_factor_head": (1.0, 3.0),
    "safety_factor_npsh": (1.0, 3.0),
}

# 부호 규칙 (위반 → 오류 SEM014): pos = 0 보다 커야, nonneg = 0 이상
SIGN_RULES = {
    "diameter": "pos", "c_factor": "pos", "velocity_max": "pos", "velocity_min": "nonneg",
    "efficiency": "pos", "roughness": "nonneg", "k_factor": "nonneg", "required_q": "nonneg",
    "required_p": "nonneg", "level_max": "nonneg", "level_min": "nonneg", "volume": "pos", "npshr": "nonneg", "min_level": "nonneg",
    "safety_factor_head": "pos", "safety_factor_npsh": "pos", "flow": "nonneg", "head": "nonneg",
}
