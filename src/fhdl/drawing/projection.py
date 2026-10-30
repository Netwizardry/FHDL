"""3D 모델 좌표 → 2D 도면 좌표 투영.

모델 좌표: x = 동(E), y = 북(N), z = 상(Up), 단위 m.
- iso: ISO 6412-2 등각 투영. 북 = 오른쪽 위 30°, 동 = 오른쪽 아래 30°, 상 = 수직.
  (참고 자료 "ISO 보는 요령"의 방위 규약과 같다.) 세 축의 투영 길이는 모두 1.
- plan: 평면도(위에서 봄). 동 = 오른쪽, 북 = 위.
- elevation: 정면도(남쪽에서 북쪽을 봄). 동 = 오른쪽, 상 = 위.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Sequence, Tuple

P2 = Tuple[float, float]
_C30 = math.cos(math.radians(30))
_S30 = 0.5


def _iso(p: Sequence[float]) -> P2:
    x, y, z = p
    return ((x + y) * _C30, (y - x) * _S30 + z)


def _plan(p: Sequence[float]) -> P2:
    return (p[0], p[1])


def _elev(p: Sequence[float]) -> P2:
    return (p[0], p[2])


PROJECTIONS: Dict[str, Callable[[Sequence[float]], P2]] = {
    "iso": _iso, "plan": _plan, "elevation": _elev,
}

# 기호 b축 후보 — 동점이면 앞쪽 우선: 수평관의 치수·기호는 수직(Up) 평면에 그리는 것이 관례
WORLD_AXES = [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]


def project_dir(view: str, d: Sequence[float]) -> P2:
    """방향 벡터의 투영 (원점 투영을 빼서 평행이동 제거)."""
    f = PROJECTIONS[view]
    a, b = f(d), f((0.0, 0.0, 0.0))
    return (a[0] - b[0], a[1] - b[1])


_AXIS_NAMES = {(1.0, 0.0, 0.0): "E", (0.0, 1.0, 0.0): "N", (0.0, 0.0, 1.0): "U"}


def frame_axes(view: str, u: Sequence[float]):
    """좌표축과 나란한 배관 방향 u → (배관 축 이름, 부호 "+"/"-", 기호 평면 축 이름).

    기호표 방향 변형(drawing/data/iso_symbols.json) 선택용. 사선 배관이면 None.
    평면 축은 symbol_frame 이 고르는 축과 같다.
    """
    k = max(range(3), key=lambda i: abs(u[i]))
    if abs(u[k]) < 0.999:
        return None
    a_name = "ENU"[k]
    sign = "+" if u[k] > 0 else "-"
    _, _, w = _frame(view, u)
    return (a_name, sign, _AXIS_NAMES[w]) if w is not None else None


def symbol_frame(view: str, u: Sequence[float]) -> Tuple[P2, P2]:
    a, b, _ = _frame(view, u)
    return a, b


def _frame(view: str, u: Sequence[float]):
    """배관 방향 u(단위벡터)에 대한 기호 로컬 좌표축 (a축, b축)의 도면 방향.

    a = u 의 투영(정규화), b = u 에 수직인 월드 방향 중 도면에서 가장 길게 보이고
    a 와 가장 덜 겹치는 방향. 참고 기호표처럼 기호가 배관이 놓인 평면에 그려진다.
    u 가 시선 방향이라 투영 길이가 0이면 (화면 x, 화면 y)를 돌려준다.
    """
    au = project_dir(view, u)
    la = math.hypot(*au)
    if la < 1e-6:
        return (1.0, 0.0), (0.0, 1.0), None
    a = (au[0] / la, au[1] / la)
    best, best_score, best_w = None, -1.0, None
    for w in WORLD_AXES:
        # u 에 수직 성분만 남김
        dot = sum(w[i] * u[i] for i in range(3))
        perp = tuple(w[i] - dot * u[i] for i in range(3))
        n = math.sqrt(sum(c * c for c in perp))
        if n < 1e-6:
            continue
        pb = project_dir(view, tuple(c / n for c in perp))
        lb = math.hypot(*pb)
        if lb < 1e-6:
            continue
        cross = abs(a[0] * pb[1] - a[1] * pb[0]) / lb   # a 와의 사잇각 sin
        score = lb * cross
        if score > best_score + 1e-6:
            best, best_score, best_w = (pb[0] / lb, pb[1] / lb), score, w
    if best is None or best_score < 0.2:
        best, best_w = (-a[1], a[0]), None
    # b 가 a 의 왼쪽(반시계)이 되도록 통일 — 주석 배치 방향이 일관된다
    if a[0] * best[1] - a[1] * best[0] < 0:
        best = (-best[0], -best[1])
    return a, best, best_w


class Fit:
    """모델 투영 좌표(m) → 용지 좌표(mm) 균등 축척 변환 (도면 영역에 맞춤)."""

    def __init__(self, pts2d, area: Tuple[float, float, float, float], margin: float = 12.0,
                 right_extra: float = 0.0):
        x0, y0, x1, y1 = area
        x1 -= right_extra       # 오른쪽 주석(노드 라벨) 공간
        if pts2d:
            xs = [p[0] for p in pts2d]
            ys = [p[1] for p in pts2d]
            mx0, mx1, my0, my1 = min(xs), max(xs), min(ys), max(ys)
        else:
            mx0 = my0 = 0.0
            mx1 = my1 = 1.0
        w = max(mx1 - mx0, 1e-6)
        h = max(my1 - my0, 1e-6)
        aw = max(x1 - x0 - 2 * margin, 1.0)
        ah = max(y1 - y0 - 2 * margin, 1.0)
        self.scale = min(aw / w, ah / h)            # mm / m
        cx, cy = (mx0 + mx1) / 2, (my0 + my1) / 2
        self.ox = (x0 + x1) / 2 - cx * self.scale
        self.oy = (y0 + y1) / 2 - cy * self.scale

    def __call__(self, p: P2) -> P2:
        return (self.ox + p[0] * self.scale, self.oy + p[1] * self.scale)
