"""토폴로지 뷰어 패널 (중앙 우측).

배관망을 아이소메트릭 2.5D로 시각화한다.
사용자 입력 (x, y, elevation) 을 (x, y, z) 3D 좌표로 보고
아이소메트릭 투영하여 화면에 그린다.

투영식:
    sx = (x - y) * cos(30°) * SCALE_XY
    sy = (x + y) * sin(30°) * SCALE_XY  -  z * SCALE_Z

각 노드는 바닥(z=0) 투영점까지 '높이 기둥'을 그려 고도를 표현하고,
바닥에는 아이소 격자를 깐다. 네트워크 진단(NET/WRN)은 노드 테두리와
배관 선 색으로 표시한다.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QLineF, QPointF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainterPath, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView,
    QVBoxLayout, QWidget,
)

from ...core.models import AnalysisResult, EntityMap


# ---------------------------------------------------------------------------
# 투영 상수
# ---------------------------------------------------------------------------

_ISO_COS = math.cos(math.radians(30))   # ≈ 0.866
_ISO_SIN = math.sin(math.radians(30))   # = 0.5
_SCALE_XY = 2.6                          # 평면 좌표 1단위 → px
_SCALE_Z = 7.0                           # 고도 1m → px (수직 과장)

_NODE_SIZE = 26

_NODE_COLORS = {
    "tank":        "#4EC9B0",   # 청록
    "pump":        "#85C1E9",   # 하늘
    "submersible": "#5B9BD5",   # 진청
    "terminal":    "#F0A500",   # 주황
    "junction":    "#9B9B9B",   # 회색
}

# 진단 심각도 → 강조 색/굵기
_SEVERITY_PEN = {
    "ERROR":   ("#E74C3C", 3.0),   # 빨강 (NET001/003/005, 등)
    "FATAL":   ("#E74C3C", 3.0),
    "WARNING": ("#F39C12", 2.5),   # 주황 (NET004, WRN*)
}
_DEFAULT_NODE_PEN = ("#1A1A1A", 1.5)

_PIPE_COLORS = {
    "OK":      "#6C7A89",
    "WARNING": "#D4AC0D",
    "ERROR":   "#E74C3C",
}

_SEV_RANK = {"INFO": 0, "WARNING": 1, "ERROR": 2, "FATAL": 3}

# 진단 메시지에서 '식별자' 추출
_ID_RE = re.compile(r"'([A-Za-z_]\w*)'")


def _iso(x: float, y: float, z: float) -> QPointF:
    """(x, y, z) → 아이소메트릭 화면 좌표."""
    sx = (x - y) * _ISO_COS * _SCALE_XY
    sy = (x + y) * _ISO_SIN * _SCALE_XY - z * _SCALE_Z
    return QPointF(sx, sy)


# ---------------------------------------------------------------------------
# 노드 아이템 (타입별 도형 + 진단 테두리)
# ---------------------------------------------------------------------------

class NodeItem(QGraphicsPathItem):
    def __init__(self, node_id: str, node_type: str, apex: QPointF,
                 elevation: float):
        super().__init__()
        self.node_id = node_id
        self.node_type = node_type
        self.setPath(self._shape_for(node_type))
        self.setBrush(QBrush(QColor(_NODE_COLORS.get(node_type, "#9B9B9B"))))
        self.set_severity(None)
        self.setPos(apex)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        # 라벨 (id + 고도)
        label = QGraphicsSimpleTextItem(f"{node_id}\nz={elevation:g}m", self)
        label.setFont(QFont("Arial", 7))
        label.setBrush(QBrush(QColor("#EAEAEA")))
        lw = label.boundingRect().width()
        label.setPos(-lw / 2, _NODE_SIZE / 2 + 1)

    @staticmethod
    def _shape_for(node_type: str) -> QPainterPath:
        r = _NODE_SIZE / 2
        path = QPainterPath()
        if node_type == "tank":
            path.addRoundedRect(-r, -r, _NODE_SIZE, _NODE_SIZE, 4, 4)
        elif node_type == "terminal":
            tri = QPolygonF([QPointF(0, -r), QPointF(r, r), QPointF(-r, r)])
            path.addPolygon(tri)
            path.closeSubpath()
        else:  # pump / submersible / junction
            path.addEllipse(-r, -r, _NODE_SIZE, _NODE_SIZE)
        return path

    def set_severity(self, severity: Optional[str]):
        color, width = _SEVERITY_PEN.get(severity or "", _DEFAULT_NODE_PEN)
        self.setPen(QPen(QColor(color), width))


# ---------------------------------------------------------------------------
# 배관(엣지) 아이템
# ---------------------------------------------------------------------------

class EdgeItem(QGraphicsLineItem):
    def __init__(self, pipe_id: str, p1: QPointF, p2: QPointF, status: str = "OK"):
        super().__init__(QLineF(p1, p2))
        self.pipe_id = pipe_id
        self.set_status(status)
        self.setZValue(-1)  # 노드 아래

    def set_status(self, status: str):
        color = _PIPE_COLORS.get(status, "#6C7A89")
        if status == "ERROR":
            pen = QPen(QColor(color), 2.6, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor(color), 2.6 if status == "WARNING" else 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)


# ---------------------------------------------------------------------------
# 뷰어 패널
# ---------------------------------------------------------------------------

class TopologyViewer(QWidget):
    entity_selected = Signal(str)            # 노드 선택
    node_double_clicked = Signal(str)        # 노드 더블클릭 → 속성 편집
    connection_requested = Signal(str, str)  # 노드 드래그 연결 (from, to)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self._view = _ZoomableView(self._scene)
        self._node_items: Dict[str, NodeItem] = {}
        self._edge_items: Dict[str, EdgeItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._scene.selectionChanged.connect(self._on_selection)
        # 뷰의 마우스 제스처 → 시그널
        self._view.on_node_double = self.node_double_clicked.emit
        self._view.on_connect = self.connection_requested.emit

    # -- 공개 API -------------------------------------------------------

    def update_from_result(self, result: AnalysisResult):
        if result.entity_map:
            self._build(result.entity_map)
        # 배관 상태 색
        status_map = {pr.pipe_id: pr.status for pr in result.pipe_results}
        for pid, edge in self._edge_items.items():
            edge.set_status(status_map.get(pid, "OK"))
        # 진단 → 노드/배관 강조
        self._apply_diagnostics(result, status_map)
        self._scene.update()

    def update_from_entity_map(self, em: EntityMap):
        self._build(em)

    def clear(self):
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()

    # -- 내부 ----------------------------------------------------------

    def _on_selection(self):
        for it in self._scene.selectedItems():
            if isinstance(it, NodeItem):
                self.entity_selected.emit(it.node_id)
                return

    def _build(self, em: EntityMap):
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()

        plane = self._plane_layout(em)                      # nid -> (x, y)
        zmap = {nid: self._elevation(em, nid) for nid in plane}

        self._draw_ground(plane)

        # 높이 기둥 (바닥 z=0 → 노드 apex)
        for nid, (px, py) in plane.items():
            apex = _iso(px, py, zmap[nid])
            base = _iso(px, py, 0.0)
            pillar = QGraphicsLineItem(QLineF(base, apex))
            pillar.setPen(QPen(QColor("#3A4A5A"), 1.0, Qt.PenStyle.DashLine))
            pillar.setZValue(-2)
            self._scene.addItem(pillar)
            # 바닥 발자국 점
            foot = QGraphicsLineItem(QLineF(base, base))
            foot.setPen(QPen(QColor("#2E3B49"), 4.0))
            foot.setZValue(-2)
            self._scene.addItem(foot)

        # 배관(엣지): 노드 apex 연결
        for pipe in em.pipes.values():
            if pipe.start_id in plane and pipe.end_id in plane:
                p1 = _iso(*plane[pipe.start_id], zmap[pipe.start_id])
                p2 = _iso(*plane[pipe.end_id], zmap[pipe.end_id])
                edge = EdgeItem(pipe.entity_id, p1, p2)
                self._scene.addItem(edge)
                self._edge_items[pipe.entity_id] = edge

        # 노드
        for nid, (px, py) in plane.items():
            apex = _iso(px, py, zmap[nid])
            item = NodeItem(nid, _resolve_type(nid, em), apex, zmap[nid])
            # 앞쪽(x+y 큰) 노드가 위로 오도록
            item.setZValue(px + py)
            self._scene.addItem(item)
            self._node_items[nid] = item

        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-40, -40, 40, 40),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def _apply_diagnostics(self, result: AnalysisResult, status_map: Dict[str, str]):
        """진단 메시지에서 식별자를 추출해 노드/배관에 최고 심각도 강조."""
        node_sev: Dict[str, str] = {}
        edge_sev: Dict[str, str] = {}
        for d in result.diagnostics:
            for ident in _ID_RE.findall(d.message):
                if ident in self._node_items:
                    if _SEV_RANK.get(d.severity, 0) > _SEV_RANK.get(node_sev.get(ident, "INFO"), 0):
                        node_sev[ident] = d.severity
                elif ident in self._edge_items:
                    if _SEV_RANK.get(d.severity, 0) > _SEV_RANK.get(edge_sev.get(ident, "INFO"), 0):
                        edge_sev[ident] = d.severity
        for nid, item in self._node_items.items():
            item.set_severity(node_sev.get(nid))
        # 배관: 진단 심각도가 status보다 강하면 반영
        for pid, edge in self._edge_items.items():
            sev = edge_sev.get(pid)
            if sev in ("ERROR", "FATAL"):
                edge.set_status("ERROR")
            elif sev == "WARNING" and status_map.get(pid, "OK") == "OK":
                edge.set_status("WARNING")

    def _draw_ground(self, plane: Dict[str, Tuple[float, float]]):
        """노드 평면 좌표 범위에 아이소 격자를 깐다."""
        if not plane:
            return
        xs = [p[0] for p in plane.values()]
        ys = [p[1] for p in plane.values()]
        margin = 30.0
        x0, x1 = min(xs) - margin, max(xs) + margin
        y0, y1 = min(ys) - margin, max(ys) + margin
        step = max((x1 - x0), (y1 - y0)) / 8 or 20.0

        pen = QPen(QColor("#26303C"), 1.0)
        # x 방향 선 (y 고정)
        yy = y0
        while yy <= y1 + 1e-6:
            line = QGraphicsLineItem(QLineF(_iso(x0, yy, 0), _iso(x1, yy, 0)))
            line.setPen(pen)
            line.setZValue(-5)
            self._scene.addItem(line)
            yy += step
        # y 방향 선 (x 고정)
        xx = x0
        while xx <= x1 + 1e-6:
            line = QGraphicsLineItem(QLineF(_iso(xx, y0, 0), _iso(xx, y1, 0)))
            line.setPen(pen)
            line.setZValue(-5)
            self._scene.addItem(line)
            xx += step

    @staticmethod
    def _elevation(em: EntityMap, nid: str) -> float:
        ent = em.get_node_entity(nid)
        return float(getattr(ent, "elevation", 0.0)) if ent else 0.0

    def _plane_layout(self, em: EntityMap) -> Dict[str, Tuple[float, float]]:
        """노드 평면(x, y) 좌표. DSL 지정값 우선, 없으면 자동 배치."""
        pos: Dict[str, Tuple[float, float]] = {}
        spacing = 45.0
        radius = 90.0

        tanks = list(em.tanks)
        for i, nid in enumerate(tanks):
            pos[nid] = (i * spacing, 0.0)

        normal_pumps = [n for n, p in em.pumps.items() if p.pump_type != "submersible"]
        offset = len(tanks) * spacing
        for i, nid in enumerate(normal_pumps):
            pos[nid] = (offset + i * spacing, 0.0)

        for nid, pump in em.pumps.items():
            if pump.pump_type == "submersible":
                ref = pump.submerge_ref
                pos[nid] = pos.get(ref, pos.get(tanks[0]) if tanks else (0.0, 0.0))

        sources = set(tanks) | set(em.pumps)
        others = [n for n in em.all_node_ids() if n not in sources]
        for i, nid in enumerate(others):
            ang = 2 * math.pi * i / max(len(others), 1)
            pos[nid] = (radius + radius * math.cos(ang), radius * math.sin(ang))

        # DSL에 x/y가 명시된 노드는 그 값으로 덮어씀
        for ent in (list(em.tanks.values()) + list(em.pumps.values()) +
                    list(em.junctions.values()) + list(em.terminals.values())):
            if hasattr(ent, "x") and (ent.x != 0 or ent.y != 0):
                pos[ent.entity_id] = (float(ent.x), float(ent.y))

        return pos


def _resolve_type(nid: str, em: EntityMap) -> str:
    if nid in em.tanks:
        return "tank"
    if nid in em.pumps:
        return "submersible" if em.pumps[nid].pump_type == "submersible" else "pump"
    if nid in em.terminals:
        return "terminal"
    return "junction"


# ---------------------------------------------------------------------------
# 줌/패닝 가능한 QGraphicsView
# ---------------------------------------------------------------------------

class _ZoomableView(QGraphicsView):
    """줌/패닝 + 노드 더블클릭(편집)·노드 간 드래그(연결) 제스처."""

    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(self.renderHints().Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setStyleSheet("background:#161B22; border:none;")

        # 콜백 (TopologyViewer 가 시그널 emit 에 연결)
        self.on_node_double = None   # callable(node_id)
        self.on_connect = None       # callable(from_id, to_id)
        self._conn_start: Optional[NodeItem] = None
        self._temp_line = None

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else (1 / 1.15)
        self.scale(factor, factor)

    def _node_at(self, pos) -> Optional[NodeItem]:
        item = self.itemAt(pos)
        while item is not None:
            if isinstance(item, NodeItem):
                return item
            item = item.parentItem()
        return None

    def mouseDoubleClickEvent(self, event):
        node = self._node_at(event.position().toPoint())
        if node and callable(self.on_node_double):
            self.on_node_double(node.node_id)
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            node = self._node_at(event.position().toPoint())
            if node:
                # 노드에서 드래그 시작 → 연결 제스처 (패닝 억제)
                self._conn_start = node
                sp = self.mapToScene(event.position().toPoint())
                self._temp_line = self.scene().addLine(
                    QLineF(node.scenePos(), sp),
                    QPen(QColor("#F0A500"), 1.6, Qt.PenStyle.DashLine),
                )
                self._temp_line.setZValue(1000)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._conn_start and self._temp_line:
            sp = self.mapToScene(event.position().toPoint())
            ln = self._temp_line.line()
            self._temp_line.setLine(ln.x1(), ln.y1(), sp.x(), sp.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._conn_start is not None:
            start = self._conn_start
            target = self._node_at(event.position().toPoint())
            self._conn_start = None
            if self._temp_line is not None:
                self.scene().removeItem(self._temp_line)
                self._temp_line = None
            if target is not None and target is not start and callable(self.on_connect):
                self.on_connect(start.node_id, target.node_id)
            return
        super().mouseReleaseEvent(event)
