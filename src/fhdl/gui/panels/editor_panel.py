"""DSL 에디터 패널 (중앙 좌측)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPaintEvent, QTextCursor, QTextFormat,
)
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget,
)

from ..highlighter import FHDLHighlighter


# ---------------------------------------------------------------------------
# 줄번호 거터
# ---------------------------------------------------------------------------

class _LineNumberGutter(QWidget):
    def __init__(self, editor: QPlainTextEdit):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor._gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent):
        self._editor._paint_gutter(event)


# ---------------------------------------------------------------------------
# 에디터 본체
# ---------------------------------------------------------------------------

class FHDLEditor(QPlainTextEdit):
    text_changed_debounced = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter = _LineNumberGutter(self)
        self._highlighter = FHDLHighlighter(self.document())
        self._error_lines: dict = {}  # {line: code}

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_debounced)

        self.setFont(QFont("Consolas, 'Courier New', monospace", 11))
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1E1E1E;
                color: #D4D4D4;
                border: none;
                selection-background-color: #264F78;
            }
        """)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(28)  # ~4 spaces

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.textChanged.connect(self._on_text_changed)
        self._update_gutter_width()

    # ------------------------------------------------------------------
    # 파일 I/O
    # ------------------------------------------------------------------

    def load_file(self, path: str):
        try:
            text = Path(path).read_text(encoding="utf-8")
            self.setPlainText(text)
        except Exception as e:
            self.setPlainText(f"// 파일 읽기 오류: {e}")

    def save_file(self, path: str):
        Path(path).write_text(self.toPlainText(), encoding="utf-8")

    # ------------------------------------------------------------------
    # 에러 마커
    # ------------------------------------------------------------------

    def set_error_lines(self, error_lines: dict):
        """error_lines: {line_number: code}"""
        self._error_lines = error_lines
        self._highlight_error_lines()

    def _highlight_error_lines(self):
        extras = []
        sel = QTextCursor(self.document())
        for line_no in self._error_lines:
            block = self.document().findBlockByLineNumber(line_no - 1)
            if block.isValid():
                sel = QTextCursor(block)
                sel.select(QTextCursor.SelectionType.LineUnderCursor)
                extra = self.ExtraSelection()
                extra.format.setBackground(QColor(80, 20, 20))
                extra.cursor = sel
                extras.append(extra)
        self.setExtraSelections(extras)

    def jump_to_line(self, line: int):
        block = self.document().findBlockByLineNumber(line - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()

    # ------------------------------------------------------------------
    # 거터 (줄번호)
    # ------------------------------------------------------------------

    def _gutter_width(self) -> int:
        digits = max(3, len(str(self.blockCount())))
        return 6 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self):
        self.setViewportMargins(self._gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self._gutter_width(), cr.height()))

    def _paint_gutter(self, event: QPaintEvent):
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor("#1A1A1A"))
        block = self.firstVisibleBlock()
        bn = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                num = str(bn + 1)
                is_err = (bn + 1) in self._error_lines
                painter.setPen(QColor("#E06C75") if is_err else QColor("#858585"))
                painter.drawText(
                    0, top, self._gutter.width() - 3,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, num,
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            bn += 1

    # ------------------------------------------------------------------
    # 텍스트 변경 debounce
    # ------------------------------------------------------------------

    def _on_text_changed(self):
        self._debounce_timer.start()

    def _emit_debounced(self):
        self.text_changed_debounced.emit(self.toPlainText())


# ---------------------------------------------------------------------------
# 에디터 패널 래퍼
# ---------------------------------------------------------------------------

class EditorPanel(QWidget):
    run_requested = Signal(str)       # 소스 코드
    text_changed = Signal(str)        # debounce 적용된 텍스트
    file_path_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fhd_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 상단 헤더 바
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet("background:#252526; border-bottom:1px solid #333;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(8, 2, 8, 2)
        self._file_label = QLabel("untitled.fhd")
        self._file_label.setStyleSheet("color:#CCC; font-size:11px;")
        h_lay.addWidget(self._file_label)
        h_lay.addStretch()
        layout.addWidget(header)

        # 에디터
        self._editor = FHDLEditor()
        self._editor.text_changed_debounced.connect(self.text_changed)
        layout.addWidget(self._editor, stretch=1)

    def load_file(self, fhd_path: str):
        self._fhd_path = fhd_path
        from pathlib import Path
        self._file_label.setText(Path(fhd_path).name)
        self._editor.load_file(fhd_path)
        self.file_path_changed.emit(fhd_path)

    def save_file(self, path: Optional[str] = None):
        target = path or self._fhd_path
        if target:
            self._editor.save_file(target)

    def get_source(self) -> str:
        return self._editor.toPlainText()

    def set_error_lines(self, error_lines: dict):
        self._editor.set_error_lines(error_lines)

    def jump_to_line(self, line: int):
        self._editor.jump_to_line(line)

    def set_source(self, text: str):
        self._editor.setPlainText(text)

    @property
    def fhd_path(self) -> Optional[str]:
        return self._fhd_path
