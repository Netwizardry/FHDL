"""계통도(P&ID) 생성 — ISO 10628 배치 규칙 · ISO 14617 스타일 기호.

형상(좌표)이 아니라 연결 관계를 그린다: 공급원에서의 흐름 깊이를 왼쪽→오른쪽 열로,
같은 깊이의 노드를 위→아래로 놓고, 배관은 수평-수직-수평 직교선으로 잇는다.
좌표가 없는 모델도 그릴 수 있다. 밸브·계기는 배관 위에 입력 순서대로 놓는다.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..core.fittings import fitting_symbol, parse_fitting_placements
from ..core.units import display_units
from . import frame
from .layout import flow_depths
from .piping import size_label
from .sheet import Circle, Line, Polyline, Sheet, Text
from .symbols import pump_symbol, render_symbol

P2 = Tuple[float, float]


def _node_slots(em, area) -> Dict[str, P2]:
    depth = flow_depths(em)
    cols: Dict[int, List[str]] = {}
    for n in em.all_node_ids():
        cols.setdefault(depth[n], []).append(n)
    parents: Dict[str, List[str]] = {}
    for p in em.pipes.values():
        parents.setdefault(p.end_id, []).append(p.start_id)
    x0, y0, x1, y1 = area
    ncol = max(cols) + 1 if cols else 1
    dx = (x1 - x0 - 60.0) / max(ncol - 1, 1)
    rows: Dict[str, float] = {}
    pos: Dict[str, P2] = {}
    for d in sorted(cols):
        col = cols[d]
        # 부모 행의 평균(무게중심) 순으로 정렬 → 교차 감소
        col.sort(key=lambda n: sum(rows.get(p, 0.0) for p in parents.get(n, [])) /
                 max(len(parents.get(n, [])), 1))
        for i, n in enumerate(col):
            rows[n] = float(i)
        n_rows = len(col)
        dy = min((y1 - y0 - 50.0) / max(n_rows, 1), 60.0)
        top = (y0 + y1) / 2 + dy * (n_rows - 1) / 2
        for i, n in enumerate(col):
            pos[n] = (x0 + 30.0 + d * dx, top - i * dy)
    return pos


def build_pid_sheet(result, project: str = "", sheet_no: str = "1/1") -> Sheet:
    sheet = Sheet(title="P&ID", view="pid")
    frame.draw_border(sheet)
    em = getattr(result, "entity_map", None)
    if em is None:
        frame.draw_title_block(sheet, sheet.title, project or "-", "P&ID (ISO 10628)", sheet_no)
        return sheet
    units = display_units(em.fluid.unit_system)
    ff, fu = units["flow"]
    pr = {p.pipe_id: p for p in result.pipe_results}
    area = frame.drawing_area(sheet)
    pos = _node_slots(em, area)

    # --- 배관(직교선) + 밸브·계기 + 흐름 화살표 + 라인 번호 -------------------
    for pid, pipe in em.pipes.items():
        if pipe.start_id not in pos or pipe.end_id not in pos:
            continue
        a, b = pos[pipe.start_id], pos[pipe.end_id]
        xa, xb = a[0] + 7.0, b[0] - 7.0
        if xb <= xa:
            xa, xb = a[0], b[0]
        xm = xa + (xb - xa) * 0.35
        pts = [a, (xa, a[1]), (xm, a[1]), (xm, b[1]), (xb, b[1]), b]
        sheet.add(Polyline(pts, layer="PIPE", width=0.45, ref=pid))
        # 기호: 마지막 수평 구간에 순서대로
        syms = [fp for fp in parse_fitting_placements(pipe.fittings) if fitting_symbol(fp.canon)]
        n = sum(fp.count for fp in syms)
        k = 0
        for fp in syms:
            for _ in range(fp.count):
                k += 1
                x = xm + (xb - xm) * k / (n + 1.6)
                sheet.extend(render_symbol(fitting_symbol(fp.canon), (x, b[1]), (1.0, 0.0), (0.0, 1.0),
                                           2.8, ref=pid))
        sheet.extend(render_symbol("flow_arrow", (xm + (xb - xm) * (n + 1.0) / (n + 1.6), b[1]),
                                   (1.0, 0.0), (0.0, 1.0), 2.2, ref=pid))
        r = pr.get(pid)
        tag = f"{pid}-{size_label(r.diameter if r else pipe.diameter.value)}-{pipe.material}"
        sheet.add(Text((xm + 2.0, b[1] + 9.0), tag, height=2.2, layer="TEXT", ref=pid))
        if r:
            sheet.add(Text((xm + 2.0, b[1] - 3.6), f"{abs(r.flow) * ff:.1f} {fu}", height=1.9,
                           layer="DIM", valign="top", ref=pid))

    # --- 장비 기호 ------------------------------------------------------------
    for nid, (x, y) in pos.items():
        if nid in em.tanks:
            sheet.add(Polyline([(x - 7, y - 6), (x + 7, y - 6), (x + 7, y + 8), (x - 7, y + 8)],
                               layer="EQPT", closed=True, width=0.4, ref=nid))
            sheet.add(Line((x - 7, y + 4), (x + 7, y + 4), layer="EQPT", width=0.2, ref=nid))
            sheet.add(Text((x, y - 9.0), nid, height=2.6, layer="TEXT", anchor="middle", ref=nid))
        elif nid in em.pumps:
            sheet.extend(pump_symbol((x, y), 5.0, (1.0, 0.0), ref=nid))
            sheet.add(Line((x - 4, y - 7), (x + 4, y - 7), layer="EQPT", width=0.4, ref=nid))
            sheet.add(Text((x, y - 10.5), nid, height=2.6, layer="TEXT", anchor="middle", ref=nid))
            s = result.summary
            if s.recommended_pump_head > 0:
                sheet.add(Text((x, y - 14.0), f"{s.recommended_pump_flow * ff:.0f} {fu} × "
                                              f"{s.recommended_pump_head:.1f} m", height=2.0,
                               layer="DIM", anchor="middle", ref=nid))
        elif nid in em.terminals:
            sheet.extend(render_symbol("nozzle", (x - 2.4, y), (1.0, 0.0), (0.0, 1.0), 2.6, ref=nid))
            sheet.add(Text((x + 3.0, y + 3.0), nid, height=2.6, layer="TEXT", ref=nid))
            t = em.terminals[nid]
            pf, pu = units["press"]
            sheet.add(Text((x + 3.0, y - 1.0), f"{t.required_q * ff:.0f} {fu} @ {t.required_p * pf:.2f} {pu}",
                           height=2.0, layer="DIM", valign="top", ref=nid))
        else:
            sheet.add(Circle((x, y), 0.9, layer="PIPE", fill=True, ref=nid))
            sheet.add(Text((x + 2.0, y + 2.5), nid, height=2.2, layer="TEXT", ref=nid))

    # --- 장비·라인 목록 · 표제란 -------------------------------------------------
    rx = sheet.width - frame.MARGIN - frame.RIGHT_W + 2.0
    rw = frame.RIGHT_W - 4.0
    y = sheet.height - frame.MARGIN - 2.0
    eq = []
    for t in em.tanks.values():
        vol = "∞" if t.volume == float("inf") else f"{t.volume:g} m3"
        eq.append([t.entity_id, "TANK", f"V {vol}, EL {t.elevation:+.1f}"])
    for p in em.pumps.values():
        s = result.summary
        eq.append([p.entity_id, "PUMP", f"H {s.recommended_pump_head:.1f} m (권장)"
                   if p.head.mode != "MANUAL" else f"H {p.head.value:.1f} m"])
    for t in em.terminals.values():
        eq.append([t.entity_id, "TERMINAL", f"{t.required_q * ff:.0f} {fu}"])
    y = frame.draw_table(sheet, rx, y, rw, "EQUIPMENT LIST", ["TAG", "TYPE", "SPEC"], [30, 22, 48], eq, 12)
    lines = []
    for pid, pipe in em.pipes.items():
        r = pr.get(pid)
        lines.append([pid, size_label(r.diameter if r else pipe.diameter.value), pipe.material,
                      f"{abs(r.flow) * ff:.0f}" if r else "-", f"{r.velocity:.2f}" if r else "-"])
    y = frame.draw_table(sheet, rx, y, rw, "LINE LIST", ["LINE", "SIZE", "MAT'L", fu, "m/s"],
                         [28, 24, 18, 16, 14], lines, 16)
    frame.draw_notes(sheet, rx, y, rw, ["계통도: 배치는 연결 관계 기준이며 실제 위치·길이와 무관하다.",
                                        "기호: ISO 14617 스타일(밸브=나비넥타이형, 펌프=원+삼각형)."])
    frame.draw_title_block(sheet, sheet.title, project or "FHDL", "P&ID (ISO 10628)", sheet_no)
    return sheet
