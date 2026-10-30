"""도곽·표제란·자재표(BOM)·단관 절단표·방위 표시.

배치는 참고 도면 양식(archive/dxf 도면FORM)을 따른다: 오른쪽 열에 BILL OF MATERIAL,
그 아래 단관 절단표·NOTES, 아래쪽 표제란, 도면 영역 오른쪽 위에 방위(N) 표시.
용지는 A3 가로(420×297mm), 여백 10mm.
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import List, Optional, Sequence, Tuple

from .sheet import Line, Polyline, Sheet, Text

MARGIN = 10.0
RIGHT_W = 112.0       # 오른쪽 표 열 너비
TITLE_H = 30.0        # 표제란 높이
ROW_H = 4.6


def drawing_area(sheet: Sheet) -> Tuple[float, float, float, float]:
    """도면(그림) 영역 (x0, y0, x1, y1)."""
    return (MARGIN, MARGIN + TITLE_H, sheet.width - MARGIN - RIGHT_W, sheet.height - MARGIN)


def _rect(x0, y0, x1, y1, layer="BORDER", w=0.35) -> Polyline:
    return Polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer=layer, closed=True, width=w)


def draw_border(sheet: Sheet) -> None:
    m = MARGIN
    sheet.add(_rect(m, m, sheet.width - m, sheet.height - m, w=0.7))
    x_r = sheet.width - m - RIGHT_W
    sheet.add(Line((x_r, m + TITLE_H), (x_r, sheet.height - m), layer="BORDER", width=0.5))
    sheet.add(Line((m, m + TITLE_H), (sheet.width - m, m + TITLE_H), layer="BORDER", width=0.5))


def draw_title_block(sheet: Sheet, title: str, project: str, view_label: str,
                     sheet_no: str = "1/1", date: Optional[str] = None) -> None:
    """아래쪽 표제란 (오른쪽부터 칸을 채운다)."""
    m, y0, y1 = MARGIN, MARGIN, MARGIN + TITLE_H
    date = date or _dt.date.today().isoformat()
    cells = [  # (라벨, 값, 너비)
        ("PROJECT", project, 70.0), ("DRAWING TITLE", title, 110.0), ("VIEW", view_label, 60.0),
        ("SCALE", "NTS", 25.0), ("DATE", date, 32.0), ("DRAWN", "FHDL", 28.0),
        ("SHEET", sheet_no, 25.0),
    ]
    x = m
    x_end = sheet.width - m
    total = sum(c[2] for c in cells)
    k = (x_end - x) / total
    for label, value, w in cells:
        w *= k
        sheet.add(Line((x, y0), (x, y1), layer="BORDER", width=0.35))
        sheet.add(Text((x + 1.5, y1 - 4.0), label, height=2.0, layer="BORDER"))
        sheet.add(Text((x + 1.5, y0 + 9.0), str(value), height=3.5 if len(str(value)) < 28 else 2.6,
                       layer="BORDER"))
        x += w
    sheet.add(Line((m, y1 - 6.0), (x_end, y1 - 6.0), layer="BORDER", width=0.25))


def draw_table(sheet: Sheet, x0: float, y_top: float, width: float, title: str,
               headers: Sequence[str], col_w: Sequence[float], rows: List[Sequence[str]],
               max_rows: int) -> float:
    """오른쪽 열에 표를 그리고 표 아래 y 를 돌려준다. 칸 너비는 비율."""
    k = width / sum(col_w)
    cw = [c * k for c in col_w]
    y = y_top
    sheet.add(Text((x0 + width / 2, y - 3.6), title, height=3.0, layer="BORDER", anchor="middle"))
    y -= 5.5
    sheet.add(Line((x0, y), (x0 + width, y), layer="BORDER", width=0.35))
    shown = rows[:max_rows]
    if len(rows) > max_rows:
        shown = rows[:max_rows - 1] + [["…", f"외 {len(rows) - max_rows + 1}건"] + [""] * (len(headers) - 2)]
    for r_i, row in enumerate([list(headers)] + [list(r) for r in shown]):
        x = x0
        for c_i, cell in enumerate(row):
            sheet.add(Text((x + 1.0, y - ROW_H + 1.2), _fit(str(cell), cw[c_i]),
                           height=2.2 if r_i else 2.0, layer="BORDER"))
            x += cw[c_i]
        y -= ROW_H
        sheet.add(Line((x0, y), (x0 + width, y), layer="BORDER", width=0.35 if r_i == 0 else 0.18))
    x = x0
    for w in cw[:-1]:
        x += w
        sheet.add(Line((x, y_top - 5.5), (x, y), layer="BORDER", width=0.18))
    return y - 3.0


def _fit(s: str, width_mm: float, char_mm: float = 1.6) -> str:
    n = max(int(width_mm / char_mm), 1)
    return s if len(s) <= n else s[: max(n - 1, 1)] + "…"


def draw_notes(sheet: Sheet, x0: float, y_top: float, width: float, notes: List[str]) -> None:
    if not notes or y_top < MARGIN + TITLE_H + 12:
        return
    sheet.add(Text((x0 + 1.0, y_top - 3.6), "NOTES", height=3.0, layer="BORDER"))
    y = y_top - 8.5
    for i, n in enumerate(notes, 1):
        for j, chunk in enumerate(_wrap(n, int(width / 1.75))):
            if y < MARGIN + TITLE_H + 3:
                return
            sheet.add(Text((x0 + 1.0, y), (f"{i}. " if j == 0 else "   ") + chunk,
                           height=2.2, layer="BORDER"))
            y -= 3.6


def _wrap(s: str, n: int) -> List[str]:
    out, line = [], ""
    for word in s.split(" "):
        if len(line) + len(word) + 1 > n and line:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def draw_north_arrow(sheet: Sheet, center: Tuple[float, float], north_dir: Tuple[float, float],
                     size: float = 7.0) -> None:
    """방위 표시: 타원 안의 N + 북쪽 방향 화살표 (참고 ISO 상단의 방위 표시)."""
    nx, ny = north_dir
    n = math.hypot(nx, ny) or 1.0
    nx, ny = nx / n, ny / n
    cx, cy = center
    pts = [(cx + size * math.cos(t) * 1.0 * nx - size * 0.55 * math.sin(t) * ny,
            cy + size * math.cos(t) * 1.0 * ny + size * 0.55 * math.sin(t) * nx)
           for t in [2 * math.pi * i / 32 for i in range(32)]]
    sheet.add(Polyline(pts, layer="NORTH", closed=True, width=0.35))
    tail = (cx - nx * size * 1.7, cy - ny * size * 1.7)
    head = (cx + nx * size * 1.9, cy + ny * size * 1.9)
    sheet.add(Line(tail, (cx - nx * size, cy - ny * size), layer="NORTH", width=0.35))
    sheet.add(Line((cx + nx * size, cy + ny * size), head, layer="NORTH", width=0.35))
    px, py = -ny, nx
    sheet.add(Polyline([head, (head[0] - nx * 3.2 + px * 1.3, head[1] - ny * 3.2 + py * 1.3),
                        (head[0] - nx * 3.2 - px * 1.3, head[1] - ny * 3.2 - py * 1.3)],
                       layer="NORTH", closed=True, fill=True))
    sheet.add(Text((cx, cy), "N", height=size * 0.75, layer="NORTH", anchor="middle", valign="middle"))
