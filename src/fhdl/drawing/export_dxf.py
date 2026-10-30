"""Sheet → DXF (ezdxf). 레이어·색은 sheet.LAYERS, 단위 mm (용지 좌표 그대로).

AutoCAD 등 기존 CAD 에서 그대로 열 수 있다. 채운 다각형은 SOLID HATCH, 글자는 TEXT.
"""
from __future__ import annotations

from .sheet import LAYERS, Circle, Line, Polyline, Sheet, Text

_HALIGN = {"start": 0, "middle": 1, "end": 2}       # TEXT halign: LEFT/CENTER/RIGHT
_VALIGN = {"baseline": 0, "middle": 2, "top": 3}    # TEXT valign: BASELINE/MIDDLE/TOP


def _rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def sheet_to_dxf(sheet: Sheet):
    """ezdxf Drawing 객체를 만든다 (ezdxf 미설치 시 ImportError)."""
    import ezdxf
    from ezdxf import units as dxf_units

    doc = ezdxf.new("R2010", setup=True)
    doc.units = dxf_units.MM
    doc.header["$INSUNITS"] = 4
    style = doc.styles.get("Standard")
    if style is not None:
        style.dxf.font = "malgun.ttf"   # 한글 표시 (없으면 CAD 가 대체 글꼴 사용)
    for name, (desc, color) in LAYERS.items():
        layer = doc.layers.add(name)
        layer.rgb = _rgb(color)
        layer.description = desc
    msp = doc.modelspace()
    for it in sheet.items:
        attr = {"layer": it.layer if it.layer in LAYERS else "TEXT"}
        if isinstance(it, Line):
            msp.add_line(it.p1, it.p2, dxfattribs=attr)
        elif isinstance(it, Polyline):
            if it.fill and len(it.pts) >= 3:
                hatch = msp.add_hatch(dxfattribs=attr)
                hatch.paths.add_polyline_path(it.pts, is_closed=True)
            msp.add_lwpolyline(it.pts, close=it.closed, dxfattribs=attr)
        elif isinstance(it, Circle):
            if it.fill:
                hatch = msp.add_hatch(dxfattribs=attr)
                edge = hatch.paths.add_edge_path()
                edge.add_arc(it.center, it.r, 0, 360)
            msp.add_circle(it.center, it.r, dxfattribs=attr)
        elif isinstance(it, Text):
            t = msp.add_text(it.text, height=it.height, rotation=it.angle, dxfattribs=attr)
            t.dxf.halign = _HALIGN.get(it.anchor, 0)
            t.dxf.valign = _VALIGN.get(it.valign, 0)
            t.dxf.insert = it.pos
            t.dxf.align_point = it.pos
    return doc


def save_dxf(sheets, path: str) -> str:
    """Sheet 하나는 그대로, 여러 장이면 가로로 나란히(간격 20mm) 한 DXF 에 담는다."""
    if isinstance(sheets, Sheet):
        doc = sheet_to_dxf(sheets)
    else:
        merged = Sheet(width=0.0, height=max(s.height for s in sheets), title=sheets[0].title)
        x = 0.0
        for s in sheets:
            merged.extend(_shifted(s, x))
            x += s.width + 20.0
        merged.width = x
        doc = sheet_to_dxf(merged)
    doc.saveas(path)
    return path


def _shifted(sheet: Sheet, dx: float):
    import copy
    out = []
    for it in sheet.items:
        c = copy.copy(it)
        if isinstance(c, Line):
            c.p1, c.p2 = (c.p1[0] + dx, c.p1[1]), (c.p2[0] + dx, c.p2[1])
        elif isinstance(c, Polyline):
            c.pts = [(x + dx, y) for x, y in c.pts]
        elif isinstance(c, (Circle,)):
            c.center = (c.center[0] + dx, c.center[1])
        elif isinstance(c, Text):
            c.pos = (c.pos[0] + dx, c.pos[1])
        out.append(c)
    return out
