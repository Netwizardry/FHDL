"""EHDL 단위 — 입력 단위 → 내부 SI 단위 변환을 한 곳에서 관리 (SPEC 9.2).

내부 단위: 전압 V, 전류 A, 유효전력 W, 피상전력 VA, 무효전력 var, 길이 m, 단면적 mm²,
리액턴스 Ω/m, 시간 s, 온도 °C, 주파수 Hz, 비율 0~1.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# 단위 표기(소문자) → (종류, 배율)
_UNITS = {
    "v": ("voltage", 1.0), "kv": ("voltage", 1e3),
    "a": ("current", 1.0), "ka": ("current", 1e3), "ma": ("current", 1e-3),
    "w": ("power", 1.0), "kw": ("power", 1e3), "mw": ("power", 1e6),
    "va": ("apparent", 1.0), "kva": ("apparent", 1e3), "mva": ("apparent", 1e6),
    "var": ("reactive", 1.0), "kvar": ("reactive", 1e3),
    "m": ("length", 1.0), "km": ("length", 1e3),
    "mm2": ("area", 1.0), "sq": ("area", 1.0),
    "mohm/m": ("reactance", 1e-3), "ohm/km": ("reactance", 1e-3), "ohm/m": ("reactance", 1.0),
    "s": ("time", 1.0), "ms": ("time", 1e-3),
    "hz": ("frequency", 1.0),
    "c": ("temperature", 1.0), "degc": ("temperature", 1.0),
    "%": ("ratio", 0.01),
}

# 속성 종류 → 허용 단위 종류
KIND_ACCEPTS = {
    "voltage": {"voltage"}, "current": {"current"}, "current_ka": {"current"},
    "current_ma": {"current"}, "power": {"power"}, "apparent": {"apparent"},
    "power_or_apparent": {"power", "apparent"}, "length": {"length"}, "area": {"area"},
    "reactance": {"reactance"}, "time": {"time"}, "frequency": {"frequency"},
    "temperature": {"temperature"}, "ratio": {"ratio"},
}
# 단위 없이 숫자만 쓴 경우의 기본 단위 (속성 종류별)
DEFAULT_UNIT = {
    "voltage": "v", "current": "a", "current_ka": "ka", "current_ma": "ma", "power": "kw",
    "apparent": "kva", "length": "m", "area": "mm2", "reactance": "mohm/m", "time": "s",
    "frequency": "hz", "temperature": "c", "ratio": "",
}

_NUM = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z%/²°0-9]*)\s*$")


def parse_quantity(raw: str, kind: str) -> Tuple[Optional[float], Optional[str], str]:
    """'37kW' → (37000.0, 'power', '') / 오류 시 (None, None, 메시지).

    반환 두 번째 값은 실제 단위 종류(kW/kVA 구분용). ratio 는 '85%' 또는 '0.85'.
    """
    m = _NUM.match(str(raw))
    if not m:
        return None, None, f"수치가 아닙니다: '{raw}'"
    val = float(m.group(1))
    unit = m.group(2).replace("²", "2").replace("°", "deg").lower()
    if unit == "":
        unit = DEFAULT_UNIT.get(kind, "")
        if kind == "ratio" or unit == "":
            return val, "ratio" if kind == "ratio" else kind, ""
    if unit not in _UNITS:
        return None, None, f"알 수 없는 단위 '{m.group(2)}'"
    ukind, factor = _UNITS[unit]
    if ukind not in KIND_ACCEPTS.get(kind, {ukind}):
        return None, None, f"단위 '{m.group(2)}' 는 이 속성에 맞지 않습니다"
    return val * factor, ukind, ""


def fmt(value: Optional[float], unit: str, digits: int = 1) -> str:
    """표시용 문자열. 전력은 k 단위, 1만 V 이상은 kV. value 가 None 이면 '미입력'."""
    if value is None:
        return "미입력"
    if unit in ("W", "VA", "var"):
        return f"{value / 1000:.{digits}f} k{unit}"
    if unit == "V" and abs(value) >= 10000:
        return f"{value / 1000:.{digits}f} kV"
    if unit == "%":
        return f"{value:.{digits}f}%"
    return f"{value:.{digits}f} {unit}"
