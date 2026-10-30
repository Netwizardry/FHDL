"""배관 도면 생성 — 단선 아이소메트릭(ISO 6412-2 스타일)·평면도·정면도.

해석 결과(AnalysisResult)를 받아 Sheet 를 만든다. 도면은 DSL 에서 자동 생성되는
출력물이며, 도면 요소의 `ref` 로 원본 노드·배관을 역추적한다(GUI Inverse Sync).

그리는 것:
- 배관 중심선(경유점 via 포함), 꺾임점·분기점 용접점, 흐름 방향 화살표
- 부속 기호(fittings, `@` 위치가 없으면 배관을 따라 균등 배치 — 개략 위치)
- 구간 치수(mm), 배관 주석(ID·호칭경·재질·유량·유속), 노드 주석(ID·EL·요구조건)
- 평면도의 수직관 UP/DN 표시, 방위(N) 표시, 표제란, 자재표(BOM), 단관 절단표
"""
from __future__ import annotations

import math
from collections import Counter, OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

from ..core.fittings import FITTINGS, fitting_symbol, parse_fitting_placements
from ..core.geometry import (
    bend_angles, norm, point_at, polyline_length, spool_cut_lengths, sub, unit,
)
from ..core.pipe_sizes import nominal_size
from ..core.units import display_units
from . import frame
from .layout import node_positions
from .projection import Fit, PROJECTIONS, frame_axes, project_dir, symbol_frame
from .sheet import Circle, Line, Polyline, Sheet, Text
from .symbols import pump_symbol, render_symbol, tank_symbol, weld_dot

VIEW_LABELS = {
    "iso": "ISOMETRIC (ISO 6412-2)",
    "plan": "PLAN (평면도)",
    "elevation": "ELEVATION (정면도, 남→북)",
}

SYM = 2.6          # 부속 기호 반폭 mm
DOT_OFS = 2.2      # 용접점 — 꺾임점에서의 거리 mm
DIM_OFS = 7.0      # 치수선 오프셋 mm
MIN_DIM = 9.0      # 이보다 짧게 보이는 구간은 치수 생략 mm


def _nice_inch(inch: float) -> str:
    whole = int(inch)
    frac = inch - whole
    fr = {0.25: "1/4", 0.375: "3/8", 0.5: "1/2", 0.75: "3/4"}.get(round(frac, 3), "")
    if whole and fr:
        return f'{whole}-{fr}"'
    return f'{fr or whole}"'


def size_label(d_m: float) -> str:
    s = nominal_size(d_m)
    return f"{s.nominal_a}A({_nice_inch(s.nominal_inch)})"


def _text_angle(d: Tuple[float, float]) -> float:
    ang = math.degrees(math.atan2(d[1], d[0]))
    if ang > 90.0:
        ang -= 180.0
    elif ang <= -90.0:
        ang += 180.0
    return ang


def _add(p: Sequence[float], d: Sequence[float], k: float) -> Tuple[float, float]:
    return (p[0] + d[0] * k, p[1] + d[1] * k)


class _Ctx:
    def __init__(self, result, view: str):
        self.r = result
        self.em = result.entity_map
        self.view = view
        self.proj = PROJECTIONS[view]
        self.pr = {p.pipe_id: p for p in result.pipe_results}
        self.nr = {n.node_id: n for n in result.node_results}
        self.units = display_units(self.em.fluid.unit_system)
        self.pos, self.auto_nodes = node_positions(self.em)
        auto = set(self.auto_nodes)
        self.routes: Dict[str, List[Tuple[float, float, float]]] = {}
        for pid, p in self.em.pipes.items():
            if p.start_id not in self.pos or p.end_id not in self.pos:
                continue
            via = [] if (p.start_id in auto or p.end_id in auto) else [tuple(v) for v in p.via]
            pts = [self.pos[p.start_id]] + via + [self.pos[p.end_id]]
            clean = [pts[0]]
            for q in pts[1:]:
                if norm(sub(q, clean[-1])) > 1e-9:
                    clean.append(q)
            if len(clean) >= 2:
                self.routes[pid] = clean
        all2d = [self.proj(p) for p in self.pos.values()]
        for pts in self.routes.values():
            all2d += [self.proj(p) for p in pts]
        self.all2d = all2d

    def diameter(self, pid: str) -> float:
        pr = self.pr.get(pid)
        if pr and pr.diameter > 0:
            return pr.diameter
        return self.em.pipes[pid].diameter.value or 0.05

    def flow_sign(self, pid: str) -> float:
        pr = self.pr.get(pid)
        return -1.0 if pr and pr.flow < 0 else 1.0


def build_piping_sheet(result, view: str = "iso", project: str = "", sheet_no: str = "1/1",
                       form: str = "company") -> Sheet:
    """form = "company"(도면 양식 DXF 추출 양식, 기본) | "simple"(간이 도곽)."""
    if view not in PROJECTIONS:
        raise ValueError(f"알 수 없는 도면 종류: {view}")
    sheet = Sheet(title=f"PIPING {VIEW_LABELS[view].split(' ')[0]}", view=view)
    form_data = frame.company_form() if form == "company" else None
    if result is None or result.entity_map is None:
        if form_data:
            frame.draw_company_form(sheet, form_data, {"sheet": sheet_no, "job_no": project}, [], [])
        else:
            frame.draw_border(sheet)
            frame.draw_title_block(sheet, sheet.title, project or "-", VIEW_LABELS[view], sheet_no)
        return sheet
    c = _Ctx(result, view)
    area = tuple(form_data["drawing_area"]) if form_data else frame.drawing_area(sheet)
    fit = Fit(c.all2d, area, margin=18.0, right_extra=32.0)
    to_paper = lambda p3: fit(c.proj(p3))  # noqa: E731
    sheet.fit = (fit.scale, fit.ox, fit.oy)

    if not form_data:
        frame.draw_border(sheet)
    unplaced_fittings = False
    turn_nodes = Counter()   # 노드별 연결 배관 수 (분기·꺾임 용접점)
    for p in c.em.pipes.values():
        if p.entity_id in c.routes:
            turn_nodes[p.start_id] += 1
            turn_nodes[p.end_id] += 1

    # --- 배관 ---------------------------------------------------------
    for pid, pts in c.routes.items():
        paper = [to_paper(p) for p in pts]
        sheet.add(Polyline(paper, layer="PIPE", width=0.5, ref=pid))
        # 평면/정면도에서 시선 방향 구간(투영 길이 0) → UP/DN 표시
        for i in range(len(pts) - 1):
            seg2 = sub(paper[i + 1] + (0,), paper[i] + (0,))
            if math.hypot(seg2[0], seg2[1]) < 0.8:
                _rise_mark(sheet, paper[i], pts[i], pts[i + 1], view, pid, c.em.fluid.unit_system)
        # 경유점 꺾임 용접점
        for i, ang in enumerate(bend_angles(pts), start=1):
            if ang <= 0:
                continue
            for j in (i - 1, i + 1):
                d = sub(paper[j] + (0,), paper[i] + (0,))
                L = math.hypot(d[0], d[1])
                if L > DOT_OFS * 2:
                    sheet.add(weld_dot(_add(paper[i], (d[0] / L, d[1] / L), DOT_OFS), ref=pid))

    # 분기(티)·노드 꺾임 용접점: 배관 2개 이상이 만나는 junction
    for nid, cnt in turn_nodes.items():
        if cnt < 2 or nid not in c.em.junctions:
            continue
        o = to_paper(c.pos[nid])
        for pid, pts in c.routes.items():
            p = c.em.pipes[pid]
            if nid not in (p.start_id, p.end_id):
                continue
            nxt = to_paper(pts[1] if p.start_id == nid else pts[-2])
            d = (nxt[0] - o[0], nxt[1] - o[1])
            L = math.hypot(*d)
            if L > DOT_OFS * 2:
                sheet.add(weld_dot(_add(o, (d[0] / L, d[1] / L), DOT_OFS), ref=nid))

    # --- 부속 기호 · 흐름 화살표 · 치수 · 배관 주석 --------------------------
    lf, lu = c.units["length"]
    ff, fu = c.units["flow"]
    label_spots: List[Tuple[float, float]] = []
    for pid, pts in c.routes.items():
        pipe = c.em.pipes[pid]
        route_len = polyline_length(pts)
        decl = pipe.length if pipe.length > 0 else route_len
        placements = [fp for fp in parse_fitting_placements(pipe.fittings) if fitting_symbol(fp.canon)]
        free = [fp for fp in placements if fp.at_m is None and fp.at_frac is None]
        if free:
            unplaced_fittings = True
        k_free = 0
        sym_spots: List[Tuple[float, float]] = []   # 부속 기호 위치 (흐름 화살표가 피함)
        for fp in placements:
            if fp.at_m is not None:
                d_route = fp.at_m * route_len / decl if decl > 0 else fp.at_m
            elif fp.at_frac is not None:
                d_route = fp.at_frac * route_len
            else:
                k_free += 1
                d_route = route_len * k_free / (len(free) + 1)
            p3, u = point_at(pts, d_route)
            a, b = symbol_frame(view, u)
            axes = frame_axes(view, u) if view == "iso" else None
            base = to_paper(p3)
            sym_spots.append(base)
            for k in range(fp.count):
                off = (k - (fp.count - 1) / 2) * SYM * 2.4
                sheet.extend(render_symbol(fitting_symbol(fp.canon), _add(base, a, off), a, b, SYM,
                                           ref=pid, axes=axes))

        # 흐름 화살표: 투영상 가장 긴 구간에서 부속 기호와 가장 먼 지점 (기본 35%)
        segs = [(i, math.dist(to_paper(pts[i]), to_paper(pts[i + 1]))) for i in range(len(pts) - 1)]
        i_long, L_long = max(segs, key=lambda s: s[1])
        if L_long > 6.0:
            sgn = c.flow_sign(pid)
            p_a, p_b = to_paper(pts[i_long]), to_paper(pts[i_long + 1])

            def _at(t):
                return (p_a[0] + (p_b[0] - p_a[0]) * t, p_a[1] + (p_b[1] - p_a[1]) * t)

            cands = [0.35, 0.5, 0.65, 0.25, 0.75, 0.15, 0.85, 0.42, 0.58]
            if sgn < 0:
                cands = [1 - t for t in cands]
            clear = lambda t: min((math.dist(_at(t), q) for q in sym_spots), default=99.0)  # noqa: E731
            t = next((t for t in cands if clear(t) > SYM * 2.2), max(cands, key=clear))
            tip = _at(t)
            u = tuple(x * sgn for x in unit(sub(pts[i_long + 1], pts[i_long])))
            a, b = symbol_frame(view, u)
            sheet.extend(render_symbol("flow_arrow", tip, a, b, 2.2, ref=pid,
                                       axes=frame_axes(view, u) if view == "iso" else None))

        # 구간 치수
        for i in range(len(pts) - 1):
            p_a, p_b = to_paper(pts[i]), to_paper(pts[i + 1])
            if math.dist(p_a, p_b) < MIN_DIM:
                continue
            seg_len = norm(sub(pts[i + 1], pts[i]))
            _dimension(sheet, p_a, p_b, symbol_frame(view, unit(sub(pts[i + 1], pts[i])))[1],
                       _fmt_len(seg_len, c.em.fluid.unit_system), pid)

        # 배관 주석 (가장 긴 구간 가운데, 치수 반대편)
        p_a, p_b = to_paper(pts[i_long]), to_paper(pts[i_long + 1])
        mid = ((p_a[0] + p_b[0]) / 2, (p_a[1] + p_b[1]) / 2)
        a, b = symbol_frame(view, unit(sub(pts[i_long + 1], pts[i_long])))
        if L_long < 6.0:
            a, b = (1.0, 0.0), (0.0, 1.0)
        ang = _text_angle(a)
        pr = c.pr.get(pid)
        line1 = f"{pid}  {size_label(c.diameter(pid))}  {pipe.material}"
        line2 = (f"Q {abs(pr.flow) * ff:.1f} {fu} · v {pr.velocity:.2f} m/s" if pr else "")
        # 겹치는 배관(정면도의 나란한 관 등) 주석은 b 반대쪽으로 한 단씩 밀어낸다
        shift = 0.0
        while any(math.dist(_add(mid, b, -shift), q) < 6.0 for q in label_spots):
            shift += 7.5
        label_spots.append(_add(mid, b, -shift))
        sheet.add(Text(_add(mid, b, -3.2 - shift), line1, height=2.3, layer="TEXT", angle=ang,
                       anchor="middle", valign="top", ref=pid))
        if line2:
            sheet.add(Text(_add(mid, b, -6.6 - shift), line2, height=2.0, layer="TEXT", angle=ang,
                           anchor="middle", valign="top", ref=pid))

    # --- 노드(장비·말단) ----------------------------------------------------
    placed: List[Tuple[float, float, float, float]] = []
    up = project_dir(view, (0.0, 0.0, 1.0))
    ex = project_dir(view, (1.0, 0.0, 0.0))
    ny = project_dir(view, (0.0, 1.0, 0.0))
    for nid in c.em.all_node_ids():
        if nid not in c.pos:
            continue
        o = to_paper(c.pos[nid])
        ent = c.em.get_node_entity(nid)
        label = [nid, f"EL {ent.elevation:+.3f}"]
        if nid in c.em.tanks:
            sheet.extend(tank_symbol((o[0], o[1] - 0.0), 4.5, (up[0] * 1.0, up[1] * 1.0), (ex, ny),
                                     ref=nid))
        elif nid in c.em.pumps:
            out_dir = _out_dir(c, nid, to_paper)
            sheet.extend(pump_symbol(o, 3.4, out_dir, ref=nid))
            s = c.r.summary
            if s.recommended_pump_head > 0:
                label.append(f"H {s.recommended_pump_head:.1f} m (권장)")
        elif nid in c.em.terminals:
            in_d = _in_dir3(c, nid)
            if in_d is not None:
                a, b = symbol_frame(view, in_d)
                sheet.extend(render_symbol("nozzle", o, a, b, 2.4, ref=nid))
            t = c.em.terminals[nid]
            pf, pu = c.units["press"]
            label.append(f"{t.required_q * ff:.0f} {fu} @ {t.required_p * pf:.2f} {pu}")
        else:
            if turn_nodes.get(nid, 0) < 2:
                sheet.add(Circle(o, 0.8, layer="PIPE", fill=True, ref=nid))
        _place_label(sheet, placed, o, label, nid)

    # --- 방위 · 표 · 표제란 ------------------------------------------------
    x0, y0, x1, y1 = area
    na = tuple(form_data["north_arrow"]) if form_data else (x1 - 16.0, y1 - 14.0)
    if view in ("iso", "plan"):
        frame.draw_north_arrow(sheet, na, project_dir(view, (0.0, 1.0, 0.0)),
                               size=5.5 if form_data else 7.0)
    else:
        sheet.add(Text((x1 - 4.0, y1 - 6.0), "VIEW: 남측에서 북쪽을 봄", height=2.4,
                       layer="NORTH", anchor="end"))

    cut_rows = []
    short_any = False
    for pid, pts in c.routes.items():
        if len(pts) < 3:
            continue
        for sp in spool_cut_lengths(pts, c.diameter(pid)):
            cut_rows.append([pid, str(sp.index + 1), f"{sp.length_m * 1000:.0f}",
                             f"{sp.cut_m * 1000:.0f}" + (" ⚠" if sp.short else "")])
            short_any = short_any or sp.short
    notes = [
        "좌표계: x=동(E), y=북(N), z=상. 치수 단위 " + ("mm" if lu == "m" else "ft") + ", EL 은 datum 기준(m).",
        "축척 없음(NTS). 도면은 FHDL DSL 에서 자동 생성된다.",
    ]
    if cut_rows:
        notes.append("절단 길이 = 구간 C-C − 롱 엘보 테이크오프(1.5D·tan(θ/2), KS/JIS).")
    if short_any:
        notes.append("⚠ 표시 구간은 C-C 가 양 끝 엘보 테이크오프 합보다 짧음 — 엘보 직결(단관 없음) 또는 경로 조정 필요.")
    if unplaced_fittings:
        notes.append("위치(@)를 지정하지 않은 부속은 배관을 따라 균등 배치(개략 위치).")
    if c.auto_nodes:
        notes.append("좌표 미지정 노드 자동 배치(개략): " + ", ".join(c.auto_nodes))
    sheet.notes = notes
    bom = bom_rows(c)

    if form_data:
        sheet.add(Text((x0 + 4.0, y1 - 6.0), f"{sheet.title} — {VIEW_LABELS[view]}", height=3.0,
                       layer="TEXT"))
        # 양식 칸이 좁다: SIZE = 호칭 A 만, Q'TY 는 공백 없이
        def _qty(q: str) -> str:
            q = q.replace(" ", "")
            return f"{float(q[:-1]):.0f}m" if q.endswith("m") and len(q) > 5 else q

        rows = [[no, size.split("(")[0], _qty(qty), desc[5:] if desc.startswith("PIPE ") else "",
                 desc] for no, desc, size, qty in bom]
        if cut_rows:
            rows.append(["", "", "", "", "PIPE CUT LENGTH (mm)  LINE#SEG  C-C / CUT"])
            rows += [["", "", "", "", f"{pid}#{seg}  {cc} / {cut}"] for pid, seg, cc, cut in cut_rows]
        frame.draw_company_form(sheet, form_data, _form_fields(c, project, view, sheet_no), rows, notes)
        return sheet

    rx = sheet.width - frame.MARGIN - frame.RIGHT_W + 2.0
    rw = frame.RIGHT_W - 4.0
    y = sheet.height - frame.MARGIN - 2.0
    y = frame.draw_table(sheet, rx, y, rw, "BILL OF MATERIAL",
                         ["NO", "DESCRIPTION", "SIZE", "Q'TY"], [8, 52, 22, 18], bom, 16)
    if cut_rows:
        y = frame.draw_table(sheet, rx, y, rw, "PIPE CUT LENGTH (mm)",
                             ["LINE", "SEG", "C-C", "CUT"], [40, 12, 24, 24], cut_rows, 14)
    frame.draw_notes(sheet, rx, y, rw, notes)
    frame.draw_title_block(sheet, sheet.title, project or "FHDL", VIEW_LABELS[view], sheet_no)
    return sheet


def _form_fields(c: "_Ctx", project: str, view: str, sheet_no: str) -> Dict[str, str]:
    """회사 양식 표제란 채움 값. 운전 압력 = 노드 최대 게이지압(kg/cm²), 온도 = 유체 온도."""
    import datetime as _dt
    p_max = max((n.p_gauge for n in c.r.node_results), default=0.0)
    lines = list(c.em.pipes)
    return {
        "line_no": ", ".join(lines) if len(lines) <= 3 else f"{lines[0]} 외 {len(lines) - 1}",
        "commodity": str(c.em.fluid.fluid_type).upper(),
        "job_no": project or "FHDL", "sheet": sheet_no, "rev": "0",
        "rev_no": "0", "rev_year": _dt.date.today().strftime("%Y"),
        "rev_md": _dt.date.today().strftime("%m.%d"),
        "rev_desc": "FHDL 자동 생성", "drawn": "FHDL",
        "area": project or "-", "unit": {"iso": "ISO", "plan": "PLAN", "elevation": "ELEV"}[view],
        "oper_press": f"{p_max / 98066.5:.2f}", "oper_temp": f"{c.em.fluid.temp:g}",
    }


def _place_label(sheet: Sheet, placed: list, o, lines: List[str], ref: str) -> None:
    """노드 주석을 기존 주석과 겹치지 않는 자리(우상·우하·좌상·좌하 순)에 놓는다."""
    w = max(len(s) for s in lines) * 1.55 + 1.0
    h = 3.2 * len(lines) + 1.0
    cands = [(4.5, 5.5, "start"), (4.5, -6.0 - h + 3.2, "start"),
             (-4.5, 5.5, "end"), (-4.5, -6.0 - h + 3.2, "end"), (4.5, 5.5 + h, "start")]
    choice = cands[0]
    for dx, dy, anchor in cands:
        x0 = o[0] + dx if anchor == "start" else o[0] + dx - w
        rect = (x0, o[1] + dy - h + 3.2, x0 + w, o[1] + dy + 3.2)
        if not any(rect[0] < r[2] and r[0] < rect[2] and rect[1] < r[3] and r[1] < rect[3] for r in placed):
            choice = (dx, dy, anchor)
            placed.append(rect)
            break
    else:
        dx, dy, anchor = choice
    dx, dy, anchor = choice
    for k, s_ in enumerate(lines):
        sheet.add(Text((o[0] + dx, o[1] + dy - k * 3.2), s_, height=2.6 if k == 0 else 2.1,
                       layer="TEXT", anchor=anchor, ref=ref))


def _fmt_len(m: float, unit_system: str) -> str:
    if str(unit_system).upper() == "IMPERIAL":
        return f"{m * 3.2808399:.2f}'"
    return f"{m * 1000:.0f}"


def _dimension(sheet: Sheet, p_a, p_b, b_dir, text: str, ref: str) -> None:
    """정렬 치수: 연장선(b 방향) + 치수선 + 사선 틱 + 글자."""
    e0 = _add(p_a, b_dir, 1.2)
    e1 = _add(p_b, b_dir, 1.2)
    d0 = _add(p_a, b_dir, DIM_OFS)
    d1 = _add(p_b, b_dir, DIM_OFS)
    sheet.add(Line(e0, _add(p_a, b_dir, DIM_OFS + 1.2), layer="DIM", width=0.18, ref=ref))
    sheet.add(Line(e1, _add(p_b, b_dir, DIM_OFS + 1.2), layer="DIM", width=0.18, ref=ref))
    sheet.add(Line(d0, d1, layer="DIM", width=0.18, ref=ref))
    ux, uy = d1[0] - d0[0], d1[1] - d0[1]
    L = math.hypot(ux, uy) or 1.0
    ux, uy = ux / L, uy / L
    tick = ((ux + b_dir[0]) * 0.9, (uy + b_dir[1]) * 0.9)
    for p in (d0, d1):
        sheet.add(Line((p[0] - tick[0], p[1] - tick[1]), (p[0] + tick[0], p[1] + tick[1]),
                       layer="DIM", width=0.3, ref=ref))
    mid = ((d0[0] + d1[0]) / 2, (d0[1] + d1[1]) / 2)
    sheet.add(Text(_add(mid, b_dir, 1.0), text, height=2.2, layer="DIM", angle=_text_angle((ux, uy)),
                   anchor="middle", ref=ref))


def _rise_mark(sheet: Sheet, at, p_from, p_to, view: str, ref: str, us: str = "METRIC") -> None:
    """평면도/정면도에서 시선 방향 수직·수평관: 원 + 점(올라옴) / 원 + X(내려감)."""
    toward_viewer = {"plan": 2, "elevation": 1}.get(view)
    if toward_viewer is None:
        return
    d = p_to[toward_viewer] - p_from[toward_viewer]
    if view == "elevation":
        d = -d   # 정면도는 남쪽(−y)에서 봄 → 북쪽(+y)으로 가는 관은 멀어짐
    r = 1.8
    sheet.add(Circle(at, r, layer="PIPE", width=0.3, ref=ref))
    if d > 0:
        sheet.add(Circle(at, 0.5, layer="PIPE", fill=True, ref=ref))
        tag = "UP" if view == "plan" else "▲"
    else:
        k = r * 0.7
        sheet.add(Line((at[0] - k, at[1] - k), (at[0] + k, at[1] + k), layer="PIPE", width=0.3, ref=ref))
        sheet.add(Line((at[0] - k, at[1] + k), (at[0] + k, at[1] - k), layer="PIPE", width=0.3, ref=ref))
        tag = "DN" if view == "plan" else "▼"
    if view == "plan":
        sheet.add(Text((at[0] + 2.4, at[1] - 3.6), f"{tag} {_fmt_len(abs(p_to[2] - p_from[2]), us)}",
                       height=2.0, layer="DIM", ref=ref))


def _out_dir(c: _Ctx, nid: str, to_paper) -> Tuple[float, float]:
    for pid, pts in c.routes.items():
        if c.em.pipes[pid].start_id == nid:
            a, b = to_paper(pts[0]), to_paper(pts[1])
            if math.dist(a, b) > 1e-6:
                return (b[0] - a[0], b[1] - a[1])
    return (1.0, 0.0)


def _in_dir3(c: _Ctx, nid: str):
    for pid, pts in c.routes.items():
        if c.em.pipes[pid].end_id == nid:
            return unit(sub(pts[-1], pts[-2]))
    return None


def bom_rows(c: _Ctx) -> List[List[str]]:
    """자재표: 배관(재질·호칭경별 총길이), 엘보(경유점 꺾임), 티(분기), 밸브·부속."""
    items: "OrderedDict[Tuple[str, str], float]" = OrderedDict()

    def add(desc: str, size: str, q: float) -> None:
        items[(desc, size)] = items.get((desc, size), 0.0) + q

    for pid, pipe in c.em.pipes.items():
        size = size_label(c.diameter(pid))
        L = pipe.length if pipe.length > 0 else polyline_length(c.routes.get(pid, [(0, 0, 0)] * 2))
        add(f"PIPE {pipe.material}", size, L)
    for pid, pts in c.routes.items():
        size = size_label(c.diameter(pid))
        for ang in bend_angles(pts):
            if ang <= 0:
                continue
            add("ELBOW 45° LR" if ang <= 60 else "ELBOW 90° LR", size, 1)
    deg = Counter()
    for p in c.em.pipes.values():
        deg[p.start_id] += 1
        deg[p.end_id] += 1
    for nid in c.em.junctions:
        if deg[nid] >= 3:
            ds = [c.diameter(p.entity_id) for p in c.em.pipes.values() if nid in (p.start_id, p.end_id)]
            add("TEE", size_label(max(ds)), 1)
    for pid, pipe in c.em.pipes.items():
        size = size_label(c.diameter(pid))
        for fp in parse_fitting_placements(pipe.fittings):
            if not fp.canon or fp.canon in ("entrance", "exit"):
                continue
            add(FITTINGS[fp.canon][1], size, fp.count)
    rows = []
    for i, ((desc, size), q) in enumerate(items.items(), 1):
        if desc.startswith("PIPE"):
            imp = str(c.em.fluid.unit_system).upper() == "IMPERIAL"
            qty = f"{q * 3.2808399:.1f} ft" if imp else f"{q:.1f} m"
        else:
            qty = f"{int(q)} EA"
        rows.append([str(i), desc, size, qty])
    return rows
