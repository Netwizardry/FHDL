"""
FHDL 메인 윈도우.
5패널 레이아웃: 프로젝트(좌) | 에디터(중좌) | 토폴로지(중우) | 결과(하좌) | 진단(하우)
"""
from __future__ import annotations

import os
from enum import auto, Enum
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow,
    QMenuBar, QProgressBar, QSplitter, QStatusBar, QVBoxLayout, QWidget,
)

from .panels.project_panel import ProjectPanel
from .panels.editor_panel import EditorPanel
from .panels.viewer_panel import TopologyViewer
from .panels.results_panel import ResultsPanel
from .panels.diagnostics_panel import DiagnosticsPanel
from .worker import AnalysisWorker


# ---------------------------------------------------------------------------
# 상태 기계
# ---------------------------------------------------------------------------

class AppState(Enum):
    IDLE = auto()
    DIRTY = auto()
    VALIDATING = auto()
    SOLVING = auto()
    SOLVED = auto()
    VALIDATION_FAILED = auto()
    CALC_FAILED = auto()
    SAVING = auto()
    SAVED = auto()
    ABORTED = auto()


_STATE_LABELS = {
    AppState.IDLE:             "대기",
    AppState.DIRTY:            "수정됨",
    AppState.VALIDATING:       "검증 중...",
    AppState.SOLVING:          "계산 중...",
    AppState.SOLVED:           "계산 완료",
    AppState.VALIDATION_FAILED: "검증 실패",
    AppState.CALC_FAILED:      "계산 실패",
    AppState.SAVING:           "저장 중...",
    AppState.SAVED:            "저장됨",
    AppState.ABORTED:          "취소됨",
}

_STATE_COLORS = {
    AppState.SOLVED:  "#4EC9B0",
    AppState.DIRTY:   "#D4AC0D",
    AppState.VALIDATION_FAILED: "#E74C3C",
    AppState.CALC_FAILED: "#E74C3C",
}


# ---------------------------------------------------------------------------
# 메인 윈도우
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._state = AppState.IDLE
        self._project_dir: Optional[str] = None
        self._worker: Optional[AnalysisWorker] = None
        self._thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle("FHDL — Fluid Hardware Description Language")
        self.setMinimumSize(QSize(1200, 700))
        self._apply_dark_theme()
        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._connect_signals()
        self._set_state(AppState.IDLE)

    # ------------------------------------------------------------------
    # UI 구성
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 메인 수평 분할
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 좌측: 프로젝트 패널
        self._project_panel = ProjectPanel()
        self._project_panel.setMinimumWidth(160)
        self._project_panel.setMaximumWidth(280)
        h_splitter.addWidget(self._project_panel)

        # 중앙: 에디터 + 토폴로지 수평 분할
        center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._editor_panel = EditorPanel()
        self._viewer_panel = TopologyViewer()
        center_splitter.addWidget(self._editor_panel)
        center_splitter.addWidget(self._viewer_panel)
        center_splitter.setSizes([500, 400])

        # 하단: 결과 + 진단 수평 분할
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._results_panel = ResultsPanel()
        self._diag_panel = DiagnosticsPanel()
        bottom_splitter.addWidget(self._results_panel)
        bottom_splitter.addWidget(self._diag_panel)
        bottom_splitter.setSizes([550, 350])

        # 수직 분할 (에디터/뷰어 vs 결과/진단)
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(center_splitter)
        v_splitter.addWidget(bottom_splitter)
        v_splitter.setSizes([420, 220])

        h_splitter.addWidget(v_splitter)
        h_splitter.setSizes([200, 900])
        h_splitter.setChildrenCollapsible(False)

        main_layout.addWidget(h_splitter, stretch=1)

    def _build_menu(self):
        mb = self.menuBar()

        # File 메뉴
        file_menu = mb.addMenu("파일(&F)")
        for text, shortcut, slot in [
            ("새 프로젝트(&N)", "Ctrl+Shift+N", self._project_panel._new_project),
            ("열기(&O)", "Ctrl+O", self._project_panel._open_project),
            ("저장(&S)", "Ctrl+S", self._save),
            (None, None, None),
            ("종료(&Q)", "Ctrl+Q", self.close),
        ]:
            if text is None:
                file_menu.addSeparator()
            else:
                act = QAction(text, self)
                if shortcut:
                    act.setShortcut(QKeySequence(shortcut))
                act.triggered.connect(slot)
                file_menu.addAction(act)

        # Run 메뉴
        run_menu = mb.addMenu("실행(&R)")
        self._run_action = QAction("해석 실행(&R)", self)
        self._run_action.setShortcut(QKeySequence("Ctrl+Return"))
        self._run_action.triggered.connect(self._run_analysis)
        run_menu.addAction(self._run_action)

        self._stop_action = QAction("중단(&S)", self)
        self._stop_action.setShortcut(QKeySequence("Ctrl+."))
        self._stop_action.triggered.connect(self._stop_analysis)
        self._stop_action.setEnabled(False)
        run_menu.addAction(self._stop_action)

    def _build_status_bar(self):
        sb = self.statusBar()
        self._state_label = QLabel("대기")
        self._state_label.setStyleSheet("color:#4EC9B0; padding-right:10px;")
        sb.addPermanentWidget(self._state_label)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(120)
        self._progress.setFixedHeight(14)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)

        self._msg_label = QLabel("")
        sb.addWidget(self._msg_label)

    # ------------------------------------------------------------------
    # 신호 연결
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self._project_panel.project_opened.connect(self._on_project_opened)
        self._project_panel.project_saved.connect(self._save)
        self._editor_panel.text_changed.connect(self._on_text_changed)
        self._editor_panel.run_requested.connect(lambda _: self._run_analysis())
        self._diag_panel.diagnostic_selected.connect(self._on_diagnostic_selected)

    # ------------------------------------------------------------------
    # 상태 기계
    # ------------------------------------------------------------------

    def _set_state(self, state: AppState, msg: str = ""):
        self._state = state
        label = _STATE_LABELS.get(state, str(state))
        color = _STATE_COLORS.get(state, "#CCC")
        self._state_label.setText(label)
        self._state_label.setStyleSheet(f"color:{color}; padding-right:10px;")
        if msg:
            self._msg_label.setText(msg)

        is_running = state in (AppState.VALIDATING, AppState.SOLVING)
        self._run_action.setEnabled(not is_running)
        self._stop_action.setEnabled(is_running)
        self._progress.setVisible(is_running)

    # ------------------------------------------------------------------
    # 이벤트 핸들러
    # ------------------------------------------------------------------

    def _on_project_opened(self, path: str):
        self._project_dir = path
        fhd = os.path.join(path, "main.fhd")
        if os.path.exists(fhd):
            self._editor_panel.load_file(fhd)
        self.setWindowTitle(f"FHDL — {Path(path).name}")
        self._set_state(AppState.IDLE, f"프로젝트 열림: {path}")

    def _on_text_changed(self, text: str):
        if self._state not in (AppState.VALIDATING, AppState.SOLVING):
            self._set_state(AppState.DIRTY)

    def _on_diagnostic_selected(self, code: str, line: int):
        if line > 0:
            self._editor_panel.jump_to_line(line)

    def _save(self, _path: str = ""):
        if not self._project_dir:
            return
        fhd = os.path.join(self._project_dir, "main.fhd")
        self._set_state(AppState.SAVING)
        try:
            self._editor_panel.save_file(fhd)
            self._set_state(AppState.SAVED, "저장 완료")
        except Exception as e:
            self._set_state(AppState.DIRTY, f"저장 실패: {e}")

    # ------------------------------------------------------------------
    # 분석 실행
    # ------------------------------------------------------------------

    def _run_analysis(self):
        if self._state in (AppState.VALIDATING, AppState.SOLVING):
            return

        source = self._editor_panel.get_source()
        if not source.strip():
            self._set_state(AppState.VALIDATION_FAILED, "빈 코드입니다.")
            return

        output_dir = os.path.join(self._project_dir or ".", "outputs") if self._project_dir else "outputs"
        os.makedirs(output_dir, exist_ok=True)

        self._set_state(AppState.VALIDATING, "분석 시작...")
        self._results_panel.clear()
        self._diag_panel.clear()
        self._viewer_panel.clear()

        self._worker = AnalysisWorker(source, output_dir)
        self._worker.signals.status_update.connect(self._on_status_update)
        self._worker.signals.finished.connect(self._on_analysis_finished)
        self._worker.signals.error.connect(self._on_analysis_error)
        self._thread_pool.start(self._worker)

    def _stop_analysis(self):
        if self._worker:
            self._worker.cancel()
        self._set_state(AppState.ABORTED, "분석 취소됨")

    def _on_status_update(self, msg: str):
        self._set_state(AppState.SOLVING, msg)

    def _on_analysis_finished(self, result):
        from ..core.models import AnalysisResult
        r: AnalysisResult = result

        # 진단 패널 업데이트
        self._diag_panel.update_diagnostics(r.diagnostics)

        # 에디터 에러 마커 갱신
        error_lines = {}
        for d in r.diagnostics:
            if d.source_span.line > 0 and d.severity in ("ERROR", "FATAL"):
                error_lines[d.source_span.line] = d.code
        self._editor_panel.set_error_lines(error_lines)

        if r.status == "FAILED":
            self._set_state(AppState.VALIDATION_FAILED,
                            f"오류 {len(r.errors)}건 발견")
            return

        # 결과 패널 업데이트
        self._results_panel.update_result(r)

        # 토폴로지 뷰어 업데이트
        if r.entity_map:
            self._viewer_panel.update_from_result(r)

        # DB 저장
        if self._project_dir:
            self._save_to_db(r)

        err_cnt = len(r.errors)
        wrn_cnt = len(r.warnings)
        msg = f"완료 — 오류: {err_cnt}, 경고: {wrn_cnt}"
        state = AppState.CALC_FAILED if err_cnt else AppState.SOLVED
        self._set_state(state, msg)

    def _on_analysis_error(self, err: str):
        self._set_state(AppState.CALC_FAILED, f"내부 오류: {err}")

    def _save_to_db(self, result):
        try:
            db_path = os.path.join(self._project_dir, "state.db")
            from ..db.project_db import ProjectDB
            db = ProjectDB(db_path)
            db.save_analysis_result(result)
            db.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 테마
    # ------------------------------------------------------------------

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background:#1E1E1E; color:#D4D4D4; }
            QMenuBar { background:#252526; color:#CCC; }
            QMenuBar::item:selected { background:#094771; }
            QMenu { background:#252526; color:#CCC; border:1px solid #444; }
            QMenu::item:selected { background:#094771; }
            QSplitter::handle { background:#333; }
            QStatusBar { background:#007ACC; color:#FFF; }
            QLabel { color:#CCC; }
            QProgressBar { background:#333; border:none; height:8px; }
            QProgressBar::chunk { background:#007ACC; }
        """)
