"""EHDL GUI 패널 — 계통 그래프(단선결선도, FHDL DrawingPanel 재사용) · 노드 상세 · 결과 표."""
from __future__ import annotations

import html
import os
from typing import List, Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMenu, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout,
    QWidget,
)

from fhdl.gui.panels.drawing_panel import DrawingPanel

from ..drawing import build_sld
from ..language import CONTAINER_TYPES, GLOSSARY, NODE_ATTRS, NODE_TYPES, EDGE_ATTRS, EDGE_TYPES
from ..model import EResult
from ..units import fmt

ST_COLOR = {"FAIL": "#E74C3C", "UNKNOWN": "#E67E22", "REVIEW": "#D4AC0D", "PASS": "#4EC9B0", "N/A": "#8B949E"}


# ---------------------------------------------------------------------------
# 계통 그래프 (단선결선도)
# ---------------------------------------------------------------------------

class SystemGraphPanel(DrawingPanel):
    """단선결선도를 그래프 에디터로 — 클릭 선택, 더블클릭 편집, 오른쪽 클릭 메뉴(접기/펼치기·근거·연결·삭제)."""
    VIEW_ITEMS = [("sld", "계통 구성도 (단선결선도)")]
    DRAG_VIEWS = ()
    EXPORT_FILTERS = "PDF (*.pdf);;SVG (*.svg);;DXF (*.dxf);;PNG (*.png)"
    VIEW_LABEL = "보기:"

    edit_requested = Signal(str)          # 설비·배선 속성 편집
    delete_requested = Signal(str)
    link_requested = Signal(str)          # 이 설비 아래에 배선 추가
    why_requested = Signal(str)

    def __init__(self, parent=None):
        self.collapsed: Set[str] = set()
        super().__init__(parent)
        self.node_double_clicked.connect(self.edit_requested)
        self.pipe_double_clicked.connect(self.edit_requested)
        self._hint.setText("클릭 선택 · 더블클릭 편집 · 오른쪽 클릭: 접기/펼치기·근거·연결·삭제")

    def has_result(self) -> bool:
        return self._result is not None and getattr(self._result, "model", None) is not None

    def build_sheet(self, view: str):
        return build_sld(self._result if self.has_result() else None, self._project, self.collapsed)

    def _rebuild(self, keep_zoom: bool = False) -> None:
        super()._rebuild(keep_zoom)
        self._hint.setText("클릭 선택 · 더블클릭 편집 · 오른쪽 클릭: 접기/펼치기·근거·연결·삭제")

    def _is_node(self, ref: str) -> bool:
        return self.has_result() and ref in self._result.model.nodes

    def toggle_collapse(self, nid: str) -> None:
        self.collapsed ^= {nid}
        self._rebuild(keep_zoom=True)

    def context_menu(self, ref: str, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction("속성 편집…", lambda: self.edit_requested.emit(ref))
        menu.addAction("판정 근거 보기", lambda: self.why_requested.emit(ref))
        if self._is_node(ref):
            n = self._result.model.nodes[ref]
            if n.type in CONTAINER_TYPES:
                menu.addAction("펼치기" if ref in self.collapsed else "접기", lambda: self.toggle_collapse(ref))
            if n.type != "load":
                menu.addAction("아래에 배선·부하 연결…", lambda: self.link_requested.emit(ref))
        menu.addSeparator()
        menu.addAction("삭제", lambda: self.delete_requested.emit(ref))
        menu.exec(global_pos)

    def export_file(self, path: str, views) -> str:
        ext = os.path.splitext(path)[1].lower()
        sheet = build_sld(self._result, self._project, self.collapsed)
        if ext == ".svg":
            from fhdl.drawing.export_svg import save_svg
            save_svg(sheet, path)
        elif ext == ".dxf":
            from fhdl.drawing.export_dxf import save_dxf
            save_dxf(sheet, path)
        elif ext == ".pdf":
            from fhdl.drawing.render_qt import save_pdf
            save_pdf(sheet, path)
        elif ext == ".png":
            from fhdl.drawing.render_qt import save_png
            save_png(sheet, path)
        else:
            raise ValueError(f"지원하지 않는 형식: {ext}")
        return path


# ---------------------------------------------------------------------------
# 노드 상세 (SPEC 7.2 — 7개 항목 + 산정 근거 추적)
# ---------------------------------------------------------------------------

class NodeDetailPanel(QTextBrowser):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setStyleSheet("QTextBrowser { background:#1E1E1E; color:#D4D4D4; border:none; }")
        self.kb = None
        self.show_placeholder()

    def show_placeholder(self):
        self.setHtml("<p style='color:#8B949E'>계통도나 표에서 설비를 선택하면 쉬운 설명·입력값·요구조건·"
                     "실제 규격·판정·선정 근거·확인 질문이 여기에 나옵니다.</p>")

    def show_target(self, res: Optional[EResult], tid: str) -> None:
        if res is None or res.model is None or not tid:
            self.show_placeholder()
            return
        m = res.model
        is_node = tid in m.nodes
        obj = m.nodes.get(tid) or m.edges.get(tid)
        if obj is None:
            self.show_placeholder()
            return
        kind_name, desc = (NODE_TYPES if is_node else EDGE_TYPES)[obj.type]
        spec = (NODE_ATTRS if is_node else EDGE_ATTRS)[obj.type]
        checks = res.checks_for(tid)
        status = res.node_status(tid)
        h = [f"<h2 style='margin:0'>{html.escape(getattr(obj, 'name', '') or tid)} "
             f"<span style='color:#8B949E;font-size:11px'>{tid} · {kind_name}</span> "
             f"<span style='color:{ST_COLOR[status]}'>● {status}</span></h2>"]
        # 1. 쉬운 설명
        h.append(f"<h3>1. 이 설비는</h3><p>{html.escape(desc)}</p>")
        terms = [t for t in GLOSSARY if any(t in (c.title + c.explanation) for c in checks)]
        if terms:
            h.append("<p style='color:#8B949E'>" + "<br>".join(f"<b>{t}</b>: {html.escape(GLOSSARY[t])}" for t in terms)
                     + "</p>")
        # 2. 입력값 · 4. 실제 규격
        def rows(d, role):
            out = []
            for k, v in d.items():
                a = spec.get(k)
                lab = a.label if a else k
                if isinstance(v, float):
                    kind = a.kind if a else ""
                    unit = {"voltage": "V", "current": "A", "current_ka": "A", "current_ma": "A", "power": "W",
                            "apparent": "VA", "length": "m", "area": "㎟"}.get(kind, "")
                    if kind == "power_or_apparent":
                        unit = "VA" if obj.unit_kinds.get(k) == "apparent" else "W"
                    if kind == "ratio":
                        v = f"{v:g}" if v > 0.01 else f"{v * 100:g}%"
                    elif kind == "reactance":
                        v = f"{v * 1000:g} mΩ/m"
                    elif unit == "㎟":
                        v = f"{v:g} ㎟"
                    elif unit:
                        v = fmt(v, unit, 2 if unit == "A" else 1)
                out.append(f"<tr><td>{html.escape(lab)}</td><td><code>{k}</code></td><td>{html.escape(str(v))}</td></tr>")
            return "".join(out) or f"<tr><td colspan=3 style='color:#8B949E'>({role} 없음)</td></tr>"
        h.append("<h3>2. 입력값</h3><table cellpadding=2>" + rows(obj.params, "입력") + "</table>")
        # 3. 요구조건
        req = [c for c in checks if c.required]
        h.append("<h3>3. 계산된 요구조건</h3><ul>" + ("".join(
            f"<li>{html.escape(c.required.text())} <span style='color:#8B949E'>"
            + html.escape(" · ".join(x for x in ((c.evidence.scenario + " 조건") if c.evidence.scenario else "",
                                                  "추정" if c.estimated else "") if x))
            + "</span></li>" for c in req) or "<li>-</li>") + "</ul>")
        h.append("<h3>4. 실제 설계 규격</h3><table cellpadding=2>" + rows(obj.installed, "실제 규격") + "</table>")
        # 5. 판정
        h.append("<h3>5. 적합성 판정</h3>")
        for c in checks:
            if c.kind == "sizing_rationale":
                continue
            h.append(f"<p><b style='color:{ST_COLOR[c.status]}'>{c.status}</b> {html.escape(c.title)} — "
                     f"{html.escape(c.explanation)}</p>")
            ev = c.evidence
            meta = []
            if ev.formula:
                meta.append(f"식: {html.escape(ev.formula)}")
            if ev.rule:
                meta.append(f"기준: {html.escape(ev.rule.title)} — {html.escape(ev.rule.citation or ev.rule.clause)}"
                            + ("" if ev.rule.verified else " <b>[원문 미확인]</b>"))
                txt = self._kb_excerpt(ev.rule)
                if txt:
                    meta.append(f"<span style='color:#6A9955'>원문: {html.escape(txt)}</span>")
            for x in ev.defaults:
                meta.append(f"기준 기본값: {html.escape(x)}")
            for x in ev.assumptions:
                meta.append(f"<span style='color:#D4AC0D'>추정: {html.escape(x)}</span>")
            if c.missing:
                meta.append("<span style='color:#E67E22'>필요 입력: " + html.escape(", ".join(c.missing)) + "</span>")
            if meta:
                h.append("<p style='margin-left:12px;color:#8B949E;font-size:11px'>" + "<br>".join(meta) + "</p>")
        # 6. 선정 근거
        rat = [c for c in checks if c.kind == "sizing_rationale"]
        just = getattr(obj, "justification", "")
        h.append("<h3>6. 선정 근거</h3><p>" + (html.escape(just) if just else "<span style='color:#8B949E'>(입력 없음)</span>")
                 + "</p>" + "".join(f"<p><b style='color:{ST_COLOR[c.status]}'>{c.status}</b> "
                                    f"{html.escape(c.explanation)}</p>" for c in rat))
        # 7. 질문
        qs = [q for c in checks for q in c.questions]
        h.append("<h3>7. 설계자에게 확인할 질문</h3><ol>" + ("".join(f"<li>{html.escape(q)}</li>" for q in qs)
                                                   or "<li style='color:#8B949E'>없음</li>") + "</ol>")
        # 산정 근거 추적 (SPEC 8)
        if is_node:
            sr = res.scenarios.get(res.design_scenario)
            kids = res.children.get(tid, [])
            if sr and kids:
                r = sr.nodes[tid]
                h.append(f"<h3>산정 근거 추적 ({res.design_scenario})</h3><p>{tid}: "
                         f"{fmt(r.current, 'A')} · {fmt(r.P, 'W')} · {fmt(r.S, 'VA')}</p><ul>")
                for k in kids:
                    kr = sr.nodes[k]
                    h.append(f"<li>{k}: {fmt(kr.current, 'A')} · {fmt(kr.P, 'W')}"
                             + (" — <span style='color:#E67E22'>입력 부족 포함</span>" if kr.incomplete else "") + "</li>")
                h.append("</ul>")
        hist = getattr(self, "history", None)
        if hist:
            from ..history import for_target
            rows = for_target(hist, tid)
            if rows:
                h.append("<h3>변경 이력 (사용자 수정 — SPEC 8)</h3><ul>" + "".join(
                    f"<li>{html.escape(t.replace('T', ' '))} — {html.escape(d)}</li>" for t, d in reversed(rows[-8:]))
                         + "</ul>")
        self.setHtml("".join(h))

    def _kb_excerpt(self, rule) -> str:
        if self.kb is None or not getattr(self.kb, "available", False):
            return ""
        rows = self.kb.rule_sources(rule.id)
        return (rows[0]["quote"][:220] + "…") if rows else ""


# ---------------------------------------------------------------------------
# 결과 표 (설비·배선·검산·시나리오) + 설계/검산 모드
# ---------------------------------------------------------------------------

class EResultsPanel(QWidget):
    target_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._res: Optional[EResult] = None
        self.mode = QComboBox()
        self.mode.addItem("검산 모드 (요구 vs 실제)", "check")
        self.mode.addItem("기본설계 모드 (요구규격)", "design")
        self.mode.currentIndexChanged.connect(lambda _: self.update_result(self._res))
        self.summary = QLabel("")
        top = QHBoxLayout()
        top.addWidget(self.mode)
        top.addWidget(self.summary, 1)
        self.tabs = QTabWidget()
        (self.t_nodes, self.t_edges, self.t_checks, self.t_sc, self.t_fault, self.t_earth, self.t_mixed,
         self.t_impact, self.t_history) = (QTableWidget() for _ in range(9))
        for t, name in ((self.t_checks, "판정"), (self.t_nodes, "설비"), (self.t_edges, "배선"), (self.t_sc, "시나리오"),
                        (self.t_fault, "단락·기동"), (self.t_earth, "접지·수전"), (self.t_mixed, "혼합(기존/신규)"),
                        (self.t_impact, "변경 영향"), (self.t_history, "변경 이력")):
            t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            t.cellClicked.connect(lambda r, c, tbl=t: self._clicked(tbl, r))
            self.tabs.addTab(t, name)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(top)
        lay.addWidget(self.tabs)

    def _clicked(self, tbl, row):
        it = tbl.item(row, 0)
        if it:
            self.target_selected.emit(it.text())

    @staticmethod
    def _fill(tbl: QTableWidget, cols: List[str], rows: List[list], status_col: Optional[int] = None):
        tbl.clear()
        tbl.setColumnCount(len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                it = QTableWidgetItem(str(v))
                if j == status_col and str(v) in ST_COLOR:
                    it.setForeground(QColor(ST_COLOR[str(v)]))
                tbl.setItem(i, j, it)
        tbl.resizeColumnsToContents()

    def update_result(self, res: Optional[EResult]) -> None:
        self._res = res
        if res is None or res.model is None or not res.scenarios:
            for t in (self.t_nodes, self.t_edges, self.t_checks, self.t_sc, self.t_fault, self.t_earth, self.t_mixed):
                t.setRowCount(0)
            self.summary.setText("")
            return
        m = res.model
        design = self.mode.currentData() == "design"
        sr = res.scenarios[res.design_scenario]
        counts = {s: sum(1 for c in res.checks if c.status == s) for s in ("FAIL", "UNKNOWN", "REVIEW", "PASS")}
        self.summary.setText("  ".join(f"<span style='color:{ST_COLOR[k]}'>{k} {v}</span>" for k, v in counts.items())
                             + f"  · 판정 기준: {res.design_scenario}")
        rows = []
        for c in res.checks:
            if design and c.kind == "sizing_rationale":
                continue
            if design:
                rows.append([c.target, c.title, c.required.text() if c.required else "-",
                             "UNKNOWN" if c.status == "UNKNOWN" else "", c.evidence.scenario])
            else:
                rows.append([c.target, c.title, c.required.text() if c.required else "-",
                             fmt(c.installed, c.unit) if c.installed is not None else "-",
                             f"{c.utilization * 100:.0f}%" if c.utilization is not None else "-", c.status])
        if design:
            self._fill(self.t_checks, ["ID", "항목", "요구조건", "정보", "운전 조건"], rows, 3)
        else:
            self._fill(self.t_checks, ["ID", "항목", "요구", "실제 규격", "사용률", "판정"], rows, 5)
        nrows = []
        for nid in res.order:
            n, r = m.nodes[nid], sr.nodes[nid]
            nrows.append([nid, NODE_TYPES[n.type][0], fmt(r.P, "W"), fmt(r.Q, "var"), fmt(r.S, "VA"),
                          fmt(r.current, "A") if r.current is not None else "-",
                          f"{r.vdrop_pct:.2f}%" if r.vdrop_pct is not None else "-", res.node_status(nid)])
        self._fill(self.t_nodes, ["ID", "종류", "P", "Q", "S", "최대 상전류", "누적 전압강하", "상태"], nrows, 7)
        erows = []
        req = {c.target: c for c in res.checks if c.kind == "cable_size" and c.actual is not None}
        for eid, e in m.edges.items():
            r = sr.nodes.get(e.to_id)
            cs = req.get(eid)
            erows.append([eid, f"{e.from_id}→{e.to_id}", e.installed.get("material") or "-",
                          f"{e.installed['size']:g}㎟" if e.installed.get("size") else "-",
                          (f"≥ {cs.actual:g}㎟ ({cs.required.quantity.split(': ')[-1].rstrip(')')})" if cs else "-"),
                          f"{e.params['length']:g}m" if e.params.get("length") is not None else "-",
                          fmt(r.current, "A") if r and r.current is not None else "-", res.node_status(eid)])
        self._fill(self.t_edges, ["ID", "구간", "재질", "단면적", "요구 단면적 (지배 조건)", "길이", "전류", "상태"],
                   erows, 7)
        scols = ["ID"] + list(res.scenarios)
        srows = []
        for nid in res.order:
            srows.append([nid] + [fmt(s.nodes[nid].current, "A") if s.nodes[nid].current is not None else "-"
                                  for s in res.scenarios.values()])
        self._fill(self.t_sc, scols, srows)
        frows = []
        for nid in res.order:
            s = res.sc.get(nid)
            n = m.nodes[nid]
            st = [c.status for c in res.checks_for(nid) if c.kind in ("breaking_capacity", "selectivity",
                                                                      "motor_start_vd", "motor_start_protection")]
            frows.append([nid, NODE_TYPES[n.type][0],
                          f"{s.ik_max / 1000:.2f} kA" if s and s.ik_max else ("입력 부족" if s and s.missing else "-"),
                          f"{s.ik_min / 1000:.2f} kA" if s and s.ik_min else "-",
                          f"{s.motor_contrib / 1000:.2f} kA" if s and s.motor_contrib else "-",
                          f"{n.installed['breaking_capacity'] / 1000:g} kA" if n.installed.get("breaking_capacity") else "-",
                          min(st, key=lambda x: ("FAIL", "UNKNOWN", "REVIEW", "PASS", "N/A").index(x)) if st else ""])
        self._fill(self.t_fault, ["ID", "종류", "Ik'' 최대", "Ik'' 최소", "전동기 기여", "차단용량", "판정"], frows, 6)
        from ..report import tables as _tables
        tb = _tables(res)
        erows = [r for r in tb["EARTH"]["rows"]] + [["(수전)", k, v, "", "", ""] for k, v in tb["SUPPLY"]["rows"]]
        self._fill(self.t_earth, tb["EARTH"]["columns"], erows, 4)
        self._fill(self.t_mixed, tb["MIXED"]["columns"], tb["MIXED"]["rows"], 6)

    def show_history(self, entries) -> None:
        from ..history import table
        t = table(entries)
        self._fill(self.t_history, t["columns"], t["rows"])

    def show_impact(self, changes) -> None:
        from ..report import impact_table
        t = impact_table(changes)
        self._fill(self.t_impact, t["columns"], t["rows"], 2)
