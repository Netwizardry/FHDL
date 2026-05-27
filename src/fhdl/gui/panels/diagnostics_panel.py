"""진단 패널 (하단 우측). 오류/경고 목록을 표시한다."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ...core.models import DiagnosticItem


_SEVERITY_COLORS = {
    "FATAL":   "#E74C3C",
    "ERROR":   "#E06C75",
    "WARNING": "#D4AC0D",
    "INFO":    "#4FC1FF",
}

_SEVERITY_ORDER = {"FATAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}


class DiagnosticsPanel(QWidget):
    diagnostic_selected = Signal(str, int)  # (code, line)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diagnostics: List[DiagnosticItem] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 헤더 + 필터 버튼
        header = QHBoxLayout()
        title = QLabel("진단")
        title.setStyleSheet("font-weight:bold; font-size:13px; color:#CCC;")
        header.addWidget(title)
        header.addStretch()

        for label, sev in [("E", "ERROR"), ("W", "WARNING"), ("I", "INFO")]:
            btn = QPushButton(label)
            btn.setFixedSize(22, 22)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setProperty("sev", sev)
            btn.setStyleSheet(f"""
                QPushButton {{ background:{_SEVERITY_COLORS.get(sev,'#555')};
                               color:#FFF; border:none; border-radius:3px; font-weight:bold; }}
                QPushButton:checked {{ opacity:1; }}
                QPushButton:!checked {{ background:#333; }}
            """)
            btn.toggled.connect(self._apply_filter)
            header.addWidget(btn)

        layout.addLayout(header)

        # 트리 위젯
        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["심각도", "코드", "메시지", "위치"])
        self._tree.setStyleSheet("""
            QTreeWidget { background:#1E1E1E; color:#CCC; border:1px solid #333; }
            QTreeWidget::item:selected { background:#094771; }
            QTreeWidget::item:hover { background:#2A2D2E; }
            QHeaderView::section { background:#252526; color:#CCC; border:1px solid #333; }
        """)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.header().setStretchLastSection(False)
        self._tree.setColumnWidth(0, 60)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 200)
        layout.addWidget(self._tree, stretch=1)

        # 상세 레이블
        self._detail = QLabel("")
        self._detail.setWordWrap(True)
        self._detail.setStyleSheet("color:#888; font-size:11px; padding:2px;")
        layout.addWidget(self._detail)

    def update_diagnostics(self, items: List[DiagnosticItem]):
        self._diagnostics = sorted(
            items, key=lambda d: _SEVERITY_ORDER.get(d.severity, 99)
        )
        self._render()

    def _render(self):
        self._tree.clear()

        # 심각도별 그룹
        groups: dict = {"FATAL": [], "ERROR": [], "WARNING": [], "INFO": []}
        for d in self._diagnostics:
            groups.setdefault(d.severity, []).append(d)

        for sev, diags in groups.items():
            if not diags:
                continue
            group_item = QTreeWidgetItem([sev, f"({len(diags)}개)", "", ""])
            color = QColor(_SEVERITY_COLORS.get(sev, "#CCC"))
            group_item.setForeground(0, color)
            group_item.setForeground(1, color)
            self._tree.addTopLevelItem(group_item)

            for d in diags:
                loc = f"L{d.source_span.line}:C{d.source_span.col}" if d.source_span.line else ""
                child = QTreeWidgetItem([sev, d.code, d.message, loc])
                child.setForeground(0, color)
                child.setData(0, Qt.ItemDataRole.UserRole, d)
                group_item.addChild(child)

            group_item.setExpanded(True)

    def _apply_filter(self):
        # 필터링은 간단하게 re-render
        self._render()

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        d: DiagnosticItem = item.data(0, Qt.ItemDataRole.UserRole)
        if d:
            self._detail.setText(f"[{d.code}] {d.message}\n→ {d.suggested_action}")
            self.diagnostic_selected.emit(d.code, d.source_span.line)

    def clear(self):
        self._diagnostics = []
        self._tree.clear()
        self._detail.setText("")

    @property
    def error_count(self) -> int:
        return sum(1 for d in self._diagnostics if d.severity in ("ERROR", "FATAL"))

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self._diagnostics if d.severity == "WARNING")
