"""배관 경로 기하 — 경유점(via)·꺾임·엘보 테이크오프·단관 절단 길이.

좌표계: x = 동(East), y = 북(North), z = 상(Up), 단위 m. z 는 datum 상대 고도(노드 elevation).
배관 경로 = [시작 노드, via..., 끝 노드]. 양 끝 노드에 x/y 가 명시돼야 경로가 정의된다.

엘보 테이크오프(KS/JIS 롱 엘보): 90° = 1.5 × 호칭경(inch) × 25.4mm,
임의 각 θ = 1.5 × 호칭경 × tan(θ/2). 단관 절단 길이 = 구간 길이 − 양 끝 테이크오프.
"""
from __future__ import annotations

import math
from typing import List, NamedTuple, Optional, Sequence, Tuple

from .pipe_sizes import nominal_size

Point3 = Tuple[float, float, float]

LONG_ELBOW_RATIO = 1.5   # 롱 엘보 곡률반경 = 1.5D (KS/JIS)
MIN_BEND_DEG = 1.0       # 이보다 작은 꺾임은 직선으로 본다


def sub(a: Sequence[float], b: Sequence[float]) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def norm(v: Sequence[float]) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def unit(v: Sequence[float]) -> Point3:
    n = norm(v)
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def lerp(a: Sequence[float], b: Sequence[float], t: float) -> Point3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def angle_between(a: Sequence[float], b: Sequence[float]) -> float:
    """두 방향 벡터 사이 각(°). 0 = 직진."""
    na, nb = norm(a), norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    c = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (na * nb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def node_point(ent) -> Optional[Point3]:
    """노드 엔티티의 3D 좌표 (x/y 미지정이면 None)."""
    if ent is None or not getattr(ent, "has_xy", False):
        return None
    return (float(ent.x), float(ent.y), float(ent.elevation))


def pipe_route(em, pipe) -> Optional[List[Point3]]:
    """배관 경로 점열 [시작, via..., 끝]. 끝점 좌표가 없으면 None."""
    a = node_point(em.get_node_entity(pipe.start_id))
    b = node_point(em.get_node_entity(pipe.end_id))
    if a is None or b is None:
        return None
    pts = [a] + [tuple(map(float, p)) for p in pipe.via] + [b]
    # 연속 중복점 제거 (길이 0 구간)
    out = [pts[0]]
    for p in pts[1:]:
        if norm(sub(p, out[-1])) > 1e-9:
            out.append(p)
    return out


def polyline_length(pts: Sequence[Point3]) -> float:
    return sum(norm(sub(pts[i + 1], pts[i])) for i in range(len(pts) - 1))


def bend_angles(pts: Sequence[Point3]) -> List[float]:
    """경로 내부 꺾임점(via)마다 꺾임각(°). 직선(<1°)은 0."""
    out = []
    for i in range(1, len(pts) - 1):
        ang = angle_between(sub(pts[i], pts[i - 1]), sub(pts[i + 1], pts[i]))
        out.append(ang if ang >= MIN_BEND_DEG else 0.0)
    return out


def point_at(pts: Sequence[Point3], dist: float) -> Tuple[Point3, Point3]:
    """경로 시작점에서 거리 dist(m) 지점의 (좌표, 진행방향 단위벡터)."""
    dist = max(0.0, dist)
    for i in range(len(pts) - 1):
        seg = norm(sub(pts[i + 1], pts[i]))
        if dist <= seg or i == len(pts) - 2:
            t = min(dist / seg, 1.0) if seg > 0 else 0.0
            return lerp(pts[i], pts[i + 1], t), unit(sub(pts[i + 1], pts[i]))
        dist -= seg
    return pts[-1], (1.0, 0.0, 0.0)


def elbow_takeoff_m(inner_d_m: float, angle_deg: float) -> float:
    """롱 엘보 테이크오프(m) = 1.5 × 호칭경 × tan(θ/2). 90° → 1.5D."""
    if angle_deg < MIN_BEND_DEG:
        return 0.0
    inch = nominal_size(inner_d_m).nominal_inch
    # 엘보 하나의 꺾임은 90° 까지 — 그 이상(U턴)은 엘보 2개라 tan(θ/2) 가 발산하지 않게 90° 로 묶는다
    return LONG_ELBOW_RATIO * inch * 0.0254 * math.tan(math.radians(min(abs(angle_deg), 90.0)) / 2)


class Spool(NamedTuple):
    index: int          # 구간 번호 (0부터)
    length_m: float     # 구간 중심선 길이
    cut_m: float        # 단관 절단 길이 (테이크오프 차감, 0 미만은 0)
    short: bool = False  # C-C 가 양 끝 테이크오프 합보다 짧다 (단관 없음)


def spool_cut_lengths(pts: Sequence[Point3], inner_d_m: float) -> List[Spool]:
    """직선 구간별 단관 절단 길이. 각 꺾임점의 엘보 테이크오프를 양쪽 구간에서 뺀다."""
    bends = bend_angles(pts)
    take = [elbow_takeoff_m(inner_d_m, a) for a in bends]
    out = []
    for i in range(len(pts) - 1):
        L = norm(sub(pts[i + 1], pts[i]))
        cut = L - (take[i - 1] if i >= 1 else 0.0) - (take[i] if i < len(take) else 0.0)
        # 구간이 엘보 테이크오프 합보다 짧으면 단관이 들어갈 자리가 없다 — 0 으로 두고 표시(short)
        out.append(Spool(i, L, max(cut, 0.0), cut < -1e-9))
    return out


def route_end_dirs(pts: Sequence[Point3]) -> Tuple[Point3, Point3]:
    """(시작점에서 나가는 방향, 끝점으로 들어오는 방향) 단위벡터. 점이 하나뿐이면 영벡터."""
    if len(pts) < 2:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return unit(sub(pts[1], pts[0])), unit(sub(pts[-1], pts[-2]))
