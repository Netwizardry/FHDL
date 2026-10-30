"""EHDL 계통 구성도 (단선결선도, SPEC 산출물 A) — fhdl.drawing 의 Sheet·내보내기를 공유.

배치: 전원을 위에 두고 아래로 흐르는 트리(방사형). 말단을 왼쪽부터 한 칸씩 놓고 부모는 자식들의
가운데. 배전반·분전반은 굵은 모선(가로선)으로 그리고, 접힌(collapsed) 반은 내부를 숨기고 집계만 표시.
기호는 IEC 60617 스타일 간략형: 전원 ○~, 변압기 겹친 두 원, 차단기 □×, 누전차단기 □×+RCD,
SPD ↯, 부하 ○ 안에 용도 글자(M 전동기·H 히터·L 조명·R 콘센트·G 일반).
설비 옆 판정 표식(●) 색 = 최악 판정, 요소 ref = 설비/배선 ID (GUI 선택·편집).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from fhdl.drawing import frame
from fhdl.drawing.sheet import Circle, Line, Polyline, Sheet, Text

from .language import NODE_TYPES
from .model import EResult, worst
from .units import fmt

_LOAD_LETTER = {"motor": "M", "heater": "H", "lighting": "L", "receptacle": "R", "general": "G"}
_ST_LAYER = {"FAIL": "ST_FAIL", "UNKNOWN": "ST_UNKNOWN", "REVIEW": "ST_REVIEW", "PASS": "ST_PASS", "N/A": "ST_NA"}


def _visible_tree(res: EResult, collapsed: Set[str]):
    """보이는 노드와 자식 목록 (접힌 반 내부 제외)."""
    kids: Dict[str, List[str]] = {}
    order: List[str] = []
    roots = [n for n in res.order if res.upstream.get(n) is None]
    stack = list(reversed(roots))
    while stack:
        nid = stack.pop()
        order.append(nid)
        ch = [] if nid in collapsed else list(res.children.get(nid, []))
        kids[nid] = ch
        stack.extend(reversed(ch))
    return order, kids


def _status(res: EResult, ids) -> str:
    return worst(c.status for c in res.checks if c.target in ids)


def build_sld(res: EResult, project: str = "", collapsed: Optional[Set[str]] = None,
              sheet_no: str = "1/1") -> Sheet:
    sheet = Sheet(title="계통 구성도 (단선결선도)", view="sld")
    frame.draw_border(sheet)
    collapsed = set(collapsed or ())
    if res is None or res.model is None or not res.order:
        frame.draw_title_block(sheet, sheet.title, project or "EHDL", "단선결선도", sheet_no, drawn="EHDL")
        return sheet
    m = res.model
    sc = res.scenarios.get(res.design_scenario) or next(iter(res.scenarios.values()))
    order, kids = _visible_tree(res, collapsed)

    # --- 배치: 말단 칸 번호 · 깊이 -----------------------------------------------
    col: Dict[str, float] = {}
    depth: Dict[str, int] = {}
    nxt = [0]

    def place(nid: str, d: int):
        depth[nid] = d
        ch = kids.get(nid, [])
        if not ch:
            col[nid] = nxt[0]
            nxt[0] += 1
            return
        for c in ch:
            place(c, d + 1)
        col[nid] = (col[ch[0]] + col[ch[-1]]) / 2.0

    for r in [n for n in order if res.upstream.get(n) is None]:
        place(r, 0)
    x0, y0, x1, y1 = frame.drawing_area(sheet)
    ncol = max(nxt[0], 1)
    nrow = max(depth.values()) + 1
    dx = min((x1 - x0 - 30.0) / ncol, 42.0)
    dy = min((y1 - y0 - 30.0) / max(nrow, 1), 34.0)
    left = x0 + 15.0 + ((x1 - x0 - 30.0) - dx * ncol) / 2 + dx / 2
    top = y1 - 16.0
    pos = {n: (left + col[n] * dx, top - depth[n] * dy) for n in order}
    th = 2.2 if dx > 28 else 1.8

    # --- 배선·모선 ---------------------------------------------------------------
    for nid in order:
        ch = kids.get(nid, [])
        if not ch:
            continue
        x, y = pos[nid]
        n = m.nodes[nid]
        bus_y = y - dy * 0.42
        if n.type in ("switchboard", "panel", "bus") or len(ch) > 1:
            xs = [pos[c][0] for c in ch] + [x]
            sheet.add(Line((min(xs) - 3, bus_y), (max(xs) + 3, bus_y), layer="WIRE",
                           width=1.2 if n.type in ("switchboard", "panel", "bus") else 0.4, ref=nid))
        sheet.add(Line((x, y - 5.0), (x, bus_y), layer="WIRE", width=0.4, ref=nid))
        for c in ch:
            cx, cy = pos[c]
            eid = res.via_edge.get(c)
            sheet.add(Line((cx, bus_y), (cx, cy + 5.0), layer="WIRE", width=0.4, ref=eid or c))
            if eid:
                e = m.edges[eid]
                r = sc.nodes.get(c)
                lab = [eid + (" [신규]" if e.stage == "new" else "")]
                need = next((ck.actual for ck in res.checks if ck.id == f"{eid}:cable_size" and ck.actual), None)
                spec = " ".join(x for x in (e.installed.get("material") or "",
                                            f"{e.installed['size']:g}㎟" if e.installed.get("size")
                                            else (f"요구 ≥{need:g}㎟" if need else "")) if x)
                if spec:
                    lab.append(spec)
                if e.params.get("length") is not None:
                    lab.append(f"{e.params['length']:g}m")
                ymid = (bus_y + cy + 5.0) / 2
                for k, t in enumerate(lab):
                    sheet.add(Text((cx + 1.2, ymid + 1.2 - k * (th + 0.6)), t, height=th * 0.85, layer="DIM",
                                   ref=eid))
                st = _status(res, [eid])
                if st != "N/A":
                    sheet.add(Circle((cx - 1.6, ymid), 0.9, layer=_ST_LAYER[st], fill=True, ref=eid))

    # --- 설비 기호 · 주석 ----------------------------------------------------------
    for nid in order:
        n = m.nodes[nid]
        x, y = pos[nid]
        _symbol(sheet, n, (x, y), nid in collapsed)
        r = sc.nodes.get(nid)
        lines = [(n.name if n.name and n.name != nid else nid) + (" [신규]" if n.stage == "new" else "")]
        rated = n.installed.get("rated_current") or n.installed.get("rated") or n.installed.get("limit_kw")
        unit = "A" if n.installed.get("rated_current") else ("VA" if n.installed.get("rated") else "W")
        if rated:
            lines.append(f"정격 {fmt(rated, unit, 0)}")
        if r is not None and n.type == "transformer":
            lines.append(f"{fmt(r.S, 'VA')} · {fmt(r.P, 'W')}")
        elif r is not None and n.type != "source" and r.current is not None:
            lines.append(f"{fmt(r.current, 'A')} · {fmt(r.P, 'W')}")
        elif r is not None and n.type == "source":
            lines.append(f"{fmt(r.P, 'W')} · {fmt(r.S, 'VA')}")
        s = getattr(res, "sc", {}).get(nid)
        if s is not None and s.ik_max and n.type in ("transformer", "switchboard", "panel", "bus", "breaker", "rcd"):
            lines.append(f"Ik'' {s.ik_max / 1000:.1f} kA" + (f" / Icu {n.installed['breaking_capacity'] / 1000:g} kA"
                                                           if n.installed.get("breaking_capacity") else ""))
        if nid in collapsed:
            hidden = len(_all_below(res, nid))
            lines.append(f"[접힘: 하위 {hidden}개]")
        for k, t in enumerate(lines):
            sheet.add(Text((x + 5.5, y + 2.0 - k * (th + 0.7)), t, height=th if k == 0 else th * 0.85,
                           layer="TEXT", ref=nid))
        ids = {nid} | (_all_below(res, nid) if nid in collapsed else set())
        st = _status(res, ids)
        sheet.add(Circle((x - 5.5, y + 3.5), 1.3, layer=_ST_LAYER[st], fill=True, ref=nid))

    # --- 표 · 표제란 ----------------------------------------------------------------
    rx = sheet.width - frame.MARGIN - frame.RIGHT_W + 2.0
    rw = frame.RIGHT_W - 4.0
    yy = sheet.height - frame.MARGIN - 2.0
    counts = {s: sum(1 for c in res.checks if c.status == s) for s in ("FAIL", "UNKNOWN", "REVIEW", "PASS")}
    yy = frame.draw_table(sheet, rx, yy, rw, "판정 요약", ["상태", "건수", "의미"], [18, 12, 70],
                          [["FAIL", str(counts["FAIL"]), "요구조건 불충족"],
                           ["UNKNOWN", str(counts["UNKNOWN"]), "필수 입력 부족 — 판정 보류"],
                           ["REVIEW", str(counts["REVIEW"]), "근거·추정·미확인 기준 확인 필요"],
                           ["PASS", str(counts["PASS"]), "검증된 요구조건 충족"]], 6)
    def _limit(c):
        if c.installed is not None:
            return fmt(c.installed, c.unit)
        return f"{c.required.op} {fmt(c.required.value, c.unit)}" if c.required else "-"

    fails = [[c.target, c.title, f"{fmt(c.actual, c.unit)} / {_limit(c)}"]
             for c in res.checks if c.status == "FAIL"]
    if fails:
        yy = frame.draw_table(sheet, rx, yy, rw, "부적합(FAIL)", ["대상", "항목", "실제 / 기준"], [22, 40, 38],
                              fails, 14)
    sname = res.design_scenario
    earth = [n for n in m.nodes.values() if n.type == "earth"]
    if earth:
        ex0 = x0 + 12.0
        ey = y0 + 8.0
        sheet.add(Text((ex0, ey + 7.0), "접지·등전위본딩", height=2.2, layer="TEXT"))
        epos = {}
        for i, en in enumerate(earth):
            ex = ex0 + 6 + i * 42.0
            epos[en.id] = (ex, ey)
            for k, w in enumerate((3.0, 2.0, 1.0)):
                sheet.add(Line((ex - w, ey - k * 1.0), (ex + w, ey - k * 1.0), layer="DEVICE", width=0.35, ref=en.id))
            sheet.add(Line((ex, ey), (ex, ey + 3.0), layer="DEVICE", width=0.35, ref=en.id))
            lab = (en.name or en.id) + (f" {en.installed['resistance']:g}Ω" if en.installed.get("resistance") else "")
            sheet.add(Text((ex + 4.0, ey + 0.5), lab, height=th * 0.85, layer="TEXT", ref=en.id))
            st = _status(res, [en.id])
            if st != "N/A":
                sheet.add(Circle((ex - 4.5, ey + 2.5), 1.0, layer=_ST_LAYER[st], fill=True, ref=en.id))
        for e in m.edges.values():
            if e.type == "bond" and e.from_id in epos and e.to_id in epos:
                (ax, ay), (bx, by) = epos[e.from_id], epos[e.to_id]
                sheet.add(Line((ax, ay + 3.0), (bx, by + 3.0), layer="DIM", width=0.3, ref=e.id))
                sheet.add(Text(((ax + bx) / 2, ay + 3.8), f"{e.id} {e.installed.get('size', 0):g}㎟", height=th * 0.8,
                               layer="DIM", anchor="middle", ref=e.id))
                st = _status(res, [e.id])
                if st != "N/A":
                    sheet.add(Circle(((ax + bx) / 2 - 8, ay + 3.0), 0.9, layer=_ST_LAYER[st], fill=True, ref=e.id))
    frame.draw_notes(sheet, rx, yy, rw, [
        f"판정 기준 운전 조건: {sname} (대상별 가장 불리한 시나리오로 판정).",
        "● 색 = 그 설비·배선의 최악 판정. 접힌 반은 내부 포함."
        + (f" 계통접지 {m.settings['earthing']}." if m.settings.get("earthing") else ""),
        "적용 기준: " + getattr(getattr(res, "rules", None), "version", "KEC"),
        "계통 구성도는 논리 연결도이며 시공 도면이 아니다(SPEC 1.3).",
    ])
    frame.draw_title_block(sheet, sheet.title, project or "EHDL", f"단선결선도 · {m.name}", sheet_no, drawn="EHDL")
    return sheet


def _all_below(res: EResult, nid: str) -> Set[str]:
    out, stack = set(), list(res.children.get(nid, []))
    while stack:
        c = stack.pop()
        out.add(c)
        stack.extend(res.children.get(c, []))
        e = res.via_edge.get(c)
        if e:
            out.add(e)
    return out


def _symbol(sheet: Sheet, n, c: Tuple[float, float], collapsed: bool) -> None:
    x, y = c
    ref = n.id
    L, D = "DEVICE", 0.35
    if n.type == "source":
        sheet.add(Circle((x, y), 4.0, layer=L, width=D, ref=ref))
        pts = [(x - 2.6 + 5.2 * i / 16, y + 1.1 * math.sin(i / 16 * 2 * math.pi)) for i in range(17)]
        sheet.add(Polyline(pts, layer=L, width=D, ref=ref))
    elif n.type == "transformer":
        sheet.add(Circle((x, y + 1.9), 2.8, layer=L, width=D, ref=ref))
        sheet.add(Circle((x, y - 1.9), 2.8, layer=L, width=D, ref=ref))
    elif n.type in ("switchboard", "panel", "bus"):
        w, h = (9.0, 5.0) if n.type != "bus" else (7.0, 2.4)
        sheet.add(Polyline([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2),
                            (x - w / 2, y + h / 2)], layer=L, closed=True, width=D * 1.5 if collapsed else D,
                           ref=ref))
        tag = {"switchboard": "MDB", "panel": "PNL", "bus": "BUS"}[n.type]
        sheet.add(Text((x, y), tag + (" +" if collapsed else ""), height=1.8, layer=L, anchor="middle",
                       valign="middle", ref=ref))
    elif n.type in ("breaker", "rcd"):
        s = 2.6
        sheet.add(Line((x, y + 5), (x, y + s), layer="WIRE", width=0.4, ref=ref))
        sheet.add(Line((x, y - s), (x, y - 5), layer="WIRE", width=0.4, ref=ref))
        sheet.add(Polyline([(x - s, y - s), (x + s, y - s), (x + s, y + s), (x - s, y + s)], layer=L,
                           closed=True, width=D, ref=ref))
        sheet.add(Line((x - s * 0.7, y - s * 0.7), (x + s * 0.7, y + s * 0.7), layer=L, width=D, ref=ref))
        sheet.add(Line((x - s * 0.7, y + s * 0.7), (x + s * 0.7, y - s * 0.7), layer=L, width=D, ref=ref))
        if n.type == "rcd":
            sheet.add(Text((x - s - 0.6, y), "RCD", height=1.5, layer=L, anchor="end", valign="middle", ref=ref))
    elif n.type == "spd":
        sheet.add(Polyline([(x - 2, y + 3), (x + 2, y + 3), (x + 2, y - 3), (x - 2, y - 3)], layer=L,
                           closed=True, width=D, ref=ref))
        sheet.add(Polyline([(x + 0.6, y + 2), (x - 0.8, y), (x + 0.8, y), (x - 0.6, y - 2)], layer=L, width=D,
                           ref=ref))
    else:   # load
        sheet.add(Circle((x, y), 3.6, layer=L, width=D, ref=ref))
        letter = _LOAD_LETTER.get(n.params.get("kind") or "", "?")
        sheet.add(Text((x, y), letter, height=3.0, layer=L, anchor="middle", valign="middle", ref=ref))
        if n.params.get("phases") == 1:
            sheet.add(Text((x, y - 6.2), str(n.params.get("phase") or "1φ"), height=1.6, layer="DIM",
                           anchor="middle", ref=ref))


def node_label(n) -> str:
    return f"{n.id} ({NODE_TYPES[n.type][0]})"
