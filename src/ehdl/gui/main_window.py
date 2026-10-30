"""EHDL 메인 창 — FHDL 과 같은 구성(DSL 에디터 · 그래프 · 결과 · 진단 · 하단 콘솔) + 노드 상세.

  ┌ 에디터(DSL) ┬ 계통 구성도(그래프 에디터) ┬ 노드 상세 ┐
  ├ 결과(판정·설비·배선·시나리오, 설계/검산 모드) ┬ 진단 ┤
  └ 작업 로그 + 명령 입력 ┘
진실원은 DSL(main.ehd) — 그래프·명령·대화상자 편집은 모두 DSL 을 고친 뒤 재해석한다(SPEC 원칙 8).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QDialog, QFileDialog, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from fhdl.gui.log_console import LogConsole
from fhdl.gui.main_window import load_theme_qss
from fhdl.gui.panels.diagnostics_panel import DiagnosticsPanel
from fhdl.gui.panels.editor_panel import NodeEditDialog

from ..command import execute_command
from ..dsl_editor import add_block, block_type, remove_block, set_attrs
from ..kb import KB
from ..language import EDGE_ATTRS, NODE_ATTRS, NODE_TYPES
from ..parser import parse
from ..pipeline import analyze
from .editor import SAMPLE, AddBlockDialog, EHDLEditorPanel, GrammarDialog
from .panels import EResultsPanel, NodeDetailPanel, SystemGraphPanel

_ROOT = Path(__file__).resolve().parents[3]
DEMO = _ROOT / "projects" / "ehdl_demo" / "main.ehd"


class EHDLMainWindow(QMainWindow):
    switch_domain_requested = Signal()
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.path: Optional[str] = None
        self.result = None
        self.changes = []
        self._baseline_src = None
        self._prev_result = None
        self._saved_src = ""
        self._saved_result = None
        self._analyzed = None
        self.history = []
        self._dirty = False
        self.setWindowTitle("EHDL — 전력계통 설계·검산")
        self.setMinimumSize(QSize(1200, 720))
        icon = _ROOT / "resources" / "icons" / "ehdl.svg"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.setStyleSheet(load_theme_qss())
        self._build_ui()
        self._build_menu()
        self.editor.set_source(SAMPLE, reset_undo=True)
        self._run()
        self._mark_saved()

    # ------------------------------------------------------------------
    def _build_ui(self):
        self.editor = EHDLEditorPanel()
        self.graph = SystemGraphPanel()
        self.detail = NodeDetailPanel()
        self.detail.kb = KB(os.environ.get("EHDL_KB", str(_ROOT / "data" / "ehdl_kb.db")))
        self.results = EResultsPanel()
        self.diags = DiagnosticsPanel()
        self.console = LogConsole()
        top = QSplitter(Qt.Orientation.Horizontal)
        for w in (self.editor, self.graph, self.detail):
            top.addWidget(w)
        top.setSizes([420, 760, 380])
        bottom = QSplitter(Qt.Orientation.Horizontal)
        bottom.addWidget(self.results)
        bottom.addWidget(self.diags)
        bottom.setSizes([1100, 420])
        mid = QSplitter(Qt.Orientation.Vertical)
        mid.addWidget(top)
        mid.addWidget(bottom)
        mid.setSizes([520, 260])
        outer = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(mid)
        outer.addWidget(self.console)
        outer.setSizes([780, 130])
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(outer)
        self.setCentralWidget(central)

        self.editor.text_changed.connect(lambda _t: self._on_edited())
        self.editor.run_requested.connect(lambda _t: self._run())
        self.graph.entity_selected.connect(self._select)
        self.graph.edit_requested.connect(self._edit)
        self.graph.delete_requested.connect(self._delete)
        self.graph.link_requested.connect(self._link)
        self.graph.why_requested.connect(lambda t: self._command(f"why {t}"))
        self.graph.message.connect(self.console.log)
        self.results.target_selected.connect(lambda t: (self._select(t), self.graph.select(t, emit=False)))
        self.diags.diagnostic_selected.connect(lambda _c, line: self.editor.jump_to_line(line) if line > 0 else None)
        self.console.command_entered.connect(self._command)
        self.console._input.setPlaceholderText(
            "명령어 입력 (help)  예: add load M2 parent=PNL1 rating=7.5kW / set PNL1 rated_current=125A / why PNL1 / report r.pdf")
        self.console.info("EHDL 시작 — 파일 → 데모 열기로 예제 계통을 볼 수 있습니다. 명령은 help.")

    def _build_menu(self):
        mb = self.menuBar()
        f = mb.addMenu("파일(&F)")
        for text, key, slot in [("새 계통(&N)", "Ctrl+Shift+N", self._new), ("열기(&O)…", "Ctrl+O", self._open),
                                ("데모 열기", "", lambda: self.open_file(str(DEMO))),
                                ("저장(&S)", "Ctrl+S", self._save), ("다른 이름으로 저장…", "Ctrl+Shift+S", self._save_as),
                                (None, None, None),
                                ("DXF 가져오기(&I)…", "Ctrl+I", self._import_dialog),
                                ("계통 구성도 내보내기…", "Ctrl+Shift+E", self.graph.export_dialog),
                                ("검산 보고서…", "Ctrl+Shift+R", self._report_dialog),
                                (None, None, None),
                                ("설계 분야 전환(&D)…", "", self.switch_domain_requested.emit),
                                ("종료(&Q)", "Ctrl+Q", self.close)]:
            if text is None:
                f.addSeparator()
                continue
            a = QAction(text, self)
            if key:
                a.setShortcut(QKeySequence(key))
            a.triggered.connect(slot)
            f.addAction(a)
        r = mb.addMenu("실행(&R)")
        a = QAction("해석 실행", self)
        a.setShortcuts([QKeySequence("F5"), QKeySequence("Ctrl+Return")])
        a.triggered.connect(self._run)
        r.addAction(a)
        v = mb.addMenu("보기(&V)")
        v.addAction("모든 반 펼치기", lambda: (self.graph.collapsed.clear(), self.graph.update_from_result(self.result, self._project())))
        v.addAction("로그 콘솔 표시/숨김", lambda: self.console.setVisible(not self.console.isVisible()))
        h = mb.addMenu("도움말(&H)")
        h.addAction("EHDL 문법", lambda: GrammarDialog(self).exec())

    def closeEvent(self, event):
        if self._dirty and QMessageBox.question(self, "저장 안 됨", "저장하지 않은 변경이 있습니다. 닫을까요?") \
                != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()

    # ------------------------------------------------------------------
    def _project(self) -> str:
        return Path(self.path).parent.name if self.path else "untitled"

    def _on_edited(self):
        src = self.editor.get_source()
        if src == self._analyzed:                     # 프로그램이 넣은 소스(열기·새로·가져오기)의 지연 신호 — 편집 아님
            return
        self._dirty = src != self._saved_src
        self._update_title()
        self._run()

    def _reset_session(self):
        """다른 계통으로 바꿀 때 — 이전 계통의 결과·변경 영향·선택이 넘어오지 않게."""
        self.result = None
        self.changes = []
        self._prev_result = None
        self._baseline_src = None
        self.results.show_impact([])
        self.graph.collapsed.clear()
        self.graph._selected = None

    def _update_title(self):
        name = Path(self.path).name if self.path else "untitled.ehd"
        self.editor._file_label.setText(name + (" *" if self._dirty else ""))
        self.setWindowTitle(f"EHDL — {name}{' *' if self._dirty else ''}")

    def _run(self):
        src = self.editor.get_source()
        prev = self.result if (self.result is not None and self.result.status == "OK") else None
        self.result = analyze(src)
        self._analyzed = src
        r = self.result
        self.diags.update_diagnostics(r.diagnostics)
        self.editor.set_error_lines({d.source_span.line: d.code for d in r.diagnostics
                                     if d.is_blocking and d.source_span.line > 0})
        if r.status == "FAILED":
            self.console.log(f"해석 실패 — 오류 {len(r.errors)}건 (진단 패널)", "ERROR")
            return
        self.results.update_result(r)
        if r.model is not None:                       # 지운 설비가 접힘·선택 상태로 남지 않게
            self.graph.collapsed &= set(r.model.nodes)
            if getattr(self.graph, "_selected", None) and self.graph._selected not in r.model.nodes \
                    and self.graph._selected not in r.model.edges:
                self.graph._selected = None
        self.graph.update_from_result(r, self._project())
        from ..impact import diff, summary
        if prev is not None and self._baseline_src != src:
            self.changes = diff(prev, r)
            self.results.show_impact(self.changes)
            if self.changes:
                self.console.log(summary(self.changes),
                                 "WARNING" if any(c["change"] == "worse" for c in self.changes) else "INFO")
        self._baseline_src = src
        self._prev_result = prev
        counts = {s: sum(1 for c in r.checks if c.status == s) for s in ("FAIL", "UNKNOWN", "REVIEW", "PASS")}
        self.console.log("해석 — " + " · ".join(f"{k} {v}" for k, v in counts.items()),
                         "ERROR" if counts["FAIL"] else ("WARNING" if counts["UNKNOWN"] else "OK"))
        if self.graph._selected:
            self.detail.show_target(r, self.graph._selected)

    def _select(self, tid: str):
        self.detail.show_target(self.result, tid)

    def _set_source(self, src: str):
        self.editor.set_source(src)
        self._on_edited()

    # --- 그래프 편집 (Inverse Sync) ---------------------------------------
    def _edit(self, tid: str):
        src = self.editor.get_source()
        t = block_type(src, tid)
        if not t:
            return
        blocks, _ = parse(src)
        raw = next((b.raw for b in blocks if b.id == tid), {})
        spec = NODE_ATTRS.get(t) or EDGE_ATTRS.get(t) or {}
        keys = ["name"] + (["parent", "feed"] if t in NODE_TYPES else []) + list(spec) + ["justification"]
        fields = [(k, (spec[k].label if k in spec else {"name": "이름", "parent": "소속 반", "feed": "전원 측",
                                                         "justification": "선정 근거"}[k]), raw.get(k, "").strip('"'))
                  for k in dict.fromkeys(keys)]
        dlg = NodeEditDialog(tid, t, fields, self, allow_delete=True)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.delete_requested:
            self._delete(tid)
            return
        vals = dlg.get_values()
        attrs = {}
        for k, v in vals.items():
            old = raw.get(k, "").strip('"')
            if v != old:
                attrs[k] = v if v else None
        if attrs:
            self._set_source(set_attrs(src, tid, attrs))
            self.console.log(f"'{tid}' 수정: " + ", ".join(f"{k}={v}" for k, v in attrs.items()), "INFO")

    def _delete(self, tid: str):
        if QMessageBox.question(self, "삭제", f"'{tid}' 와 연결 배선을 삭제할까요?") == QMessageBox.StandardButton.Yes:
            self._set_source(remove_block(self.editor.get_source(), tid))
            self.console.log(f"'{tid}' 삭제", "WARNING")

    def _link(self, up: str):
        dlg = AddBlockDialog(self)
        dlg._type.setCurrentIndex(dlg._type.findData("load"))
        n = self.result.model.nodes.get(up) if self.result and self.result.model else None
        key = "parent" if n is not None and n.type in ("switchboard", "panel") else "feed"
        dlg._edits[key].setText(up)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            t, bid, attrs = dlg.block()
            if bid:
                self._set_source(add_block(self.editor.get_source(), t, bid, attrs))
                self.console.log(f"{t} '{bid}' 추가 ({key} = {up})", "OK")

    # --- 명령 콘솔 ---------------------------------------------------------
    def _command(self, cmd: str):
        res = execute_command(self.editor.get_source(), cmd, self.result)
        for msg in res.messages:
            if msg:
                self.console.log(msg, res.level)
        if res.action == "clear":
            self.console.clear()
        elif res.action == "run":
            self._run()
        elif res.action == "save":
            self._save()
        elif res.action == "drawing":
            if res.args.get("path"):
                self.graph.export(self._abs(res.args["path"]))
        elif res.action == "report":
            self.export_report(self._abs(res.args["path"]))
        elif res.action == "import":
            self.import_dxf(self._abs(res.args["path"]))
        elif res.action == "history":
            from ..history import describe, for_target
            tid = res.args.get("id")
            if tid:
                rows = for_target(self.history, tid)
                self.console.log(f"{tid} 변경 이력 {len(rows)}건", "INFO")
                for t, d in rows[-20:]:
                    self.console.log(f"  {t} {d}", "INFO")
            else:
                self.console.log(f"변경 이력 {len(self.history)}건 (저장 시점별)", "INFO")
                for e in self.history[-10:]:
                    self.console.log(f"  {e['time']} " + ("; ".join(describe(x) for x in e['edits']) or "-")
                                     + (f" — {e['verdict']}" if e.get('verdict') else ""), "INFO")
        elif res.action == "impact":
            from ..impact import summary
            self.console.log(summary(self.changes), "INFO")
            for d in self.changes[:20]:
                self.console.log(f"  {d['target']} {d['title']}: {d['old']} → {d['new']}", "INFO")
        if res.new_source is not None and res.new_source != self.editor.get_source():
            self._set_source(res.new_source)

    def _abs(self, p: str) -> str:
        if os.path.isabs(p):
            return p
        base = os.path.dirname(self.path) if self.path else os.path.expanduser("~")   # 저장 전 계통은 홈 폴더 기준
        return os.path.join(base, p)

    # --- 파일 · 보고서 -------------------------------------------------------
    def _new(self):
        self.path = None
        self._reset_session()
        self.editor.set_source(SAMPLE, reset_undo=True)
        self._dirty = False
        self._update_title()
        self._run()
        self._mark_saved()

    def _open(self):
        p, _ = QFileDialog.getOpenFileName(self, "EHDL 열기", str(_ROOT / "projects"), "EHDL (*.ehd)")
        if p:
            self.open_file(p)

    def open_file(self, p: str):
        try:
            text = Path(p).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = Path(p).read_text(encoding="cp949")       # 한글 Windows 메모장 저장본
                self.console.log(f"{Path(p).name}: UTF-8 이 아니라 CP949 로 읽었습니다(저장하면 UTF-8).", "WARNING")
            except (UnicodeDecodeError, OSError) as e:
                self.console.log(f"열기 실패: {p} — {e}", "ERROR")
                return False
        except OSError as e:
            self.console.log(f"열기 실패: {p} — {e}", "ERROR")
            return False
        self.path = p                       # 읽기에 성공한 뒤에만 — 실패한 파일을 저장으로 덮어쓰지 않게
        self._reset_session()
        self.editor.set_source(text, reset_undo=True)
        self._dirty = False
        self._update_title()
        self._run()
        self._mark_saved()
        self.console.log(f"열기: {p}" + (f" — 변경 이력 {len(self.history)}건" if self.history else ""), "INFO")
        return True

    def _mark_saved(self):
        """저장/열기 시점 — 다음 저장의 변경 이력 기준."""
        from ..history import load
        self._saved_src = self.editor.get_source()
        self._saved_result = self.result
        self.history = load(self.path)
        self.detail.history = self.history
        self.results.show_history(self.history)

    def _save(self):
        if not self.path:
            return self._save_as()
        src = self.editor.get_source()
        Path(self.path).write_text(src, encoding="utf-8")
        self._dirty = False
        self._update_title()
        from ..history import append, make_entry
        if self._saved_result is not None and self.result is not None and self.editor.get_source() != self._analyzed:
            self._run()                                    # 저장 내용 기준 판정으로 이력 남김
        entry = make_entry(self._saved_src, src, self._saved_result, self.result)
        if entry is not None:
            try:
                append(self.path, entry)
            except OSError as e:
                self.console.log(f"변경 이력 기록 실패: {e}", "WARNING")
        self._mark_saved()
        self.console.log(f"저장: {self.path}" + (f" — 변경 {len(entry['edits'])}건 이력 기록 ({entry['verdict']})"
                                                if entry and entry["edits"] else ""), "OK")

    def _save_as(self):
        p, _ = QFileDialog.getSaveFileName(self, "다른 이름으로 저장", str(_ROOT / "projects" / "main.ehd"), "EHDL (*.ehd)")
        if p:
            self.path = p if p.endswith(".ehd") else p + ".ehd"
            self._save()

    def _import_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "DXF 가져오기 (부하 일람표·CABLE SCHEDULE·단선결선도)",
                                           str(Path.home()), "DXF (*.dxf)")
        if p:
            self.import_dxf(p)

    def import_dxf(self, path: str):
        """DXF 전기 설계도 → 새 EHDL 계통 (저장 전). 가져오기 보고서는 로그로."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        if self._dirty and QMessageBox.question(self, "저장 안 됨", "저장하지 않은 변경이 있습니다. 버리고 가져올까요?") \
                != QMessageBox.StandardButton.Yes:
            return None
        from ..dxf_import import import_dxf
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = import_dxf(path)
        except Exception as e:
            self.console.log(f"DXF 가져오기 실패: {e}", "ERROR")
            return None
        finally:
            QApplication.restoreOverrideCursor()
        self.path = None
        self._reset_session()
        self.editor.set_source(res.source, reset_undo=True)
        self._dirty = True
        self._update_title()
        self.graph.collapsed = set()
        self._run()
        if self.result is not None and self.result.model is not None:   # 회로가 많은 반은 접어서 보여 준다
            self.graph.collapsed = {k for k, v in self.result.children.items()
                                    if self.result.model.nodes[k].type == "panel" and len(v) > 6}
            self.graph.update_from_result(self.result, self._project())
        self._mark_saved()
        self._dirty = True
        self.console.log("DXF 가져오기 — " + res.summary() + f" ({Path(path).name})", "OK")
        for w_ in res.warnings:
            self.console.log("  도면 불일치: " + w_, "WARNING")
        for n_ in res.notes:
            self.console.log("  참고: " + n_, "INFO")
        for q_ in res.questions:
            self.console.log("  확인할 입력: " + q_, "INFO")
        self.console.log("다른 이름으로 저장(Ctrl+Shift+S) 하면 .ehd 프로젝트가 됩니다.", "INFO")
        return res

    def _report_dialog(self):
        base = os.path.join(os.path.dirname(self.path) if self.path else str(Path.home()), f"{self._project()}_report")
        p, flt = QFileDialog.getSaveFileName(self, "검산 보고서", base,
                                             "PDF (*.pdf);;HTML (*.html);;CSV 표별 (*.csv);;JSON (*.json)")
        if p:
            ext = flt.split("*.")[-1].rstrip(")")
            self.export_report(p if p.lower().endswith("." + ext) else p + "." + ext)

    def export_report(self, path: str) -> str:
        from ..report import export_report
        if self.result is None or self.result.model is None or self.result.status != "OK":
            self.console.log("보고서: 먼저 해석이 성공해야 합니다.", "WARNING")
            return ""
        try:
            out = export_report(self.result, path, self._project(), baseline=self._prev_result, history=self.history)
        except Exception as e:
            self.console.log(f"보고서 실패: {e}", "ERROR")
            return ""
        self.console.log(f"보고서 저장: {out}", "OK")
        return out
