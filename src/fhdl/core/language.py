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
    "volume", "level_max", "efficiency", "npshr",
    "pump_type", "min_level", "submerge_ref",
    "temp", "altitude", "unit_system", "fluid", "friction_model",
    "velocity_min", "velocity_max", "safety_factor_head", "safety_factor_npsh",
    "start", "end",
)

# 지원 단위 (구문 강조 / 검증용)
UNITS = (
    "m3s", "m3h", "m3/s", "m3/h", "lpm", "gpm", "ls",
    "mpa", "kpa", "bar", "psi", "pa",
    "mm", "m", "ft", "inch", "in", "m3",
)
