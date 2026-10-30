"""시작 화면 — 설계 분야(FHDL 유체 / EHDL 전기 …) 선택.

분야 목록은 `fhdl.domains.DOMAINS`. 준비 중인 분야는 비활성 카드로 보인다.
"다음부터 바로 시작"을 체크하면 선택을 QSettings(`startup/domain`)에 기억한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout,
)

from ..domains import DOMAINS, Domain

SETTINGS_KEY = "startup/domain"
_ICONS = Path(__file__).resolve().parents[3] / "resources" / "icons"


class StartDialog(QDialog):

    def __init__(self, settings: Optional[QSettings] = None, parent=None, message: str = ""):
        super().__init__(parent)
        self._settings = settings
        self.selected: Optional[str] = None
        self.setWindowTitle("설계 분야 선택")
        self.setMinimumWidth(640)
        icon = _ICONS / "app.svg"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        from .main_window import load_theme_qss
        self.setStyleSheet(load_theme_qss())

        title = QLabel("어떤 설계를 시작할까요?")
        title.setStyleSheet("font-size:18px; font-weight:bold; padding:4px 0;")
        lay = QVBoxLayout(self)
        lay.addWidget(title)
        if message:
            note = QLabel(message)
            note.setStyleSheet("color:#D4AC0D;")
            lay.addWidget(note)

        cards = QHBoxLayout()
        self._cards = {}
        for d in DOMAINS:
            btn = self._card(d)
            self._cards[d.key] = btn
            cards.addWidget(btn)
        lay.addLayout(cards)

        self._remember = QCheckBox("다음부터 이 선택으로 바로 시작")
        lay.addWidget(self._remember)
        bottom = QHBoxLayout()
        hint = QLabel("분야는 실행 중에도 파일 → 설계 분야 전환으로 바꿀 수 있습니다.")
        hint.setStyleSheet("color:#8B949E;")
        bottom.addWidget(hint, 1)
        quit_btn = QPushButton("종료")
        quit_btn.clicked.connect(self.reject)
        bottom.addWidget(quit_btn)
        lay.addLayout(bottom)

    def _card(self, d: Domain) -> QToolButton:
        btn = QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        icon = _ICONS / d.icon
        if icon.exists():
            btn.setIcon(QIcon(str(icon)))
        btn.setIconSize(QSize(72, 72))
        status = "" if d.available else "\n[준비 중]"
        btn.setText(f"{d.name}\n{d.title}{status}")
        btn.setToolTip(d.description)
        btn.setMinimumSize(QSize(280, 190))
        btn.setEnabled(d.available)
        btn.setStyleSheet("QToolButton { font-size:14px; padding:10px; border:1px solid #30363D;"
                          " border-radius:8px; } QToolButton:hover { border-color:#4EC9B0; }"
                          " QToolButton:disabled { color:#6E7681; }")
        btn.clicked.connect(lambda _=False, key=d.key: self.choose(key))
        return btn

    def choose(self, key: str) -> None:
        d = next((x for x in DOMAINS if x.key == key), None)
        if d is None or not d.available:
            return
        self.selected = key
        if self._settings is not None:
            if self._remember.isChecked():
                self._settings.setValue(SETTINGS_KEY, key)
            else:
                self._settings.remove(SETTINGS_KEY)
        self.accept()
