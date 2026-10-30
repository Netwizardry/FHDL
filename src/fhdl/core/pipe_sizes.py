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


# KS 표준 관경 (호칭 A, inch, 내경 m) — 작은 관경부터
KS_PIPE_SIZES: List[PipeSize] = [
    PipeSize(10, 0.375, 0.0127), PipeSize(15, 0.5, 0.0159),
    PipeSize(20, 0.75, 0.0211), PipeSize(25, 1.0, 0.0267),
    PipeSize(32, 1.25, 0.0352), PipeSize(40, 1.5, 0.0422),
    PipeSize(50, 2.0, 0.0528), PipeSize(65, 2.5, 0.0686),
    PipeSize(80, 3.0, 0.0825), PipeSize(100, 4.0, 0.1023),
    PipeSize(125, 5.0, 0.1263), PipeSize(150, 6.0, 0.1503),
    PipeSize(200, 8.0, 0.2027), PipeSize(250, 10.0, 0.2527),
    PipeSize(300, 12.0, 0.3027), PipeSize(350, 14.0, 0.3527),
    PipeSize(400, 16.0, 0.4027), PipeSize(500, 20.0, 0.5027),
]

KS_DIAMETERS_M: List[float] = [s.inner_d_m for s in KS_PIPE_SIZES]


def nominal_size(inner_d_m: float) -> PipeSize:
    """내경(m)에 가장 가까운 표준 관경. 표 밖의 값은 양 끝 관경으로 붙인다."""
    return min(KS_PIPE_SIZES, key=lambda s: abs(s.inner_d_m - inner_d_m))
