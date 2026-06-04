"""하단 작업 로그 콘솔 — 진행 상황·경고·에러를 타임스탬프와 함께 표시."""
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)


_LEVEL_COLORS = {
    "INFO":    "#9CDCFE",   # 하늘
    "OK":      "#4EC9B0",   # 청록 (성공)
    "WARNING": "#D7BA7D",   # 노랑
    "ERROR":   "#F48771",   # 빨강
    "RUN":     "#C586C0",   # 보라 (실행 동작)
}


class LogConsole(QWidget):
    """작은 터미널 형태의 읽기 전용 로그 출력 패널."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 헤더 바
        header = QWidget()
        header.setFixedHeight(24)
        header.setStyleSheet("background:#2D2D2D; border-top:1px solid #3C3C3C;")
        h = QHBoxLayout(header)
        h.setContentsMargins(8, 0, 6, 0)
        h.setSpacing(4)
        title = QLabel("작업 로그")
        title.setStyleSheet("color:#BBB; font-size:11px; font-weight:bold;")
        h.addWidget(title)
        h.addStretch()
        clear_btn = QPushButton("지우기")
        clear_btn.setStyleSheet(
            "QPushButton{background:#3C3C3C;color:#CCC;border:1px solid #555;"
            "padding:1px 8px;border-radius:2px;font-size:10px;}"
            "QPushButton:hover{background:#4C4C4C;}")
        clear_btn.clicked.connect(self.clear)
        h.addWidget(clear_btn)
        lay.addWidget(header)

        # 로그 본문
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setMaximumBlockCount(2000)   # 오래된 줄 자동 제거
        self._view.setFont(QFont("Consolas, 'Courier New', monospace", 10))
        self._view.setStyleSheet(
            "QPlainTextEdit{background:#121212;color:#D4D4D4;border:none;"
            "selection-background-color:#264F78;}")
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lay.addWidget(self._view, 1)

    # -- 출력 API -------------------------------------------------------

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        color = _LEVEL_COLORS.get(level, "#D4D4D4")
        msg = html.escape(str(message))
        self._view.appendHtml(
            f'<span style="color:#5A5A5A">[{ts}]</span> '
            f'<span style="color:{color};font-weight:bold">{level:<7}</span> '
            f'<span style="color:#D4D4D4">{msg}</span>')
        sb = self._view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def info(self, m: str):    self.log(m, "INFO")
    def ok(self, m: str):      self.log(m, "OK")
    def warning(self, m: str): self.log(m, "WARNING")
    def error(self, m: str):   self.log(m, "ERROR")
    def run(self, m: str):     self.log(m, "RUN")

    def clear(self):
        self._view.clear()
