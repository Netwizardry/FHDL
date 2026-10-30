"""Sheet → SVG (단위 mm, 레이어 = <g id>)."""
from __future__ import annotations

from xml.sax.saxutils import escape

from .sheet import LAYERS, Circle, Line, Polyline, Sheet, Text

_ANCHOR = {"start": "start", "middle": "middle", "end": "end"}
_BASELINE = {"baseline": "auto", "middle": "central", "top": "hanging"}


def sheet_to_svg(sheet: Sheet) -> str:
    H = sheet.height

    def y(v: float) -> float:
        return H - v

    groups = {name: [] for name in LAYERS}
    for it in sheet.items:
        layer = it.layer if it.layer in groups else "TEXT"
        color = LAYERS.get(layer, ("", "#000000"))[1]
        ref = f' data-ref="{escape(it.ref)}"' if getattr(it, "ref", "") else ""
        if isinstance(it, Line):
            groups[layer].append(
                f'<line x1="{it.p1[0]:.3f}" y1="{y(it.p1[1]):.3f}" x2="{it.p2[0]:.3f}" '
                f'y2="{y(it.p2[1]):.3f}" stroke="{color}" stroke-width="{it.width}"{ref}/>')
        elif isinstance(it, Polyline):
            pts = " ".join(f"{x:.3f},{y(v):.3f}" for x, v in it.pts)
            tag = "polygon" if it.closed else "polyline"
            fill = color if it.fill else "none"
            groups[layer].append(
                f'<{tag} points="{pts}" fill="{fill}" stroke="{color}" '
                f'stroke-width="{it.width}" stroke-linejoin="round"{ref}/>')
        elif isinstance(it, Circle):
            fill = color if it.fill else "none"
            groups[layer].append(
                f'<circle cx="{it.center[0]:.3f}" cy="{y(it.center[1]):.3f}" r="{it.r:.3f}" '
                f'fill="{fill}" stroke="{color}" stroke-width="{it.width}"{ref}/>')
        elif isinstance(it, Text):
            x0, y0 = it.pos[0], y(it.pos[1])
            rot = f' transform="rotate({-it.angle:.2f} {x0:.3f} {y0:.3f})"' if it.angle else ""
            groups[layer].append(
                f'<text x="{x0:.3f}" y="{y0:.3f}" font-size="{it.height:.2f}" '
                f'text-anchor="{_ANCHOR.get(it.anchor, "start")}" '
                f'dominant-baseline="{_BASELINE.get(it.valign, "auto")}" fill="{color}"{rot}{ref}>'
                f'{escape(it.text)}</text>')
    body = []
    for name, elems in groups.items():
        if elems:
            body.append(f'<g id="{name}">\n' + "\n".join(elems) + "\n</g>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet.width}mm" height="{sheet.height}mm" '
        f'viewBox="0 0 {sheet.width} {sheet.height}" '
        'font-family="Malgun Gothic, NanumGothic, Noto Sans CJK KR, DejaVu Sans, sans-serif">\n'
        f'<title>{escape(sheet.title)}</title>\n'
        f'<rect width="{sheet.width}" height="{sheet.height}" fill="#FFFFFF"/>\n'
        + "\n".join(body) + "\n</svg>\n")


def save_svg(sheet: Sheet, path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(sheet_to_svg(sheet))
    return path
