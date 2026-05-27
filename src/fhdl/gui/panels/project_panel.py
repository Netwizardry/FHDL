"""프로젝트 선택 패널 (좌측 사이드바)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
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

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "새 프로젝트", "프로젝트 이름:")
        if not ok or not name.strip():
            return
        name = name.strip().replace(" ", "_")
        save_dir = QFileDialog.getExistingDirectory(self, "프로젝트 저장 위치 선택")
        if not save_dir:
            return
        proj_dir = os.path.join(save_dir, name)
        os.makedirs(proj_dir, exist_ok=True)
        # 기본 파일 생성
        fhd_path = os.path.join(proj_dir, "main.fhd")
        config_path = os.path.join(proj_dir, "config.fhproj")
        if not os.path.exists(fhd_path):
            Path(fhd_path).write_text(_DEFAULT_FHD, encoding="utf-8")
        if not os.path.exists(config_path):
            import json as _json
            from datetime import datetime
            cfg = {
                "schema_version": "1.0.0",
                "project_name": name,
                "created_at": datetime.now().isoformat(),
                "settings": {
                    "friction_model": "DW",
                    "unit_system": "METRIC",
                    "fluid_type": "water",
                    "fluid_temp": 20.0,
                },
            }
            Path(config_path).write_text(_json.dumps(cfg, indent=2), encoding="utf-8")
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


_DEFAULT_FHD = """\
// FHDL 새 프로젝트 - 기본 템플릿
// 자세한 문법은 docs/spec/08_LANGUAGE.md 참조

system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    altitude = 0m;
    friction_model = DW;
}

tank source {
    elevation = 5m;
}

pump p1 {
    elevation = 0m;
}

terminal t1 {
    elevation = 0m;
    required_q = 100lpm;
    required_p = 0.1MPa;
}

pipe pipe1 {
    start = source;
    end = t1;
    length = 50m;
    diameter = auto;
    material = Steel;
}

connect source -> pipe1 -> t1;
"""
