"""표시 단위 변환 — 내부 SI 값을 unit_system(METRIC/IMPERIAL)에 맞춰 환산.

내부 진실원은 SI(유량 m³/s, 압력 Pa, 수두·길이·관경 m, 유속 m/s).
GUI 표시 계층에서만 이 헬퍼로 환산한다.
"""
from __future__ import annotations

from typing import Dict, Tuple

# 환산 계수 (SI → 표시단위)
_LPM = 60000.0          # m³/s → L/min
_GPM = 15850.323        # m³/s → US GPM
_MPA = 1.0e-6           # Pa → MPa
_PSI = 1.0 / 6894.757   # Pa → psi
_FT = 3.2808399         # m → ft
_IN = 39.3700787        # m → inch


def display_units(unit_system: str) -> Dict[str, Tuple[float, str]]:
    """unit_system 별 (계수, 단위라벨) 맵.

    키: flow, press, length, dia. 유속(velocity)은 양 체계 모두 m/s.
    """
    if str(unit_system).upper() == "IMPERIAL":
        return {
            "flow":   (_GPM, "GPM"),
            "press":  (_PSI, "psi"),
            "length": (_FT, "ft"),
            "dia":    (_IN, "in"),
        }
    return {
        "flow":   (_LPM, "L/min"),
        "press":  (_MPA, "MPa"),
        "length": (1.0, "m"),
        "dia":    (1000.0, "mm"),
    }
