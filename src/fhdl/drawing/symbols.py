"""ISO 배관 도면 기호.

기호 형상의 1차 출처는 **사용자 기호표 DXF 에서 추출한 데이터**(`data/iso_symbols.json`,
`drawing/dxf_symbols.py` 로 재생성)다. 아이소메트릭에서는 배관 축·평면 축이 맞는 기호표
방향 변형을 그대로 쓰고, 그 밖(평면도·정면도·계통도·사선 배관)에는 추출한 로컬 형상을 쓴다.
데이터에 없는 기호(스트레이너·계기 태그·구동부 등)만 아래 SYMBOLS 정의를 쓴다.

기호는 배관 방향 기준 로컬 좌표 (a, b) 로 한 번만 정의한다. a = 배관 진행 방향,
b = 배관이 놓인 평면에서 a 에 수직인 방향, 단위 = 기호 크기의 절반.
그릴 때 projection.symbol_frame 이 (a, b) 축의 도면 방향을 정하므로, 같은 정의가
아이소메트릭의 6가지 방향(진행 축 × 평면)과 평면도·정면도·계통도에 모두 쓰인다.
로컬 평면의 원은 다각형으로 투영되어 아이소메트릭에서는 타원으로 보인다.

모양은 참고 기호표(archive/dxf: ISO 6412-2 스타일 아이소메트릭 기호)를 따른다:
밸브 = 나비넥타이형, 글로브 = 가운데 채운 원, 볼 = 가운데 빈 원, 체크 = 화살표,
계기 = 원형 태그(PI·FE·TI), 유니온 = 짧은 평행선 3개.

모양 정의 형식:
  ("L", [(a,b),...])         열린 선
  ("P", [(a,b),...])         닫힌 외곽선
  ("F", [(a,b),...])         채운 다각형
  ("C", (a,b), r)            로컬 평면의 원 (외곽선)
  ("CF", (a,b), r)           로컬 평면의 원 (채움)
  ("TAG", (a,b), r, "PI")    화면 원 + 글자 (계기 태그, 회전하지 않음)
  ("T", (a,b), "S")          글자 (회전하지 않음)
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

from .sheet import Circle, Line, Polyline, Text

P2 = Tuple[float, float]

_BOWTIE = ("P", [(-1.0, 0.6), (1.0, -0.6), (1.0, 0.6), (-1.0, -0.6)])
_STEM = ("L", [(0.0, 0.0), (0.0, 1.1)])


def _wave(n: int = 3, a0: float = -0.7, a1: float = 0.7, amp: float = 0.35) -> List[P2]:
    pts = []
    steps = n * 8
    for i in range(steps + 1):
        t = i / steps
        pts.append((a0 + (a1 - a0) * t, amp * math.sin(t * n * 2 * math.pi)))
    return pts


SYMBOLS: Dict[str, List[tuple]] = {
    # 밸브
    "valve_gate": [_BOWTIE],
    "valve_globe": [_BOWTIE, ("CF", (0.0, 0.0), 0.32)],
    "valve_ball": [_BOWTIE, ("C", (0.0, 0.0), 0.32)],
    "valve_needle": [_BOWTIE, ("L", [(0.0, -0.9), (0.0, 0.9)])],
    "valve_butterfly": [("L", [(-1.0, -0.6), (-1.0, 0.6)]), ("L", [(1.0, -0.6), (1.0, 0.6)]),
                        ("L", [(-1.0, 0.0), (-0.3, 0.0)]), ("L", [(0.3, 0.0), (1.0, 0.0)]),
                        ("C", (0.0, 0.0), 0.3)],
    "valve_check": [("L", [(-1.0, -0.6), (-1.0, 0.6)]), ("L", [(1.0, -0.6), (1.0, 0.6)]),
                    ("L", [(-1.0, -0.6), (1.0, 0.6)]),
                    ("F", [(0.35, 0.21), (-0.15, 0.25), (0.05, -0.08)])],
    "valve_relief": [("P", [(-1.0, 0.6), (-1.0, -0.6), (0.0, 0.0)]),
                     ("P", [(0.0, 0.0), (-0.6, 1.0), (0.6, 1.0)]),
                     ("L", [(0.0, 0.0), (0.9, 0.0)]),
                     ("L", [(0.0, 1.0), (0.2, 1.2), (-0.2, 1.4), (0.2, 1.6), (0.0, 1.8)])],
    "valve_prv": [_BOWTIE, _STEM, ("P", [(-0.45, 1.1), (0.45, 1.1), (0.45, 1.7), (-0.45, 1.7)]),
                  ("L", [(-0.45, 1.1), (0.45, 1.7)])],
    "valve_solenoid": [_BOWTIE, _STEM, ("P", [(-0.45, 1.1), (0.45, 1.1), (0.45, 1.8), (-0.45, 1.8)]),
                       ("T", (0.0, 1.45), "S")],
    "valve_air": [("P", [(-0.5, 0.0), (0.5, 0.0), (0.0, 0.8)]), ("C", (0.0, 1.2), 0.4)],
    # 부속
    "reducer": [("P", [(-0.8, 0.65), (0.8, 0.35), (0.8, -0.35), (-0.8, -0.65)])],
    "union": [("L", [(-0.3, -0.6), (-0.3, 0.6)]), ("L", [(0.0, -0.35), (0.0, 0.35)]),
              ("L", [(0.3, -0.6), (0.3, 0.6)])],
    "coupling": [("L", [(-0.2, -0.45), (-0.2, 0.45)]), ("L", [(0.2, -0.45), (0.2, 0.45)])],
    "flange": [("L", [(-0.15, -0.8), (-0.15, 0.8)]), ("L", [(0.15, -0.8), (0.15, 0.8)])],
    "expansion_joint": [("L", [(-0.8, -0.6), (-0.8, 0.6)]), ("L", [(0.8, -0.6), (0.8, 0.6)]),
                        ("L", _wave())],
    "strainer": [("P", [(-0.7, 0.4), (0.7, 0.4), (0.7, -0.4), (-0.7, -0.4)]),
                 ("L", [(0.0, -0.4), (0.6, -1.3)]), ("L", [(0.35, -1.45), (0.85, -1.15)])],
    "sight_glass": [("P", [(-0.6, 0.5), (0.6, 0.5), (0.6, -0.5), (-0.6, -0.5)]),
                    ("C", (0.0, 0.0), 0.3)],
    "cap": [("L", [(0.0, -0.6), (0.25, -0.45), (0.4, 0.0), (0.25, 0.45), (0.0, 0.6)])],
    # 계기 (원형 태그)
    "inst_pi": [_STEM, ("TAG", (0.0, 1.8), 0.7, "PI")],
    "inst_fe": [("P", [(-0.5, 0.45), (0.5, 0.45), (0.5, -0.45), (-0.5, -0.45)]),
                _STEM, ("TAG", (0.0, 1.8), 0.7, "FE")],
    "inst_ti": [_STEM, ("TAG", (0.0, 1.8), 0.7, "TI")],
    # 흐름 방향 화살표 (끝점 = 로컬 원점)
    "flow_arrow": [("F", [(0.0, 0.0), (-1.6, 0.42), (-1.6, -0.42)])],
    # 말단 노즐/스프링클러 (원점 = 배관 끝)
    "nozzle": [("F", [(0.0, 0.0), (0.9, 0.55), (0.9, -0.55)]),
               ("L", [(1.1, -0.7), (1.1, 0.7)])],
}

def symbol_layer(sym_id: str) -> str:
    return ("INSTR" if sym_id.startswith("inst_") else
            "FLOW" if sym_id == "flow_arrow" else
            "EQPT" if sym_id == "nozzle" else
            "VALVE" if sym_id.startswith("valve_") else "FITTING")


IMPORTED_PATH = os.path.join(os.path.dirname(__file__), "data", "iso_symbols.json")


@lru_cache(maxsize=1)
def imported_symbols() -> Dict[str, dict]:
    """기호표 DXF 추출 데이터 (없거나 깨졌으면 빈 dict → 내장 정의 사용)."""
    try:
        with open(IMPORTED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("symbols", {})
    except (OSError, ValueError):
        return {}


def available_symbols() -> List[str]:
    return sorted(set(SYMBOLS) | set(imported_symbols()))


def _pick_variant(sym: dict, axes) -> Tuple[Optional[list], bool]:
    """(방향 변형 경로, 배관 축 방향으로 뒤집어야 하는지). 없으면 (None, False)."""
    a, sign, b = axes
    var = sym.get("variants", {})
    if sym.get("directional"):
        flip = "-" if sign == "+" else "+"
        for key, mirror in ((f"{sign}{a}/{b}", False), (f"{flip}{a}/{b}", True)):
            if key in var:
                return var[key], mirror
        for key, paths in var.items():          # 다른 평면에 그려진 같은 배관 축 변형
            if key[1:].startswith(a + "/"):
                return paths, key[0] != sign
        return None, False
    if f"{a}/{b}" in var:
        return var[f"{a}/{b}"], False
    for key, paths in var.items():
        if key.startswith(a + "/"):
            return paths, False
    return None, False


def _circle_pts(c: P2, r: float, n: int = 24) -> List[P2]:
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def render_symbol(sym_id: str, origin: P2, a_dir: P2, b_dir: P2, size: float,
                  ref: str = "", layer: str = "", axes=None) -> List[object]:
    """기호를 용지 좌표 요소 목록으로 만든다. size = 기호 반폭(mm, 게이트 밸브 반길이 기준).

    axes = projection.frame_axes(...) — 아이소메트릭이고 배관이 좌표축 방향일 때만 넘긴다.
    """
    layer = layer or symbol_layer(sym_id)
    imp = imported_symbols().get(sym_id)
    if imp:
        paths, mirror = _pick_variant(imp, axes) if axes else (None, False)
        if paths is not None:
            return _render_paths(paths, origin, size, ref, layer, screen=True,
                                 mirror_dir=a_dir if mirror else None)
        return _render_paths(imp["local"], origin, size, ref, layer, a_dir=a_dir, b_dir=b_dir)
    shapes = SYMBOLS.get(sym_id)
    if not shapes:
        return []

    def tp(p: Sequence[float]) -> P2:
        return (origin[0] + size * (p[0] * a_dir[0] + p[1] * b_dir[0]),
                origin[1] + size * (p[0] * a_dir[1] + p[1] * b_dir[1]))

    out: List[object] = []
    w = 0.3
    for sh in shapes:
        kind = sh[0]
        if kind in ("L", "P", "F"):
            out.append(Polyline([tp(p) for p in sh[1]], layer=layer, closed=kind != "L",
                                fill=kind == "F", width=w, ref=ref))
        elif kind in ("C", "CF"):
            out.append(Polyline([tp(p) for p in _circle_pts(sh[1], sh[2])], layer=layer,
                                closed=True, fill=kind == "CF", width=w, ref=ref))
        elif kind == "TAG":
            c = tp(sh[1])
            out.append(Circle(c, sh[2] * size, layer=layer, width=w, ref=ref))
            out.append(Text(c, sh[3], height=sh[2] * size * 0.9, layer=layer,
                            anchor="middle", valign="middle", ref=ref))
        elif kind == "T":
            out.append(Text(tp(sh[1]), sh[2], height=size * 0.6, layer=layer,
                            anchor="middle", valign="middle", ref=ref))
    return out


def _render_paths(paths, origin: P2, size: float, ref: str, layer: str, screen: bool = False,
                  a_dir: P2 = (1.0, 0.0), b_dir: P2 = (0.0, 1.0),
                  mirror_dir: Optional[P2] = None) -> List[object]:
    """추출 데이터 경로 → 요소. screen=True 면 좌표가 이미 화면 방향(기호표 변형)."""
    out: List[object] = []
    for part in paths:
        pts = []
        for x, y in part["pts"]:
            if not screen:
                x, y = x * a_dir[0] + y * b_dir[0], x * a_dir[1] + y * b_dir[1]
            elif mirror_dir is not None:          # 배관 축 방향으로 반사 (화살촉 방향 뒤집기)
                d = x * mirror_dir[0] + y * mirror_dir[1]
                x, y = x - 2 * d * mirror_dir[0], y - 2 * d * mirror_dir[1]
            pts.append((origin[0] + size * x, origin[1] + size * y))
        if len(pts) >= 2:
            out.append(Polyline(pts, layer=layer, closed=part["closed"], fill=part["fill"],
                                width=0.3, ref=ref))
    return out


def weld_dot(p: P2, ref: str = "", r: float = 0.55) -> Circle:
    """용접점(엘보·티 끝) — 참고 ISO 의 검은 점."""
    return Circle(p, r, layer="FITTING", fill=True, ref=ref)


def tank_symbol(base: P2, size: float, v_up: P2, h_axes: Tuple[P2, P2], ref: str = "") -> List[object]:
    """세로형 원통 탱크: 바닥·상부 원(수평면, 투영) + 좌우 외곽선. h_axes = 수평 두 축의 도면 방향."""
    (ex, ny) = h_axes
    R, H = size, size * 1.8

    def ring(z: float) -> List[P2]:
        pts = []
        for i in range(36):
            t = 2 * math.pi * i / 36
            pts.append((base[0] + R * (math.cos(t) * ex[0] + math.sin(t) * ny[0]) + z * v_up[0],
                        base[1] + R * (math.cos(t) * ex[1] + math.sin(t) * ny[1]) + z * v_up[1]))
        return pts

    bottom, top = ring(0.0), ring(H)
    out: List[object] = [Polyline(bottom, layer="EQPT", closed=True, width=0.35, ref=ref),
                         Polyline(top, layer="EQPT", closed=True, width=0.35, ref=ref)]
    if math.hypot(*v_up) > 1e-6:
        i_min = min(range(len(bottom)), key=lambda i: bottom[i][0])
        i_max = max(range(len(bottom)), key=lambda i: bottom[i][0])
        out.append(Line(bottom[i_min], top[i_min], layer="EQPT", width=0.35, ref=ref))
        out.append(Line(bottom[i_max], top[i_max], layer="EQPT", width=0.35, ref=ref))
    return out


def pump_symbol(c: P2, size: float, out_dir: P2, ref: str = "") -> List[object]:
    """원심 펌프(ISO 14617 형): 원 + 토출 방향을 가리키는 내부 삼각형."""
    dx, dy = out_dir
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    px, py = -dy, dx
    r = size
    tri = [(c[0] + dx * r * 0.85, c[1] + dy * r * 0.85),
           (c[0] - dx * r * 0.5 + px * r * 0.72, c[1] - dy * r * 0.5 + py * r * 0.72),
           (c[0] - dx * r * 0.5 - px * r * 0.72, c[1] - dy * r * 0.5 - py * r * 0.72)]
    return [Circle(c, r, layer="EQPT", width=0.35, ref=ref),
            Polyline(tri, layer="EQPT", closed=True, width=0.3, ref=ref)]
