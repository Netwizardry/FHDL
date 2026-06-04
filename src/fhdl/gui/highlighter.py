"""FHDL DSL 구문 하이라이터 (PySide6 QSyntaxHighlighter)."""
from __future__ import annotations

import re
from typing import List, Tuple

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class FHDLHighlighter(QSyntaxHighlighter):
    """FHDL DSL 구문 하이라이팅."""

    def __init__(self, document):
        super().__init__(document)
        self._rules: List[Tuple[QRegularExpression, QTextCharFormat]] = []
        self._build_rules()

    def _build_rules(self):
        # 블록 타입 키워드
        kw_fmt = _fmt("#569CD6", bold=True)
        for kw in (
            "system", "tank", "pump", "pipe", "junction", "terminal",
            "connect", "constraint",
        ):
            self._rules.append((
                QRegularExpression(rf"\b{kw}\b", QRegularExpression.PatternOption.CaseInsensitiveOption),
                kw_fmt,
            ))

        # 속성 키워드
        attr_fmt = _fmt("#9CDCFE")
        for attr in (
            "z", "elevation", "flow", "head", "length", "diameter", "material",
            "required_q", "required_p", "k_factor", "c_factor", "fittings",
            "roughness", "temp", "altitude", "unit_system",
            "friction_model", "velocity_min", "velocity_max",
            "safety_factor_head", "safety_factor_npsh",
            "volume", "level_max", "efficiency", "npshr",
            "pump_type", "min_level", "submerge_ref",
            "start", "end", "x", "y",
        ):
            self._rules.append((
                QRegularExpression(rf"\b{attr}\b"),
                attr_fmt,
            ))

        # 단위 (숫자 뒤)
        unit_fmt = _fmt("#B5CEA8")
        self._rules.append((
            QRegularExpression(r"\b\d+(\.\d+)?\s*(m3s|m3h|m3/s|m3/h|lpm|gpm|mpa|kpa|bar|psi|mm|m|ft|m3|ls)\b",
                               QRegularExpression.PatternOption.CaseInsensitiveOption),
            unit_fmt,
        ))

        # 숫자
        num_fmt = _fmt("#B5CEA8")
        self._rules.append((
            QRegularExpression(r"\b\d+(\.\d+)?([eE][+-]?\d+)?\b"),
            num_fmt,
        ))

        # 특수값
        special_fmt = _fmt("#DCDCAA", bold=True)
        for sv in ("auto", "METRIC", "IMPERIAL", "DW", "HW", "water"):
            self._rules.append((
                QRegularExpression(rf"\b{sv}\b", QRegularExpression.PatternOption.CaseInsensitiveOption),
                special_fmt,
            ))

        # 연산자 및 구두점
        op_fmt = _fmt("#D4D4D4")
        self._rules.append((QRegularExpression(r"->"), op_fmt))
        self._rules.append((QRegularExpression(r"[=;{}]"), op_fmt))

        # 행 주석
        comment_fmt = _fmt("#6A9955", italic=True)
        self._rules.append((
            QRegularExpression(r"//[^\n]*"),
            comment_fmt,
        ))

        # 블록 주석 (멀티라인)
        self._block_comment_start = QRegularExpression(r"/\*")
        self._block_comment_end = QRegularExpression(r"\*/")
        self._block_comment_fmt = comment_fmt

    def highlightBlock(self, text: str):
        # 단일행 규칙
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

        # 멀티라인 블록 주석
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            m = self._block_comment_start.match(text)
            if m.hasMatch():
                start = m.capturedStart()
            else:
                return

        while start >= 0:
            m_end = self._block_comment_end.match(text, start)
            if m_end.hasMatch():
                length = m_end.capturedEnd() - start
                self.setFormat(start, length, self._block_comment_fmt)
                m_next = self._block_comment_start.match(text, m_end.capturedEnd())
                start = m_next.capturedStart() if m_next.hasMatch() else -1
            else:
                self.setCurrentBlockState(1)
                self.setFormat(start, len(text) - start, self._block_comment_fmt)
                break
