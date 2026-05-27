"""토폴로지 뷰어 패널 (중앙 우측). 배관망 그래프를 시각화한다."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPen, QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem,
    QGraphicsView, QVBoxLayout, QWidget,
)

from ...core.models import AnalysisResult, EntityMap, PipeCalcResult


# ---------------------------------------------------------------------------
# 노드 아이템
# ---------------------------------------------------------------------------

_NODE_COLORS = {
    "tank":         "#4EC9B0",  # 청록
    "pump":         "#85C1E9",  # 하늘
    "submersible":  "#5B9BD5",  # 진청 (수중펌프 — 탱크와 겹칠 때 구분)
    "terminal":     "#F0A500",  # 주황
    "junction":     "#9B9B9B",  # 회색
}

_PIPE_COLORS = {
    "OK":      "#555",
    "WARNING": "#D4AC0D",
    "ERROR":   "#E74C3C",
}

_NODE_SIZE = 28


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, node_id: str, node_type: str, x: float, y: float):
        r = _NODE_SIZE / 2
        super().__init__(-r, -r, _NODE_SIZE, _NODE_SIZE)
        self.node_id = node_id
        self.setPos(x, y)
        color = _NODE_COLORS.get(node_type, "#9B9B9B")
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor("#222"), 1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # 레이블
        self._label = QGraphicsSimpleTextItem(node_id, self)
        self._label.setFont(QFont("Arial", 8))
        self._label.setBrush(QBrush(QColor("#EEE")))
        lw = self._label.boundingRect().width()
        self._label.setPos(-lw / 2, _NODE_SIZE / 2 + 2)

        # 연결된 엣지 목록
        self._edges: List["EdgeItem"] = []

    def add_edge(self, edge: "EdgeItem"):
        self._edges.append(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self._edges:
                edge.update_position()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsLineItem):
    def __init__(self, pipe_id: str, src: NodeItem, dst: NodeItem, status: str = "OK"):
        super().__init__()
        self.pipe_id = pipe_id
        self._src = src
        self._dst = dst
        self._status = status
        self._set_style()
        self.update_position()
        src.add_edge(self)
        dst.add_edge(self)

    def _set_style(self):
        color = _PIPE_COLORS.get(self._status, "#555")
        width = 2.5 if self._status == "WARNING" else 1.5
        if self._status == "ERROR":
            pen = QPen(QColor(color), 2.5, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor(color), width)
        self.setPen(pen)

    def set_status(self, status: str):
        self._status = status
        self._set_style()

    def update_position(self):
        sp = self._src.scenePos()
        ep = self._dst.scenePos()
        self.setLine(sp.x(), sp.y(), ep.x(), ep.y())


# ---------------------------------------------------------------------------
# 뷰어 패널
# ---------------------------------------------------------------------------

class TopologyViewer(QWidget):
    entity_selected = Signal(str)   # 선택된 노드/배관 ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._view = _ZoomableView(self._scene)
        self._node_items: Dict[str, NodeItem] = {}
        self._edge_items: Dict[str, EdgeItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

    def update_from_result(self, result: AnalysisResult):
        """분석 결과로 뷰를 갱신한다."""
        if result.entity_map:
            self._build_from_entity_map(result.entity_map)
        # 배관 상태 색상 갱신
        status_map = {pr.pipe_id: pr.status for pr in result.pipe_results}
        for pid, edge in self._edge_items.items():
            edge.set_status(status_map.get(pid, "OK"))
        self._scene.update()

    def update_from_entity_map(self, em: EntityMap):
        self._build_from_entity_map(em)

    def _build_from_entity_map(self, em: EntityMap):
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()

        # 자동 레이아웃 (간단한 circular/spring)
        positions = self._layout(em)

        # 노드 그리기
        for nid, (x, y) in positions.items():
            ntype = _resolve_type(nid, em)
            item = NodeItem(nid, ntype, x, y)
            self._scene.addItem(item)
            self._node_items[nid] = item

        # 배관(엣지) 그리기
        for pipe in em.pipes.values():
            src = self._node_items.get(pipe.start_id)
            dst = self._node_items.get(pipe.end_id)
            if src and dst:
                edge = EdgeItem(pipe.entity_id, src, dst)
                self._scene.addItem(edge)
                self._edge_items[pipe.entity_id] = edge

        # fit view
        self._view.fitInView(self._scene.itemsBoundingRect(),
                             Qt.AspectRatioMode.KeepAspectRatio)

    def _layout(self, em: EntityMap) -> Dict[str, Tuple[float, float]]:
        """노드 위치 자동 배치 (계층형 + 수중펌프 탱크 중첩 처리)."""
        pos: Dict[str, Tuple[float, float]] = {}
        r = 200.0
        cx, cy = 0.0, 0.0

        # 1단계: 탱크 배치 (왼쪽에서 오른쪽)
        tanks = list(em.tanks)
        for i, nid in enumerate(tanks):
            pos[nid] = (cx + i * 130, cy)

        # 2단계: 일반 펌프 배치 (탱크 행 옆에 이어서)
        normal_pumps = [
            nid for nid, p in em.pumps.items()
            if p.pump_type != "submersible"
        ]
        offset = len(tanks) * 130
        for i, nid in enumerate(normal_pumps):
            pos[nid] = (cx + offset + i * 130, cy)

        # 3단계: 수중펌프 — 기준 탱크와 동일 좌표 (겹침 허용)
        for nid, pump in em.pumps.items():
            if pump.pump_type == "submersible":
                ref = pump.submerge_ref
                if ref and ref in pos:
                    # 기준 탱크와 완전히 겹침 (사용자 요청)
                    pos[nid] = pos[ref]
                elif tanks:
                    # 기준 탱크 미지정 시 첫 번째 탱크에 겹침
                    pos[nid] = pos[tanks[0]]
                else:
                    pos[nid] = (cx, cy)

        # 4단계: 나머지 노드(junction, terminal)를 원형 배치
        sources = set(tanks) | set(em.pumps.keys())
        others = [nid for nid in em.all_node_ids() if nid not in sources]
        for i, nid in enumerate(others):
            angle = 2 * math.pi * i / max(len(others), 1)
            pos[nid] = (cx + r * math.cos(angle), cy + r * math.sin(angle))

        # 5단계: DSL에 x/y 좌표가 직접 지정된 경우 덮어씀
        for entity in (list(em.tanks.values()) + list(em.pumps.values()) +
                       list(em.junctions.values()) + list(em.terminals.values())):
            if hasattr(entity, 'x') and (entity.x != 0 or entity.y != 0):
                pos[entity.entity_id] = (entity.x * 5, -entity.y * 5)

        return pos

    def clear(self):
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()


def _resolve_type(nid: str, em: EntityMap) -> str:
    if nid in em.tanks:
        return "tank"
    if nid in em.pumps:
        return "submersible" if em.pumps[nid].pump_type == "submersible" else "pump"
    if nid in em.junctions:
        return "junction"
    if nid in em.terminals:
        return "terminal"
    return "junction"


# ---------------------------------------------------------------------------
# 줌/패닝 가능한 QGraphicsView
# ---------------------------------------------------------------------------

class _ZoomableView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(self.renderHints().Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setStyleSheet("background:#1A1A2E; border:none;")

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else (1 / 1.15)
        self.scale(factor, factor)
