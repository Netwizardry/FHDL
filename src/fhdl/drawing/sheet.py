"""도면 기본 요소(primitive)와 도면 시트.

모든 좌표는 용지 좌표(mm, 원점 좌하단, y 위쪽 — DXF 와 같은 방향)다.
SVG/PDF/GUI 렌더러는 y 를 뒤집어 그린다. `ref` 는 원본 엔티티 ID(노드·배관)로,
GUI 에서 도면을 클릭했을 때 어떤 객체인지 찾는 데 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

P2 = Tuple[float, float]

# 레이어 → (설명, 색상 #RRGGBB). 참고 기호표 DXF 의 레이어 구분(PIPE·VLVS·FITTS·EQPT·INSTR)을 따른다.
LAYERS: Dict[str, Tuple[str, str]] = {
    "BORDER":  ("도곽·표제란", "#000000"),
    "PIPE":    ("배관 중심선", "#000000"),
    "VALVE":   ("밸브", "#C00000"),
    "FITTING": ("부속·용접점", "#1F4FBF"),
    "EQPT":    ("장비(탱크·펌프·말단)", "#000000"),
    "INSTR":   ("계기", "#8A2BE2"),
    "FLOW":    ("흐름 방향", "#D00000"),
    "DIM":     ("치수", "#007A33"),
    "TEXT":    ("주석", "#000000"),
    "NORTH":   ("방위 표시", "#000000"),
}


@dataclass
class Line:
    p1: P2
    p2: P2
    layer: str = "PIPE"
    width: float = 0.25          # 선 굵기 mm
    ref: str = ""


@dataclass
class Polyline:
    pts: List[P2]
    layer: str = "PIPE"
    closed: bool = False
    fill: bool = False
    width: float = 0.25
    ref: str = ""


@dataclass
class Circle:
    center: P2
    r: float
    layer: str = "FITTING"
    fill: bool = False
    width: float = 0.25
    ref: str = ""


@dataclass
class Text:
    pos: P2
    text: str
    height: float = 2.5          # 글자 높이 mm
    layer: str = "TEXT"
    angle: float = 0.0           # 반시계 방향 도(°)
    anchor: str = "start"        # start | middle | end
    valign: str = "baseline"     # baseline | middle | top
    ref: str = ""


Item = object  # Line | Polyline | Circle | Text


@dataclass
class Sheet:
    width: float = 420.0         # A3 가로
    height: float = 297.0
    title: str = ""
    view: str = ""
    items: List[Item] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    # 모델 → 용지 변환 (scale mm/m, ox, oy) — 평면도·정면도에서 GUI 드래그를 모델 좌표로 역변환
    fit: Optional[Tuple[float, float, float]] = None

    def add(self, item) -> None:
        self.items.append(item)

    def extend(self, items) -> None:
        self.items.extend(items)

    def by_layer(self, layer: str) -> List[Item]:
        return [i for i in self.items if getattr(i, "layer", "") == layer]

    def refs(self) -> set:
        return {i.ref for i in self.items if getattr(i, "ref", "")}

    def bbox(self, layer: Optional[str] = None) -> Tuple[float, float, float, float]:
        xs, ys = [], []
        for it in self.items:
            if layer and it.layer != layer:
                continue
            for x, y in _points_of(it):
                xs.append(x)
                ys.append(y)
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))


def _points_of(it) -> List[P2]:
    if isinstance(it, Line):
        return [it.p1, it.p2]
    if isinstance(it, Polyline):
        return list(it.pts)
    if isinstance(it, Circle):
        (x, y), r = it.center, it.r
        return [(x - r, y - r), (x + r, y + r)]
    if isinstance(it, Text):
        return [it.pos]
    return []
