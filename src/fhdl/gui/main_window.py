"""
FHDL 메인 윈도우.
5패널 레이아웃: 프로젝트(좌) | 에디터(중좌) | 토폴로지(중우) | 결과(하좌) | 진단(하우)
"""
from __future__ import annotations

import os
from enum import auto, Enum
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow,
    QMenuBar, QMessageBox, QProgressBar, QSplitter, QStatusBar,
    QTabWidget, QVBoxLayout, QWidget,
)

from .panels.project_panel import ProjectPanel
from .panels.editor_panel import EditorPanel
from .panels.viewer_panel import TopologyViewer
from .panels.drawing_panel import DrawingPanel
from .panels.results_panel import ResultsPanel
from .panels.diagnostics_panel import DiagnosticsPanel
from .log_console import LogConsole
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

def load_theme_qss() -> str:
    """resources/styles/dark_theme.qss (없으면 빈 문자열). 시작 화면과 메인 창이 공유."""
    # src/fhdl/gui/main_window.py → 프로젝트 루트 = parents[3]
    qss_path = Path(__file__).resolve().parents[3] / "resources" / "styles" / "dark_theme.qss"
    try:
        return qss_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _changed(fields, values: dict) -> dict:
    """편집 대화상자 — 사용자가 바꾼 값만 (그대로 OK 하면 DSL 을 건드리지 않는다)."""
    init = {k: v for k, _, v in fields}
    return {k: v for k, v in values.items() if str(v).strip() != str(init.get(k, "")).strip()}


class MainWindow(QMainWindow):
    switch_domain_requested = Signal()   # 파일 → 설계 분야 전환 (시작 화면으로)
    closed = Signal()                    # 창이 실제로 닫힘 (앱 컨트롤러가 종료 판단)

    def __init__(self):
        super().__init__()
        self._state = AppState.IDLE
        self._project_dir: Optional[str] = None
        self._worker: Optional[AnalysisWorker] = None
        self._thread_pool = QThreadPool.globalInstance()
        self._entity_map = None   # 최근 해석된 EntityMap (그래프 편집용)
        self._last_result = None  # 최근 해석 결과 (저장/복원용)
        self._analyzed_source = ""  # 마지막으로 해석한 소스 (캐시 체크섬 기준)

        self.setWindowTitle("FHDL — Fluid Hardware Description Language")
        self.setMinimumSize(QSize(1200, 700))
        _app_icon = Path(__file__).resolve().parents[3] / "resources" / "icons" / "app.svg"
        if _app_icon.exists():
            self.setWindowIcon(QIcon(str(_app_icon)))
        self._apply_dark_theme()
        self._build_ui()
        self._build_menu()
        self._build_status_bar()
        self._connect_signals()
        self._set_state(AppState.IDLE)
        self._saved_source = self._editor_panel.get_source()   # 마지막 저장/열기 시점 소스 (미저장 판단)

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
        self._drawing_panel = DrawingPanel()
        # 토폴로지(편집용 그래프) / 도면(ISO·평면·정면·P&ID) 탭
        self._view_tabs = QTabWidget()
        self._view_tabs.addTab(self._viewer_panel, "토폴로지")
        self._view_tabs.addTab(self._drawing_panel, "도면")
        center_splitter.addWidget(self._editor_panel)
        center_splitter.addWidget(self._view_tabs)
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

        # 하단 작업 로그 콘솔 (작은 터미널) — 전체를 수직 분할
        self._log_console = LogConsole()
        outer_v = QSplitter(Qt.Orientation.Vertical)
        outer_v.addWidget(h_splitter)
        outer_v.addWidget(self._log_console)
        outer_v.setSizes([640, 130])
        outer_v.setStretchFactor(0, 1)
        outer_v.setCollapsible(1, True)
        self._outer_splitter = outer_v

        main_layout.addWidget(outer_v, stretch=1)
        self._log_console.info("FHDL 시작됨. 프로젝트를 열거나 새로 만드세요.")

    def _build_menu(self):
        mb = self.menuBar()

        # File 메뉴
        file_menu = mb.addMenu("파일(&F)")
        for text, shortcut, slot in [
            ("새 프로젝트(&N)", "Ctrl+Shift+N", self._project_panel._new_project),
            ("열기(&O)", "Ctrl+O", self._project_panel._open_project),
            ("저장(&S)", "Ctrl+S", self._save),
            ("도면 내보내기(&E)…", "Ctrl+Shift+E", self._drawing_panel.export_dialog),
            ("계산 보고서 내보내기(&R)…", "Ctrl+Shift+R", self.export_report_dialog),
            (None, None, None),
            ("설계 분야 전환(&D)…", "", self.switch_domain_requested.emit),
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
        # 해석 실행 — Ctrl+Enter 또는 F5
        self._run_action.setShortcuts([QKeySequence("Ctrl+Return"), QKeySequence("F5")])
        self._run_action.triggered.connect(self._run_analysis)
        run_menu.addAction(self._run_action)

        self._stop_action = QAction("중단(&S)", self)
        self._stop_action.setShortcut(QKeySequence("Ctrl+."))
        self._stop_action.triggered.connect(self._stop_analysis)
        self._stop_action.setEnabled(False)
        run_menu.addAction(self._stop_action)

        # 설정 메뉴 — 제약 조건 편집 / 부품 라이브러리 관리
        settings_menu = mb.addMenu("설정(&T)")
        constraint_action = QAction("제약 조건 편집…", self)
        constraint_action.setShortcut(QKeySequence("Ctrl+E"))
        constraint_action.triggered.connect(self._on_edit_constraints)
        settings_menu.addAction(constraint_action)
        library_action = QAction("부품 라이브러리 관리…", self)
        library_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        library_action.triggered.connect(self._on_manage_library)
        settings_menu.addAction(library_action)

        # 보기 메뉴 — 로그 콘솔
        view_menu = mb.addMenu("보기(&V)")
        toggle_log = QAction("로그 콘솔 표시/숨김", self)
        toggle_log.setShortcut(QKeySequence("Ctrl+`"))
        toggle_log.triggered.connect(self._toggle_log)
        view_menu.addAction(toggle_log)
        clear_log = QAction("로그 지우기", self)
        clear_log.setShortcut(QKeySequence("Ctrl+L"))
        clear_log.triggered.connect(lambda: self._log_console.clear())
        view_menu.addAction(clear_log)
        focus_cmd = QAction("명령 입력줄 포커스", self)
        focus_cmd.setShortcut(QKeySequence("Ctrl+;"))
        focus_cmd.triggered.connect(lambda: self._log_console.focus_input())
        view_menu.addAction(focus_cmd)

    def _toggle_log(self):
        self._log_console.setVisible(not self._log_console.isVisible())

    def _execute_command(self, command: str):
        """하단 콘솔 명령어 실행 — GUI 작업을 명령으로도 수행."""
        from ..core.command import execute_command
        res = execute_command(self._editor_panel.get_source(), command, self._entity_map)
        for m in res.messages:
            self._log(m, res.level)
        if res.action == "clear":
            self._log_console.clear()
            return
        if res.action == "save":
            self._save()
            return
        if res.action == "run":
            self._run_analysis()
            return
        if res.action == "report":
            path = res.args["path"]
            if not os.path.isabs(path) and self._project_dir:
                path = os.path.join(self._project_dir, path)
            self.export_report(path)
            return
        if res.action == "drawing":
            self._view_tabs.setCurrentWidget(self._drawing_panel)
            if "view" in res.args:
                self._drawing_panel.set_view(res.args["view"])
            else:
                path = res.args["path"]
                if not os.path.isabs(path) and self._project_dir:
                    path = os.path.join(self._project_dir, path)
                self._drawing_panel.export(path, res.args.get("views"))
            return
        if res.new_source is not None and res.new_source != self._editor_panel.get_source():
            self._editor_panel.set_source(res.new_source)
            if res.rerun:
                self._run_analysis()

    def export_report_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        start = os.path.join(self._project_dir or ".", "calc_report.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "계산 보고서 내보내기", start, "PDF (*.pdf);;HTML (*.html)")
        if path:
            self.export_report(path)

    def export_report(self, path: str) -> Optional[str]:
        """최근 해석 결과의 수리 계산 보고서 (PDF/HTML) — 해석한 소스 기준."""
        if self._last_result is None:
            self._log("보고서: 먼저 해석(F5)하세요.", "ERROR")
            return None
        from ..core.calc_report import export_calc_report
        try:
            out = export_calc_report(self._last_result, path, self._analyzed_source, self._project_name())
        except Exception as e:
            self._log(f"보고서 저장 실패: {e}", "ERROR")
            return None
        stale = self._analyzed_source != self._editor_panel.get_source()
        self._log(f"계산 보고서 → {out}" + (" (편집 후 재해석 전 결과)" if stale else ""), "WARNING" if stale else "OK")
        return out

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
        # 토폴로지 그래프 편집 → DSL 역반영 (Inverse Sync)
        self._viewer_panel.node_double_clicked.connect(self._on_node_edit)
        self._viewer_panel.pipe_double_clicked.connect(self._on_pipe_edit)
        self._viewer_panel.connection_requested.connect(self._on_connection_requested)
        # 도면 편집 → DSL 역반영 (토폴로지와 같은 핸들러 + 드래그 좌표 이동)
        self._drawing_panel.node_double_clicked.connect(self._on_node_edit)
        self._drawing_panel.pipe_double_clicked.connect(self._on_pipe_edit)
        self._drawing_panel.node_moved.connect(self._on_node_moved)
        self._drawing_panel.message.connect(self._log)
        # 하단 콘솔 명령어 입력 → 실행
        self._log_console.command_entered.connect(self._execute_command)

    # ------------------------------------------------------------------
    # 상태 기계
    # ------------------------------------------------------------------

    _STATE_LOG_LEVEL = {
        AppState.SOLVED: "OK", AppState.SAVED: "OK",
        AppState.VALIDATION_FAILED: "ERROR", AppState.CALC_FAILED: "ERROR",
        AppState.ABORTED: "WARNING",
        AppState.VALIDATING: "RUN", AppState.SOLVING: "RUN",
    }

    def _set_state(self, state: AppState, msg: str = ""):
        self._state = state
        label = _STATE_LABELS.get(state, str(state))
        color = _STATE_COLORS.get(state, "#CCC")
        self._state_label.setText(label)
        self._state_label.setStyleSheet(f"color:{color}; padding-right:10px;")
        if msg:
            self._msg_label.setText(msg)
            # 상태 메시지를 로그 콘솔에도 흘림 (DIRTY 같은 잡음은 제외)
            if state != AppState.DIRTY and hasattr(self, "_log_console"):
                self._log_console.log(msg, self._STATE_LOG_LEVEL.get(state, "INFO"))

        is_running = state in (AppState.VALIDATING, AppState.SOLVING)
        self._run_action.setEnabled(not is_running)
        self._stop_action.setEnabled(is_running)
        self._progress.setVisible(is_running)

    def _log(self, msg: str, level: str = "INFO"):
        if hasattr(self, "_log_console"):
            self._log_console.log(msg, level)

    # ------------------------------------------------------------------
    # 이벤트 핸들러
    # ------------------------------------------------------------------

    def has_unsaved_changes(self) -> bool:
        return self._editor_panel.get_source() != self._saved_source

    def confirm_discard(self, what: str = "계속") -> bool:
        """미저장 변경이 있으면 저장/버리기/취소를 묻는다. 진행해도 되면 True."""
        if not self.has_unsaved_changes():
            return True
        buttons = QMessageBox.StandardButton
        choice = buttons.Discard | buttons.Cancel
        if self._project_dir:
            choice |= buttons.Save
        ans = QMessageBox.question(
            self, "저장하지 않은 변경",
            f"편집한 FHDL 코드가 저장되지 않았습니다. {what} 전에 저장할까요?", choice,
            buttons.Save if self._project_dir else buttons.Cancel)
        if ans == buttons.Save:
            self._save()
            return not self.has_unsaved_changes()
        return ans == buttons.Discard

    def _on_project_opened(self, path: str):
        from ..core.project_io import load_project

        if not self.confirm_discard("프로젝트 열기"):          # 같은 프로젝트를 다시 열어도 미저장 편집은 확인
            return
        fhd = os.path.join(path, "main.fhd")
        if os.path.exists(fhd):
            try:
                self._editor_panel.load_file(fhd)
            except (OSError, UnicodeDecodeError) as e:
                self._log(f"main.fhd 를 읽지 못했습니다 — 프로젝트를 열지 않습니다: {e}", "ERROR")
                return
            if getattr(self._editor_panel._editor, "decoded_fallback", False):
                self._log("main.fhd 를 CP949 로 읽었습니다 — 저장하면 UTF-8 로 바뀝니다.", "WARNING")
                self._editor_panel._editor.decoded_fallback = False
        else:
            self._editor_panel.set_source("", reset_undo=True)   # 이전 프로젝트 코드가 남지 않게
            self._log("main.fhd 가 없는 폴더 — 빈 코드로 시작합니다.", "WARNING")
        # 이전 프로젝트의 해석·결과 정리 (진행 중 해석은 버린다)
        if self._worker:
            self._worker.cancel()
            self._worker = None
        self._last_result = None
        self._entity_map = None
        self._analyzed_source = ""
        self._drawing_panel.update_from_result(None, "")
        self._project_dir = path
        self._saved_source = self._editor_panel.get_source()
        self.setWindowTitle(f"FHDL — {Path(path).name}")

        # 캐시(state.db) 가 현재 소스와 일치하면 결과를 재계산 없이 복원
        try:
            loaded = load_project(path)
        except Exception as e:                              # 손상된 state.db 등 — 캐시 없이 연다
            self._log(f"결과 캐시를 읽지 못했습니다(재해석 필요): {e}", "WARNING")
            loaded = None
        if loaded is not None and loaded.cache_valid and loaded.result is not None:
            self._restore_result(loaded.result)
            self._set_state(AppState.SOLVED, f"프로젝트 열림(결과 복원): {Path(path).name}")
        else:
            self._results_panel.clear()
            self._diag_panel.clear()
            self._viewer_panel.clear()
            msg = "프로젝트 열림 — 코드 변경됨, 재해석 필요" if os.path.exists(
                os.path.join(path, "state.db")) else f"프로젝트 열림: {Path(path).name}"
            self._set_state(AppState.IDLE, msg)

    def _restore_result(self, r):
        """재계산 없이 state.db 캐시 결과로 패널을 복원한다."""
        self._last_result = r
        self._analyzed_source = self._editor_panel.get_source()
        self._entity_map = r.entity_map
        self._diag_panel.update_diagnostics(r.diagnostics)
        self._results_panel.update_result(r)
        if r.entity_map:
            self._viewer_panel.update_from_result(r)
            self._drawing_panel.update_from_result(r, self._project_name())

    def _on_text_changed(self, text: str):
        if self._state not in (AppState.VALIDATING, AppState.SOLVING) and text != self._analyzed_source:
            self._set_state(AppState.DIRTY)
        self._lint(text)

    def _lint(self, text: str):
        """실시간 검사 (편집 300ms 뒤): 구문·의미 진단만 즉시 — 해석 결과는 건드리지 않는다.

        진단 패널 = 지금 소스의 SYN/SEM + 직전 해석의 네트워크·계산 진단(다음 해석 전까지 유지)."""
        from ..core.parser import FHDLParser
        from ..core.semantic import SemanticAnalyzer
        if not text.strip():
            return
        try:
            ast, diags = FHDLParser().parse(text)
            if not any(d.is_blocking for d in diags):
                diags = diags + SemanticAnalyzer().analyze(ast)[1]
        except Exception as e:                     # 검사기는 편집을 막지 않는다
            self._log(f"실시간 검사 오류: {e}", "WARNING")
            return
        prev = [d for d in (self._last_result.diagnostics if self._last_result else [])
                if not d.code.startswith(("SYN", "SEM"))]
        self._lint_diags = diags
        self._diag_panel.update_diagnostics(diags + prev)
        self._editor_panel.set_error_lines({d.source_span.line: d.code for d in diags
                                            if d.source_span.line > 0 and d.severity in ("ERROR", "FATAL")})
        n_err = sum(1 for d in diags if d.is_blocking)
        n_wrn = sum(1 for d in diags if d.severity == "WARNING")
        self._msg_label.setText(f"실시간 검사 — 오류 {n_err} · 경고 {n_wrn}" if (n_err or n_wrn)
                                else "실시간 검사 — 문제 없음")

    def _on_diagnostic_selected(self, code: str, line: int):
        if line > 0:
            self._editor_panel.jump_to_line(line)

    # ------------------------------------------------------------------
    # 그래프 편집 → DSL 역반영 (Inverse Sync)
    # ------------------------------------------------------------------

    def _node_type_of(self, nid: str) -> str:
        em = self._entity_map
        if not em:
            return "junction"
        if nid in em.tanks:
            return "tank"
        if nid in em.pumps:
            return "pump"
        if nid in em.terminals:
            return "terminal"
        return "junction"

    def _node_fields(self, ent, ntype: str):
        """엔티티 현재값 → 편집 다이얼로그 필드 [(dsl_key, 라벨, 표시값)]."""
        f = [
            ("z", "고도 z", f"{ent.elevation:g}m"),
            ("x", "x 좌표", f"{ent.x:g}" if getattr(ent, "has_xy", False) else ""),   # 자동 배치 노드를 (0,0)에 고정하지 않게
            ("y", "y 좌표", f"{ent.y:g}" if getattr(ent, "has_xy", False) else ""),
        ]
        if ntype == "tank":
            if ent.volume != float("inf"):
                f.append(("volume", "용량", f"{ent.volume:g}m3"))
            f.append(("level_max", "최고수위", f"{ent.level_max:g}m"))
        elif ntype == "terminal":
            f.append(("required_q", "요구유량", f"{ent.required_q * 60000:g}lpm"))
            if ent.required_p > 0:
                f.append(("required_p", "요구압력", f"{ent.required_p / 1e6:g}MPa"))
            else:
                f.append(("required_p", "요구압력", ""))
        elif ntype == "pump":
            head_v = f"{ent.head.value:g}m" if ent.head.mode == "MANUAL" else ""
            flow_v = f"{ent.flow.value * 60000:g}lpm" if ent.flow.mode == "MANUAL" else ""
            f.append(("head", "양정(head)", head_v))
            f.append(("flow", "유량(flow)", flow_v))
            f.append(("npshr", "NPSHr", f"{ent.npshr:g}m"))
            f.append(("efficiency", "효율", f"{ent.efficiency:g}"))
        return f

    def _pipe_fields(self, pipe):
        """배관 현재값 → 편집 다이얼로그 필드."""
        dia = "auto" if pipe.diameter.mode == "AUTO" else f"{pipe.diameter.value * 1000:g}mm"
        return [
            ("length", "길이", f"{pipe.length:g}m"),
            ("diameter", "관경(auto 가능)", dia),
            ("material", "자재", pipe.material),
            ("k_factor", "수동 K", f"{pipe.k_explicit:g}" if pipe.k_explicit else ""),   # 부속 K 는 fittings 로 따로
            ("fittings", "피팅 [name*N]", pipe.fittings),
        ]

    def _on_node_edit(self, node_id: str):
        em = self._entity_map
        if not em:
            return
        ent = em.get_node_entity(node_id)
        if ent is None:
            return
        from .panels.editor_panel import NodeEditDialog
        from ..core.dsl_editor import set_node_attributes, remove_node

        ntype = self._node_type_of(node_id)
        fields = self._node_fields(ent, ntype)
        dlg = NodeEditDialog(node_id, ntype, fields, self, allow_delete=True)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        src = self._editor_panel.get_source()
        if dlg.delete_requested:
            ans = QMessageBox.question(
                self, "노드 삭제",
                f"노드 '{node_id}' 와 연결된 배관·connect 를 삭제할까요?")
            if ans != QMessageBox.StandardButton.Yes:
                return
            new_src = remove_node(src, node_id)
            self._log(f"노드 '{node_id}' 삭제 (연결 배관·connect 포함)", "WARNING")
        else:
            new_src = set_node_attributes(src, node_id, _changed(fields, dlg.get_values()))
            if new_src == src:
                return
            self._log(f"노드 '{node_id}' 속성 수정", "INFO")
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _project_name(self) -> str:
        return os.path.basename(self._project_dir.rstrip("/\\")) if self._project_dir else ""

    def _on_node_moved(self, node_id: str, attrs: dict):
        """도면(평면도·정면도) 노드 드래그 → DSL 좌표 갱신 후 재해석."""
        from ..core.dsl_editor import set_node_attributes
        new_src = set_node_attributes(self._editor_panel.get_source(), node_id, attrs)
        self._log(f"노드 '{node_id}' 좌표 이동: " + ", ".join(f"{k}={v}" for k, v in attrs.items()), "INFO")
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _on_pipe_edit(self, pipe_id: str):
        em = self._entity_map
        if not em or pipe_id not in em.pipes:
            return
        from .panels.editor_panel import NodeEditDialog
        from ..core.dsl_editor import set_pipe_attributes

        pipe = em.pipes[pipe_id]
        fields = self._pipe_fields(pipe)
        dlg = NodeEditDialog(pipe_id, "pipe", fields, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        src = self._editor_panel.get_source()
        new_src = set_pipe_attributes(src, pipe_id, _changed(fields, dlg.get_values()))
        if new_src == src:
            return
        self._log(f"배관 '{pipe_id}' 속성 수정", "INFO")
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _on_manage_library(self):
        from .library_dialog import LibraryManagerDialog
        from ..db.library_db import LibraryDB, default_library_path
        db = LibraryDB(default_library_path())
        self._log(f"부품 라이브러리 관리 열기 — {default_library_path()} (재질·부속 K·관경 표가 해석에 쓰입니다)", "INFO")
        try:
            LibraryManagerDialog(db, self).exec()
        finally:
            db.close()

    def _on_edit_constraints(self):
        from .panels.editor_panel import NodeEditDialog
        from ..core.dsl_editor import set_constraint_attributes

        c = self._entity_map.constraints if self._entity_map else None
        vmin = f"{c.velocity_min:g}m/s" if c else "0.3m/s"
        vmax = f"{c.velocity_max:g}m/s" if c else "2.5m/s"
        sfh = f"{c.safety_factor_head:g}" if c else "1.1"
        sfn = f"{c.safety_factor_npsh:g}" if c else "1.1"
        fields = [
            ("velocity_min", "최소 유속(m/s)", vmin),
            ("velocity_max", "최대 유속(m/s)", vmax),
            ("safety_factor_head", "양정 안전율", sfh),
            ("safety_factor_npsh", "NPSH 안전율", sfn),
        ]
        dlg = NodeEditDialog("제약 조건", "constraint", fields, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_src = set_constraint_attributes(
            self._editor_panel.get_source(), dlg.get_values())
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _on_connection_requested(self, from_id: str, to_id: str):
        from ..core.dsl_editor import add_link, remove_link, has_link

        src = self._editor_panel.get_source()
        if has_link(src, from_id, to_id):
            ans = QMessageBox.question(
                self, "연결 삭제",
                f"{from_id} → {to_id} 연결(pipe/connect)을 삭제할까요?")
            if ans != QMessageBox.StandardButton.Yes:
                return
            new_src = remove_link(src, from_id, to_id)
            self._log(f"연결 삭제: {from_id} → {to_id}", "WARNING")
        else:
            new_src = add_link(src, from_id, to_id,
                               length=self._link_length(from_id, to_id))
            self._log(f"연결 추가: {from_id} → {to_id}", "INFO")
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _link_length(self, from_id: str, to_id: str) -> str:
        """두 노드 좌표 거리로 기본 배관 길이 추정 (없으면 10m)."""
        em = self._entity_map
        a = em.get_node_entity(from_id) if em else None
        b = em.get_node_entity(to_id) if em else None
        if a is not None and b is not None:
            import math
            d = math.hypot(getattr(a, "x", 0) - getattr(b, "x", 0),
                           getattr(a, "y", 0) - getattr(b, "y", 0))
            if d > 0:
                return f"{d:.1f}m"
        return "10m"

    def _save(self, _path: str = ""):
        if not self._project_dir:
            return
        from ..core.project_io import save_project
        self._set_state(AppState.SAVING)
        try:
            # main.fhd 원자적 저장 + project.fhproj 갱신 + (있으면)결과 캐시
            save_project(self._project_dir, self._editor_panel.get_source(),
                         result=self._last_result, name=Path(self._project_dir).name,
                         result_source=self._analyzed_source)   # 결과는 그 결과를 낸 소스의 체크섬으로
            self._saved_source = self._editor_panel.get_source()
            self._set_state(AppState.SAVED, "저장 완료")
        except Exception as e:
            self._set_state(AppState.DIRTY, f"저장 실패: {e}")

    # ------------------------------------------------------------------
    # 분석 실행
    # ------------------------------------------------------------------

    def _run_analysis(self):
        if self._state in (AppState.VALIDATING, AppState.SOLVING):
            return
        if self._worker is not None and self._worker._cancel:     # 취소 중인 해석이 끝나기 전엔 새로 시작하지 않는다
            self._log("이전 해석을 취소하는 중입니다 — 잠시 뒤 다시 실행하세요.", "WARNING")
            return

        source = self._editor_panel.get_source()
        if not source.strip():
            self._set_state(AppState.VALIDATION_FAILED, "빈 코드입니다.")
            return
        self._analyzed_source = source   # 캐시 체크섬 기준

        output_dir = os.path.join(self._project_dir or ".", "outputs") if self._project_dir else "outputs"
        os.makedirs(output_dir, exist_ok=True)

        self._set_state(AppState.VALIDATING, "분석 시작...")
        self._results_panel.clear()
        self._diag_panel.clear()
        self._viewer_panel.clear()

        w = AnalysisWorker(source, output_dir)
        self._worker = w
        self._live_workers = getattr(self, "_live_workers", set()) | {w}   # 끝날 때까지 강한 참조(신호 유실 방지)
        # 신호마다 보낸 워커를 함께 넘겨, 지금 워커가 아닌(취소·다른 프로젝트) 결과는 버린다
        w.signals.status_update.connect(lambda msg, w=w: self._on_status_update(msg, w))
        w.signals.finished.connect(lambda r, w=w: self._on_analysis_finished(r, w))
        w.signals.error.connect(lambda e, w=w: self._on_analysis_error(e, w))
        self._thread_pool.start(w)

    def _stop_analysis(self):
        if self._worker:
            self._worker.cancel()
            self._set_state(AppState.ABORTED, "분석 취소 중...")

    def _on_status_update(self, msg: str, worker=None):
        if worker is not None and worker is not self._worker:
            return
        if self._state == AppState.ABORTED:
            return
        self._set_state(AppState.SOLVING, msg)

    def _on_analysis_finished(self, result, worker=None):
        from ..core.models import AnalysisResult
        r: AnalysisResult = result
        getattr(self, "_live_workers", set()).discard(worker)
        if worker is not None and worker is not self._worker:
            return                                   # 이전(취소·다른 프로젝트) 해석의 결과
        worker, self._worker = self._worker, None
        if r.status == "CANCELLED" or (worker is not None and worker._cancel):
            # 중단된 해석의 부분 결과는 표시·캐시하지 않는다 — 편집 상태로 복귀
            self._log("해석을 중단했습니다 — 부분 결과는 폐기했습니다.", "WARNING")
            self._set_state(AppState.DIRTY, "분석 취소됨 — 결과 폐기")
            return

        # 진단 패널 업데이트
        self._diag_panel.update_diagnostics(r.diagnostics)

        # 진단을 로그 콘솔에 출력 (오류/경고)
        for d in r.diagnostics:
            if d.severity in ("ERROR", "FATAL"):
                loc = f" (L{d.source_span.line})" if d.source_span.line > 0 else ""
                self._log(f"[{d.code}] {d.message}{loc}", "ERROR")
        for d in r.diagnostics:
            if d.severity == "WARNING":
                self._log(f"[{d.code}] {d.message}", "WARNING")

        # 에디터 에러 마커 갱신
        error_lines = {}
        for d in r.diagnostics:
            if d.source_span.line > 0 and d.severity in ("ERROR", "FATAL"):
                error_lines[d.source_span.line] = d.code
        self._editor_panel.set_error_lines(error_lines)

        if r.status == "FAILED":
            # 이전 결과를 남기면 보고서·도면이 새 코드와 옛 숫자를 짝지어 낸다
            self._last_result = None
            self._drawing_panel.update_from_result(None, self._project_name())
            self._set_state(AppState.VALIDATION_FAILED,
                            f"오류 {len(r.errors)}건 발견")
            return

        # 결과 패널 업데이트
        self._results_panel.update_result(r)

        # 토폴로지 뷰어 업데이트
        self._entity_map = r.entity_map
        self._last_result = r
        if r.entity_map:
            self._viewer_panel.update_from_result(r)
            self._drawing_panel.update_from_result(r, self._project_name())

        # 결과 캐시 저장 (state.db) — main.fhd 는 보존(명시적 저장 시에만 기록)
        if self._project_dir:
            try:
                from ..core.project_io import save_project
                save_project(self._project_dir, self._analyzed_source, r,
                             write_fhd=False)
            except Exception as e:
                self._log(f"결과 캐시(state.db) 저장 실패 — 다음에 열 때 다시 해석해야 합니다: {e}", "WARNING")

        s = r.summary
        self._log(
            f"해석 결과 — 총유량 {s.total_flow * 60000:.1f} L/min · "
            f"권장 펌프양정 {s.recommended_pump_head:.2f} m · "
            f"노드 {len(r.node_results)} · 배관 {len(r.pipe_results)}",
            "OK" if not r.errors else "WARNING")

        err_cnt = len(r.errors)
        wrn_cnt = len(r.warnings)
        msg = f"완료 — 오류: {err_cnt}, 경고: {wrn_cnt}"
        state = AppState.CALC_FAILED if err_cnt else AppState.SOLVED
        self._set_state(state, msg)

    def _on_analysis_error(self, err: str, worker=None):
        getattr(self, "_live_workers", set()).discard(worker)
        if worker is not None and worker is not self._worker:
            return
        self._worker = None
        self._log(f"내부 오류: {err}", "ERROR")
        self._set_state(AppState.CALC_FAILED, f"내부 오류: {err}")

    # ------------------------------------------------------------------
    # 테마
    # ------------------------------------------------------------------

    # 외부 QSS 로드 실패 시 사용할 최소 인라인 폴백 테마
    _FALLBACK_QSS = """
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
    """

    def closeEvent(self, event):
        if not self.confirm_discard("닫기"):
            event.ignore()
            return
        if self._worker:
            self._worker.cancel()
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()

    def _apply_dark_theme(self):
        """resources/styles/dark_theme.qss 를 로드해 전역 테마 적용 (실패 시 폴백)."""
        # src/fhdl/gui/main_window.py → 프로젝트 루트 = parents[3]
        self.setStyleSheet(load_theme_qss() or self._FALLBACK_QSS)
