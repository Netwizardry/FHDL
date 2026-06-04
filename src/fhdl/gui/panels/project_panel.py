"""프로젝트 선택 패널 (좌측 사이드바)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


_RECENT_FILE = Path.home() / ".fhdl_recent.json"
_MAX_RECENT = 10


def _load_recent() -> List[str]:
    try:
        if _RECENT_FILE.exists():
            return json.loads(_RECENT_FILE.read_text())
    except Exception:
        pass
    return []


def _save_recent(paths: List[str]):
    try:
        _RECENT_FILE.write_text(json.dumps(paths[:_MAX_RECENT]))
    except Exception:
        pass


class ProjectPanel(QWidget):
    project_opened = Signal(str)   # 프로젝트 디렉토리 경로
    project_saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent: List[str] = _load_recent()
        self._current_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 제목
        title = QLabel("프로젝트")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #CCC;")
        layout.addWidget(title)

        # 최근 프로젝트 목록
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget { background:#1E1E1E; border:1px solid #333; color:#CCC; }
            QListWidget::item:selected { background:#094771; }
            QListWidget::item:hover { background:#2A2D2E; }
        """)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list, stretch=1)

        # 버튼 그룹
        for label, slot in [
            ("새 프로젝트", self._new_project),
            ("열기...", self._open_project),
            ("저장", self._save_project),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton { background:#3C3C3C; color:#CCC; border:1px solid #555;
                              padding:4px; border-radius:3px; }
                QPushButton:hover { background:#4C4C4C; }
                QPushButton:pressed { background:#0E639C; }
            """)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        for p in self._recent:
            name = Path(p).name if Path(p).exists() else f"[없음] {Path(p).name}"
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setToolTip(p)
            self._list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and Path(path).exists():
            self._open_path(path)
        else:
            QMessageBox.warning(self, "경고", f"프로젝트를 찾을 수 없습니다:\n{path}")

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#252526; color:#CCC; border:1px solid #444; }
            QMenu::item:selected { background:#094771; }
            QMenu::item:disabled { color:#666; }
        """)
        open_act   = menu.addAction("열기")
        menu.addSeparator()
        remove_act = menu.addAction("목록에서 제거")
        action = menu.exec(self._list.mapToGlobal(pos))
        if action == open_act:
            self._on_item_double_clicked(item)
        elif action == remove_act:
            self._remove_from_recent(item)

    def _remove_from_recent(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path in self._recent:
            self._recent.remove(path)
            _save_recent(self._recent)
            self._refresh_list()

    def _new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.get_values()
        name = vals["name"].strip().replace(" ", "_")
        if not name:
            return
        altitude = vals["altitude"]
        temp = vals["temp"]

        save_dir = QFileDialog.getExistingDirectory(self, "프로젝트 저장 위치 선택")
        if not save_dir:
            return
        proj_dir = os.path.join(save_dir, name)
        os.makedirs(proj_dir, exist_ok=True)
        # 신규 프로젝트 생성 — main.fhd + project.fhproj 를 일관되게 기록
        # (저장/로드와 동일 경로·포맷 사용; 해발 datum + 온도 반영)
        fhd_path = os.path.join(proj_dir, "main.fhd")
        if not os.path.exists(fhd_path):
            from ...core.project_io import save_project
            save_project(proj_dir, _default_fhd(altitude, temp), name=name)
        self._open_path(proj_dir)

    def _open_project(self):
        path = QFileDialog.getExistingDirectory(self, "프로젝트 폴더 선택")
        if path:
            self._open_path(path)

    def _save_project(self):
        if self._current_path:
            self.project_saved.emit(self._current_path)

    def _open_path(self, path: str):
        self._current_path = path
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        _save_recent(self._recent)
        self._refresh_list()
        self.project_opened.emit(path)

    def set_current_path(self, path: str):
        self._current_path = path


class NewProjectDialog(QDialog):
    """새 프로젝트 생성 — 이름·기준 해발고도(datum)·유체 온도 입력."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새 프로젝트")
        self.setMinimumWidth(340)

        lay = QVBoxLayout(self)
        info = QLabel(
            "기준 해발고도(datum)를 정합니다. 이후 노드의 z 값은\n"
            "이 해발을 기준으로 한 상대 고도(+/−)이며,\n"
            "해발고도와 온도로 대기압·물성이 자동 계산됩니다.")
        info.setStyleSheet("color:#9CDCFE; font-size:11px;")
        lay.addWidget(info)

        form = QFormLayout()
        self._name = QLineEdit("project1")
        self._alt = QDoubleSpinBox()
        self._alt.setRange(-500.0, 10000.0)
        self._alt.setSuffix(" m")
        self._alt.setDecimals(1)
        self._alt.setValue(0.0)
        self._temp = QDoubleSpinBox()
        self._temp.setRange(0.0, 100.0)
        self._temp.setSuffix(" °C")
        self._temp.setDecimals(1)
        self._temp.setValue(20.0)
        form.addRow("프로젝트 이름:", self._name)
        form.addRow("기준 해발고도:", self._alt)
        form.addRow("유체 온도:", self._temp)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_values(self) -> dict:
        return {
            "name": self._name.text(),
            "altitude": self._alt.value(),
            "temp": self._temp.value(),
        }


def _default_fhd(altitude: float, temp: float) -> str:
    """기준 해발고도(datum)와 온도를 반영한 새 프로젝트 템플릿."""
    return f"""\
// FHDL 새 프로젝트 - 기본 템플릿
// 자세한 문법은 docs/spec/08_LANGUAGE.md 참조
//
// 기준 해발고도(datum) = {altitude:g}m. 아래 노드의 z 는 이 해발 기준 상대값이다.
// (예: z = 5m → 실제 해발 {altitude + 5:g}m). 대기압은 해발+온도로 자동 계산.

system main {{
    unit_system = METRIC;
    fluid = water;
    temp = {temp:g};
    altitude = {altitude:g}m;
    friction_model = DW;
}}

tank source {{
    z = 5m;
}}

pump p1 {{
    z = 0m;
}}

terminal t1 {{
    z = 0m;
    required_q = 100lpm;
    required_p = 0.1MPa;
}}

pipe pipe1 {{
    start = source;
    end = t1;
    length = 50m;
    diameter = auto;
    material = Steel;
}}

connect source -> pipe1 -> t1;
"""
