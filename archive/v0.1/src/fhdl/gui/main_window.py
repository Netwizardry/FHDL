import os
import re
from PySide6.QtWidgets import (QMainWindow, QTextEdit, QStatusBar, 
                             QToolBar, QDockWidget, QFileDialog, QMessageBox,
                             QVBoxLayout, QWidget)
from PySide6.QtGui import QAction, QFont, QTextCursor, QColor, QTextFormat
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer

from src.fhdl.core.project_manager import ProjectManager
from src.fhdl.core.parser import FHDLParser, FHDLParserError
from src.fhdl.core.pipeline import AnalysisPipeline
from src.fhdl.core.solver import FHDLSolverError
from src.fhdl.core.report_generator import ReportGenerator
from src.fhdl.gui.editor import FHDLSyntaxHighlighter, FHDLLinter
from src.fhdl.gui.viewer import ResultViewer

class AnalysisWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str, str)
    aborted = Signal()

    def __init__(self, pipeline, text):
        super().__init__()
        self.pipeline = pipeline
        self.text = text

    def run(self):
        try:
            system = self.pipeline.run_full_analysis(
                self.text,
                progress_callback=self.progress.emit,
                interruption_check=lambda: QThread.currentThread().isInterruptionRequested()
            )
            self.finished.emit(system)
        except InterruptedError: self.aborted.emit()
        except FHDLParserError as e: self.error.emit("Syntax Error", f"Line {e.line}: {e.message}")
        except Exception as e: self.error.emit("Execution Error", str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pm = ProjectManager(); self.parser = FHDLParser()
        self.pipeline = AnalysisPipeline(self.pm, self.parser)
        self.analysis_thread = None; self.is_dirty = False
        self.lint_timer = QTimer(); self.lint_timer.setSingleShot(True)
        self.lint_timer.setInterval(500); self.lint_timer.timeout.connect(self._run_linter)
        self.setWindowTitle("Fluid-HDL v1.5 - Production Ready")
        self.resize(1200, 900); self._setup_ui(); self._setup_menu(); self._setup_toolbar()
        self.highlighter = FHDLSyntaxHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._on_text_changed)
        self.statusBar().showMessage("Ready")

    def _setup_ui(self):
        central = QWidget(); self.setCentralWidget(central); layout = QVBoxLayout(central)
        self.editor = QTextEdit(); self.editor.setFont(QFont("Consolas", 11)); layout.addWidget(self.editor, stretch=2)
        self.viewer = ResultViewer(); layout.addWidget(self.viewer, stretch=1)
        self.log_console = QTextEdit(); self.log_console.setReadOnly(True); self.log_console.setFixedHeight(120)
        self.log_console.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        dock = QDockWidget("System Log", self); dock.setWidget(self.log_console); self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self._setup_dictionary_panel()

    def _setup_dictionary_panel(self):
        help_text = QTextEdit(); help_text.setReadOnly(True)
        help_text.setHtml("<h2 style='color: #569cd6;'>📖 Dictionary</h2><p><b>node ID(x,y,z,T);</b></p>")
        dock = QDockWidget("FHDL Dictionary", self); dock.setWidget(help_text); dock.setFixedWidth(250)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _setup_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        for n, c, s in [("&New Project", self._on_new_project, None), ("&Open Project", self._on_open_project, "Ctrl+O"), ("&Save", self._on_save_fhd, "Ctrl+S")]:
            act = QAction(n, self); act.triggered.connect(c); file_menu.addAction(act)

    def _setup_toolbar(self):
        toolbar = self.addToolBar("Analysis")
        self.run_act = QAction("▶ Run", self); self.run_act.triggered.connect(self._on_run_analysis)
        self.stop_act = QAction("■ Stop", self); self.stop_act.setEnabled(False); self.stop_act.triggered.connect(self._on_stop_analysis)
        toolbar.addActions([self.run_act, self.stop_act])

    def _on_text_changed(self): self.is_dirty = True; self.lint_timer.start()

    def _run_linter(self):
        self.editor.setExtraSelections([]); errors = FHDLLinter.validate(self.editor.toPlainText())
        if errors: self.statusBar().showMessage(f"⚠ {errors[0]}", 3000)
        else: self.statusBar().showMessage("✔ Syntax OK")
def _on_run_analysis(self):
    # 감사 지적 반영: 중복 실행 가드 (더블 클릭 방지)
    if not self.run_act.isEnabled() or (self.analysis_thread and self.analysis_thread.isRunning()):
        return

    if not self.pm.current_project_path:
        QMessageBox.warning(self, "No Project", "Please open or create a project first.")
        return

    self.run_act.setEnabled(False)
    self.stop_act.setEnabled(True)
    self.editor.setReadOnly(True)
    self.log_console.clear()
    self.viewer.clear_results() # 감사 지적 반영: 결과 테이블 리셋

    self.analysis_thread = QThread()

        self.worker = AnalysisWorker(self.pipeline, self.editor.toPlainText())
        self.worker.moveToThread(self.analysis_thread)
        
        # 감사 지적 반영: 안전한 종료 및 자원 해제 시퀀스
        self.analysis_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_analysis_progress)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.aborted.connect(self._on_analysis_aborted)
        
        # 모든 종료 경로에서 스레드 중단 트리거
        self.worker.finished.connect(self.analysis_thread.quit)
        self.worker.error.connect(lambda t, m: self.analysis_thread.quit())
        self.worker.aborted.connect(self.analysis_thread.quit)
        
        # 스레드가 완전히 멈춘 뒤 객체 소멸
        self.analysis_thread.finished.connect(self._on_thread_finished)
        self.analysis_thread.finished.connect(self.worker.deleteLater)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)
        
        self.analysis_thread.start()

    def _on_analysis_progress(self, msg):
        self.log_console.append(msg)
        # 감사 지적 반영: 자동 스크롤
        self.log_console.verticalScrollBar().setValue(self.log_console.verticalScrollBar().maximum())

    def _on_stop_analysis(self):
        if self.analysis_thread and self.analysis_thread.isRunning(): self.analysis_thread.requestInterruption()

    def _on_thread_finished(self):
        # 감사 지적 반영: 잠금 해제
        self.editor.setReadOnly(False); self.run_act.setEnabled(True); self.stop_act.setEnabled(False)

    def _on_analysis_finished(self, system):
        self.viewer.update_results(system); self.is_dirty = False
        self.statusBar().showMessage("Analysis Complete", 5000)

    def _on_analysis_aborted(self): self.log_console.append("<font color='orange'>Aborted by user.</font>")

    def _on_analysis_error(self, t, m):
        self.log_console.append(f"<font color='red'><b>{t}:</b> {m}</font>")
        line_match = re.search(r'Line (\d+)', m)
        if line_match: self._highlight_error_line(int(line_match.group(1)))

    def _highlight_error_line(self, n):
        cursor = QTextCursor(self.editor.document().findBlockByLineNumber(n-1))
        self.editor.setTextCursor(cursor); sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(255, 100, 100, 50)); sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = cursor; self.editor.setExtraSelections([sel])

    def _maybe_save(self) -> bool:
        if not self.is_dirty: return True
        ret = QMessageBox.question(self, "Unsaved Changes", "Save changes?", QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        if ret == QMessageBox.Save: self._on_save_fhd(); return True
        return ret == QMessageBox.Discard

    def _on_new_project(self):
        if self._maybe_save():
            path = QFileDialog.getExistingDirectory(self, "New Project")
            if path: self.pm.init_project(path, "NewProject"); self._load_fhd_to_editor()

    def _on_open_project(self):
        if self._maybe_save():
            path = QFileDialog.getExistingDirectory(self, "Open Project")
            if path and os.path.exists(os.path.join(path, "config.fhproj")):
                self.pm.current_project_path = path; self.pm._init_db(); self._load_fhd_to_editor()

    def _on_save_fhd(self):
        if self.pm.current_project_path:
            try:
                with open(os.path.join(self.pm.current_project_path, "main.fhd"), "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self.pm.save_project(); self.is_dirty = False
                self.statusBar().showMessage("Saved.", 2000)
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def _load_fhd_to_editor(self):
        fhd_path = os.path.join(self.pm.current_project_path, "main.fhd")
        if os.path.exists(fhd_path):
            with open(fhd_path, "r", encoding="utf-8") as f: self.editor.setPlainText(f.read())
            self.is_dirty = False

    def closeEvent(self, event):
        if self._maybe_save(): event.accept()
        else: event.ignore()
