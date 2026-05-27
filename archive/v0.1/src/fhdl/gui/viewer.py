from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView
from src.fhdl.core.models import FluidSystem

class ResultViewer(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # 1. Nodes Table
        self.node_table = QTableWidget()
        self.node_table.setColumnCount(6)
        self.node_table.setHorizontalHeaderLabels([
            "Node ID", "Type", "Elevation (m)", "Head (m)", "Pressure (MPa)", "Actual Q"
        ])
        self.node_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.addTab(self.node_table, "Nodes Result")

        # 2. Pipes Table
        self.pipe_table = QTableWidget()
        self.pipe_table.setSortingEnabled(True) # 정렬 활성화
        self.pipe_table.setColumnCount(6)
        self.pipe_table.setHorizontalHeaderLabels([
            "Pipe ID", "Material", "Diameter (mm)", "Length (m)", "Velocity (m/s)", "Head Loss (m)"
        ])
        self.pipe_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.addTab(self.pipe_table, "Pipes Result")

    def clear_results(self):
        """이전 분석 결과 잔상 제거 (감사 지적 반영)"""
        self.node_table.setRowCount(0)
        self.pipe_table.setRowCount(0)

    def update_results(self, system: FluidSystem):
        """계산 완료된 시스템 객체로부터 테이블 갱신 (수치형 정렬 지원)"""
        # Node Table Update
        self.node_table.setSortingEnabled(False)
        self.node_table.setRowCount(len(system.nodes))
        for i, (nid, node) in enumerate(system.nodes.items()):
            self.node_table.setItem(i, 0, QTableWidgetItem(nid))
            self.node_table.setItem(i, 1, QTableWidgetItem(node.type.name))
            
            # 수치 데이터 주입 (EditRole 사용)
            z_item = QTableWidgetItem(); z_item.setData(Qt.EditRole, round(node.z, 3))
            self.node_table.setItem(i, 2, z_item)
            h_item = QTableWidgetItem(); h_item.setData(Qt.EditRole, round(node.head, 4))
            self.node_table.setItem(i, 3, h_item)
            
            pressure = (node.head - node.z) * system.actual_density * 9.80665 / 1_000_000
            p_item = QTableWidgetItem(); p_item.setData(Qt.EditRole, round(max(0, pressure), 4))
            self.node_table.setItem(i, 4, p_item)
            
            q_item = QTableWidgetItem(); q_item.setData(Qt.EditRole, round(node.actual_q, 2))
            self.node_table.setItem(i, 5, q_item)
        self.node_table.setSortingEnabled(True)

        # Pipe Table Update
        self.pipe_table.setSortingEnabled(False)
        self.pipe_table.setRowCount(len(system.pipes))
        for i, (pid, pipe) in enumerate(system.pipes.items()):
            self.pipe_table.setItem(i, 0, QTableWidgetItem(pid))
            self.pipe_table.setItem(i, 1, QTableWidgetItem(pipe.material_id))
            
            d_item = QTableWidgetItem(); d_item.setData(Qt.EditRole, round(pipe.diameter, 1))
            self.pipe_table.setItem(i, 2, d_item)
            l_item = QTableWidgetItem(); l_item.setData(Qt.EditRole, round(pipe.length, 3))
            self.pipe_table.setItem(i, 3, l_item)
            v_item = QTableWidgetItem(); v_item.setData(Qt.EditRole, round(pipe.velocity, 3))
            self.pipe_table.setItem(i, 4, v_item)
            hl_item = QTableWidgetItem(); hl_item.setData(Qt.EditRole, round(pipe.head_loss, 4))
            self.pipe_table.setItem(i, 5, hl_item)
        self.pipe_table.setSortingEnabled(True)
