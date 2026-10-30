"""표준 관경(KS) 단일 진실원.

호칭경(A, inch)과 내경(m)을 한 곳에서 정의한다. solver(Auto-sizing)·geometry
(엘보 테이크오프)·drawing(DN 표기)이 모두 이 표를 참조한다.
"""
from __future__ import annotations

from typing import List, NamedTuple


class PipeSize(NamedTuple):
    nominal_a: int        # 호칭경 A (mm 계열)
    nominal_inch: float   # 호칭경 inch (B 계열)
    inner_d_m: float      # 해석용 내경 (m)


# KS D 3507 배관용 탄소강관(SPP) — 내경 = 외경 − 2·두께 (JIS G 3452 SGP 와 같은 치수). 작은 관경부터.
# (호칭 A, inch, 외경 mm, 두께 mm)
_SPP = [
    (10, 0.375, 17.3, 2.3), (15, 0.5, 21.7, 2.8), (20, 0.75, 27.2, 2.8), (25, 1.0, 34.0, 3.2),
    (32, 1.25, 42.7, 3.5), (40, 1.5, 48.6, 3.5), (50, 2.0, 60.5, 3.8), (65, 2.5, 76.3, 4.2),
    (80, 3.0, 89.1, 4.2), (100, 4.0, 114.3, 4.5), (125, 5.0, 139.8, 4.5), (150, 6.0, 165.2, 5.0),
    (200, 8.0, 216.3, 5.8), (250, 10.0, 267.4, 6.6), (300, 12.0, 318.5, 6.9), (350, 14.0, 355.6, 7.9),
    (400, 16.0, 406.4, 7.9), (450, 18.0, 457.2, 7.9), (500, 20.0, 508.0, 7.9),
]
KS_PIPE_SIZES: List[PipeSize] = [PipeSize(a, inch, round((od - 2 * t) / 1000.0, 5)) for a, inch, od, t in _SPP]
KS_OUTER_WALL = {a: (od, t) for a, _, od, t in _SPP}   # 호칭 A → (외경 mm, 두께 mm)

KS_DIAMETERS_M: List[float] = [s.inner_d_m for s in KS_PIPE_SIZES]


def nominal_size(inner_d_m: float) -> PipeSize:
    """내경(m)에 가장 가까운 표준 관경. 표 밖의 값은 양 끝 관경으로 붙인다."""
    return min(KS_PIPE_SIZES, key=lambda s: abs(s.inner_d_m - inner_d_m))
