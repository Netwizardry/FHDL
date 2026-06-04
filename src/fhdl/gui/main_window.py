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
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow,
    QMenuBar, QMessageBox, QProgressBar, QSplitter, QStatusBar,
    QVBoxLayout, QWidget,
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
        self._entity_map = None   # 최근 해석된 EntityMap (그래프 편집용)
        self._last_result = None  # 최근 해석 결과 (저장/복원용)
        self._analyzed_source = ""  # 마지막으로 해석한 소스 (캐시 체크섬 기준)

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

        # 설정 메뉴 — 제약 조건 편집
        settings_menu = mb.addMenu("설정(&T)")
        constraint_action = QAction("제약 조건 편집…", self)
        constraint_action.triggered.connect(self._on_edit_constraints)
        settings_menu.addAction(constraint_action)

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
        from ..core.project_io import load_project

        self._project_dir = path
        fhd = os.path.join(path, "main.fhd")
        if os.path.exists(fhd):
            self._editor_panel.load_file(fhd)
        self.setWindowTitle(f"FHDL — {Path(path).name}")

        # 캐시(state.db) 가 현재 소스와 일치하면 결과를 재계산 없이 복원
        loaded = load_project(path)
        if loaded.cache_valid and loaded.result is not None:
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

    def _on_text_changed(self, text: str):
        if self._state not in (AppState.VALIDATING, AppState.SOLVING):
            self._set_state(AppState.DIRTY)

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
            ("x", "x 좌표", f"{getattr(ent, 'x', 0):g}"),
            ("y", "y 좌표", f"{getattr(ent, 'y', 0):g}"),
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
            ("k_factor", "수동 K", f"{pipe.manual_k:g}"),
            ("fittings", "피팅 [name*N]", ""),
        ]

    def _on_node_edit(self, node_id: str):
        em = self._entity_map
        if not em:
            return
        ent = em.get_node_entity(node_id)
        if ent is None:
            return
        from .panels.editor_panel import NodeEditDialog
        from ..core.dsl_editor import set_node_attributes

        ntype = self._node_type_of(node_id)
        dlg = NodeEditDialog(node_id, ntype, self._node_fields(ent, ntype), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_src = set_node_attributes(
            self._editor_panel.get_source(), node_id, dlg.get_values())
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _on_pipe_edit(self, pipe_id: str):
        em = self._entity_map
        if not em or pipe_id not in em.pipes:
            return
        from .panels.editor_panel import NodeEditDialog
        from ..core.dsl_editor import set_pipe_attributes

        pipe = em.pipes[pipe_id]
        dlg = NodeEditDialog(pipe_id, "pipe", self._pipe_fields(pipe), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_src = set_pipe_attributes(
            self._editor_panel.get_source(), pipe_id, dlg.get_values())
        self._editor_panel.set_source(new_src)
        self._run_analysis()

    def _on_edit_constraints(self):
        from .panels.editor_panel import NodeEditDialog
        from ..core.dsl_editor import set_constraint_attributes

        c = self._entity_map.constraints if self._entity_map else None
        vmin = f"{c.velocity_min:g}m" if c else "0.3m"
        vmax = f"{c.velocity_max:g}m" if c else "2.5m"
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
        else:
            new_src = add_link(src, from_id, to_id,
                               length=self._link_length(from_id, to_id))
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
                         result=self._last_result, name=Path(self._project_dir).name)
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
        self._analyzed_source = source   # 캐시 체크섬 기준

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
        self._entity_map = r.entity_map
        self._last_result = r
        if r.entity_map:
            self._viewer_panel.update_from_result(r)

        # 결과 캐시 저장 (state.db) — main.fhd 는 보존(명시적 저장 시에만 기록)
        if self._project_dir:
            try:
                from ..core.project_io import save_project
                save_project(self._project_dir, self._analyzed_source, r,
                             write_fhd=False)
            except Exception:
                pass

        err_cnt = len(r.errors)
        wrn_cnt = len(r.warnings)
        msg = f"완료 — 오류: {err_cnt}, 경고: {wrn_cnt}"
        state = AppState.CALC_FAILED if err_cnt else AppState.SOLVED
        self._set_state(state, msg)

    def _on_analysis_error(self, err: str):
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

    def _apply_dark_theme(self):
        """resources/styles/dark_theme.qss 를 로드해 전역 테마 적용 (실패 시 폴백)."""
        # src/fhdl/gui/main_window.py → 프로젝트 루트 = parents[3]
        qss_path = Path(__file__).resolve().parents[3] / "resources" / "styles" / "dark_theme.qss"
        try:
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        except OSError:
            self.setStyleSheet(self._FALLBACK_QSS)
