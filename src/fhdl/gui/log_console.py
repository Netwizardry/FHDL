"""하단 작업 로그 콘솔 — 진행 상황·경고·에러를 타임스탬프와 함께 표시."""
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)


_LEVEL_COLORS = {
    "INFO":    "#9CDCFE",   # 하늘
    "OK":      "#4EC9B0",   # 청록 (성공)
    "WARNING": "#D7BA7D",   # 노랑
    "ERROR":   "#F48771",   # 빨강
    "RUN":     "#C586C0",   # 보라 (실행 동작)
    "CMD":     "#DCDCAA",   # 노랑 (입력 명령 에코)
}


class LogConsole(QWidget):
    """작은 터미널 — 로그 출력 + 명령어 입력(TUI). GUI 작업을 명령으로도 수행."""

    command_entered = Signal(str)   # 입력된 명령어

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list = []
        self._hist_idx = 0
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

        # 명령어 입력줄 (TUI)
        input_row = QWidget()
        ir = QHBoxLayout(input_row)
        ir.setContentsMargins(6, 2, 6, 3)
        ir.setSpacing(4)
        prompt = QLabel("›")
        prompt.setStyleSheet("color:#4EC9B0; font-weight:bold;")
        ir.addWidget(prompt)
        self._input = QLineEdit()
        self._input.setPlaceholderText("명령어 입력 (help 입력 시 목록)  예: add tank T1 z=10m / link A B / run")
        self._input.setStyleSheet(
            "QLineEdit{background:#1A1A1A;color:#D4D4D4;border:1px solid #333;"
            "border-radius:2px;padding:2px 4px;}")
        self._input.setFont(QFont("Consolas, 'Courier New', monospace", 10))
        self._input.returnPressed.connect(self._on_enter)
        self._input.installEventFilter(self)
        ir.addWidget(self._input, 1)
        lay.addWidget(input_row)

    def _on_enter(self):
        text = self._input.text().strip()
        if not text:
            return
        self.log(text, "CMD")
        self._history.append(text)
        self._hist_idx = len(self._history)
        self._input.clear()
        self.command_entered.emit(text)

    def eventFilter(self, obj, event):
        # 위/아래 화살표로 명령 히스토리 탐색
        from PySide6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up and self._history:
                self._hist_idx = max(0, self._hist_idx - 1)
                self._input.setText(self._history[self._hist_idx])
                return True
            if key == Qt.Key.Key_Down and self._history:
                self._hist_idx = min(len(self._history), self._hist_idx + 1)
                self._input.setText(self._history[self._hist_idx]
                                    if self._hist_idx < len(self._history) else "")
                return True
        return super().eventFilter(obj, event)

    def focus_input(self):
        self._input.setFocus()

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
