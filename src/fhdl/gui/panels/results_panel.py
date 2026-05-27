"""결과 대시보드 패널 (하단 좌측)."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...core.models import AnalysisResult, NodeCalcResult, PipeCalcResult, SystemSummary


class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: Optional[AnalysisResult] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 탭
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #333; background:#1E1E1E; }
            QTabBar::tab { background:#252526; color:#CCC; padding:4px 12px; border-radius:2px 2px 0 0; }
            QTabBar::tab:selected { background:#1E1E1E; color:#FFF; }
        """)

        # 요약 탭
        self._summary_widget = _SummaryWidget()
        tabs.addTab(self._summary_widget, "요약")

        # 배관 상세 탭
        self._pipes_table = _ResultTable(
            ["배관 ID", "관경(mm)", "유량(L/min)", "유속(m/s)",
             "손실수두(m)", "수충격", "상태", "공식"]
        )
        tabs.addTab(self._pipes_table, "배관 결과")

        # 노드 상세 탭
        self._nodes_table = _ResultTable(
            ["노드 ID", "수두(m)", "압력(MPa)", "유입(L/min)", "유출(L/min)", "NPSHa(m)"]
        )
        tabs.addTab(self._nodes_table, "노드 결과")

        layout.addWidget(tabs, stretch=1)

        # 내보내기 버튼
        export_btn = QPushButton("CSV 내보내기")
        export_btn.setStyleSheet("""
            QPushButton { background:#3C3C3C; color:#CCC; border:1px solid #555; padding:3px; border-radius:2px; }
            QPushButton:hover { background:#4C4C4C; }
        """)
        export_btn.clicked.connect(self._export_csv)
        layout.addWidget(export_btn)

    def update_result(self, result: AnalysisResult):
        self._result = result
        self._summary_widget.update(result.summary, result.status)
        self._update_pipes(result.pipe_results)
        self._update_nodes(result.node_results)

    def _update_pipes(self, rows: List[PipeCalcResult]):
        self._pipes_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r.pipe_id,
                f"{r.diameter * 1000:.1f}",
                f"{r.flow * 60000:.2f}",
                f"{r.velocity:.3f}",
                f"{r.h_loss_total:.4f}",
                f"{r.surge_index:.3f}",
                r.status,
                r.formula_id,
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if r.status == "WARNING":
                    item.setBackground(Qt.GlobalColor.darkYellow)
                self._pipes_table.setItem(i, j, item)

    def _update_nodes(self, rows: List[NodeCalcResult]):
        self._nodes_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r.node_id,
                f"{r.head_total:.3f}",
                f"{r.p_gauge / 1e6:.4f}",
                f"{r.flow_in * 60000:.2f}",
                f"{r.flow_out * 60000:.2f}",
                f"{r.npsha:.3f}",
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._nodes_table.setItem(i, j, item)

    def _export_csv(self):
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "results.csv", "CSV Files (*.csv)")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["=== 배관 결과 ==="])
            w.writerow(["배관ID", "관경(mm)", "유량(L/min)", "유속(m/s)", "손실수두(m)", "상태"])
            for r in self._result.pipe_results:
                w.writerow([r.pipe_id, f"{r.diameter*1000:.1f}", f"{r.flow*60000:.2f}",
                             f"{r.velocity:.3f}", f"{r.h_loss_total:.4f}", r.status])
            w.writerow([])
            w.writerow(["=== 노드 결과 ==="])
            w.writerow(["노드ID", "수두(m)", "압력(MPa)", "NPSHa(m)"])
            for r in self._result.node_results:
                w.writerow([r.node_id, f"{r.head_total:.3f}",
                             f"{r.p_gauge/1e6:.4f}", f"{r.npsha:.3f}"])

    def clear(self):
        self._summary_widget.clear()
        self._pipes_table.setRowCount(0)
        self._nodes_table.setRowCount(0)


class _SummaryWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._status_label = QLabel("─")
        self._status_label.setStyleSheet("font-size:13px; font-weight:bold; color:#4EC9B0;")
        layout.addWidget(self._status_label)

        self._cards: List[QLabel] = []
        for _ in range(6):
            lbl = QLabel("─")
            lbl.setStyleSheet("color:#CCC; font-size:12px;")
            layout.addWidget(lbl)
            self._cards.append(lbl)

        layout.addStretch()

    def update(self, s: SystemSummary, status: str):
        color = {"OK": "#4EC9B0", "PARTIAL": "#D4AC0D", "FAILED": "#E74C3C"}.get(status, "#CCC")
        self._status_label.setText(f"상태: {status}")
        self._status_label.setStyleSheet(f"font-size:13px; font-weight:bold; color:{color};")

        self._cards[0].setText(f"총 유량: {s.total_flow * 3600:.2f} m³/h ({s.total_flow * 60000:.1f} L/min)")
        self._cards[1].setText(f"총 요구양정: {s.required_head:.2f} m")
        self._cards[2].setText(f"권장 펌프 유량: {s.recommended_pump_flow * 3600:.2f} m³/h")
        self._cards[3].setText(f"권장 펌프 양정: {s.recommended_pump_head:.2f} m")
        self._cards[4].setText(f"권장 탱크 용량: {s.recommended_tank_volume:.2f} m³")
        worst = " → ".join(s.worst_path) if s.worst_path else "─"
        self._cards[5].setText(f"최불리 경로: {worst}")

    def clear(self):
        self._status_label.setText("─")
        for c in self._cards:
            c.setText("─")


class _ResultTable(QTableWidget):
    def __init__(self, headers: List[str]):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setStyleSheet("""
            QTableWidget { background:#1E1E1E; color:#CCC; gridline-color:#333; border:none; }
            QHeaderView::section { background:#252526; color:#CCC; border:1px solid #333; padding:2px; }
        """)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
