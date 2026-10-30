"""도면 패널 — 해석 결과의 배관 도면(ISO·평면·정면)과 계통도(P&ID) 보기·내보내기.

도면은 fhdl.drawing 이 만든 Sheet 를 QGraphicsScene 으로 옮겨 그린다(장면 단위 = mm).
Inverse Sync: 토폴로지 뷰어와 같은 시그널을 낸다.
- 클릭 → entity_selected, 더블클릭 → node/pipe_double_clicked (속성 편집)
- 평면도·정면도에서 노드 드래그 → node_moved(id, {"x":…, "y"|"z":…}) → DSL 좌표 갱신
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from ...drawing import VIEW_NAMES, VIEWS, build_drawing, export_drawing
from ...drawing.sheet import LAYERS, Circle, Line, Polyline, Sheet, Text

_HL = QColor("#FF8C00")
_EXPORT_FILTERS = ("PDF 도면 전체 (*.pdf);;DXF 도면 전체 (*.dxf);;SVG 현재 도면 (*.svg);;"
                   "PNG 현재 도면 (*.png);;STEP 3D 배관 (*.step)")


class _SheetView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, panel: "DrawingPanel"):
        super().__init__(scene)
        self._panel = panel
        self.setRenderHint(self.renderHints().Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setStyleSheet("background:#3A3F47; border:none;")
        self._drag_ref: Optional[str] = None
        self._drag_start: Optional[QPointF] = None

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def _ref_at(self, pos) -> str:
        for it in self.items(pos):
            ref = it.data(0)
            if ref:
                return ref
        return ""

    def mousePressEvent(self, event):
        ref = self._ref_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and ref:
            self._panel.select(ref)
            if self._panel.can_drag(ref):
                self._drag_ref = ref
                self._drag_start = self.mapToScene(event.position().toPoint())
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_ref and self._drag_start is not None:
            d = self.mapToScene(event.position().toPoint()) - self._drag_start
            self._panel.preview_move(self._drag_ref, d)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_ref and self._drag_start is not None:
            d = self.mapToScene(event.position().toPoint()) - self._drag_start
            ref, self._drag_ref, self._drag_start = self._drag_ref, None, None
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._panel.finish_move(ref, d)
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        ref = self._ref_at(event.position().toPoint())
        if ref:
            self._panel.activate(ref)
            return
        super().mouseDoubleClickEvent(event)


class DrawingPanel(QWidget):
    entity_selected = Signal(str)
    node_double_clicked = Signal(str)
    pipe_double_clicked = Signal(str)
    node_moved = Signal(str, dict)          # 노드 ID, DSL 속성 {"x": "…", "y" 또는 "z": "…"}
    message = Signal(str, str)              # (메시지, 레벨) — 로그 콘솔용

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result = None
        self._project = ""
        self._sheet: Optional[Sheet] = None
        self._items: Dict[str, List] = {}
        self._selected = ""

        self._view_combo = QComboBox()
        for v in VIEWS:
            self._view_combo.addItem(VIEW_NAMES[v], v)
        self._view_combo.currentIndexChanged.connect(lambda _: self._rebuild())
        fit_btn = QPushButton("맞춤")
        fit_btn.clicked.connect(self.fit)
        self._export_btn = QPushButton("내보내기…")
        self._export_btn.clicked.connect(self.export_dialog)
        self._hint = QLabel("")
        self._hint.setStyleSheet("color:#8B949E;")

        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)
        bar.addWidget(QLabel("도면:"))
        bar.addWidget(self._view_combo)
        bar.addWidget(fit_btn)
        bar.addWidget(self._export_btn)
        bar.addWidget(self._hint, 1)

        self._scene = QGraphicsScene()
        self._view = _SheetView(self._scene, self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(bar)
        lay.addWidget(self._view)
        self._rebuild()

    # ------------------------------------------------------------------
    @property
    def current_view(self) -> str:
        return self._view_combo.currentData() or "iso"

    def set_view(self, view: str) -> None:
        i = self._view_combo.findData(view)
        if i >= 0:
            self._view_combo.setCurrentIndex(i)

    def update_from_result(self, result, project: str = "") -> None:
        self._result = result
        self._project = project
        self._rebuild(keep_zoom=True)

    def _rebuild(self, keep_zoom: bool = False) -> None:
        transform = self._view.transform() if keep_zoom and self._sheet else None
        self._sheet = build_drawing(self._result, self.current_view, self._project)
        self._populate(self._sheet)
        if transform is not None:
            self._view.setTransform(transform)
        else:
            self.fit()
        drag = self.current_view in ("plan", "elevation")
        self._hint.setText("클릭 선택 · 더블클릭 편집" + (" · 노드 드래그로 좌표 이동" if drag else ""))
        if self._selected:
            self.select(self._selected, emit=False)

    def _populate(self, sheet: Sheet) -> None:
        self._scene.clear()
        self._items = {}
        H = sheet.height
        self._scene.addRect(QRectF(0, 0, sheet.width, sheet.height), QPen(Qt.PenStyle.NoPen),
                            QBrush(QColor("#FFFFFF")))
        for it in sheet.items:
            color = QColor(LAYERS.get(it.layer, ("", "#000000"))[1])
            pen = QPen(color, getattr(it, "width", 0.25))
            pen.setCosmetic(False)
            gi = None
            if isinstance(it, Line):
                gi = QGraphicsLineItem(it.p1[0], H - it.p1[1], it.p2[0], H - it.p2[1])
                gi.setPen(pen)
            elif isinstance(it, Polyline):
                path = QPainterPath()
                poly = QPolygonF([QPointF(x, H - y) for x, y in it.pts])
                path.addPolygon(poly)
                if it.closed:
                    path.closeSubpath()
                gi = QGraphicsPathItem(path)
                gi.setPen(pen)
                if it.fill:
                    gi.setBrush(QBrush(color))
            elif isinstance(it, Circle):
                gi = QGraphicsEllipseItem(it.center[0] - it.r, H - it.center[1] - it.r, 2 * it.r, 2 * it.r)
                gi.setPen(pen)
                if it.fill:
                    gi.setBrush(QBrush(color))
            elif isinstance(it, Text):
                gi = QGraphicsSimpleTextItem(it.text)
                font = QFont()
                font.setPixelSize(20)
                gi.setFont(font)
                gi.setBrush(QBrush(color))
                k = it.height * 1.25 / 20.0
                br = gi.boundingRect()
                dx = {"start": 0.0, "middle": -br.width() / 2, "end": -br.width()}.get(it.anchor, 0.0)
                dy = {"baseline": -br.height() * 0.8, "middle": -br.height() / 2,
                      "top": 0.0}.get(it.valign, 0.0)
                gi.setTransformOriginPoint(0, 0)
                gi.setPos(it.pos[0], H - it.pos[1])
                gi.setScale(k)
                gi.setRotation(-it.angle)
                gi.setPos(gi.pos() + gi.mapToParent(QPointF(dx, dy)) - gi.mapToParent(QPointF(0, 0)))
            if gi is None:
                continue
            ref = getattr(it, "ref", "")
            if ref:
                gi.setData(0, ref)
                gi.setCursor(Qt.CursorShape.PointingHandCursor)
                self._items.setdefault(ref, []).append(gi)
            self._scene.addItem(gi)
        self._scene.setSceneRect(QRectF(-10, -10, sheet.width + 20, sheet.height + 20))

    def fit(self) -> None:
        if self._sheet:
            self._view.fitInView(QRectF(0, 0, self._sheet.width, self._sheet.height),
                                 Qt.AspectRatioMode.KeepAspectRatio)

    # ------------------------------------------------------------------
    # 선택·편집 (Inverse Sync)
    # ------------------------------------------------------------------
    def _is_node(self, ref: str) -> bool:
        em = getattr(self._result, "entity_map", None)
        return bool(em) and em.get_node_entity(ref) is not None

    def select(self, ref: str, emit: bool = True) -> None:
        for gi in self._items.get(self._selected, []):
            self._recolor(gi, None)
        self._selected = ref
        for gi in self._items.get(ref, []):
            self._recolor(gi, _HL)
        if emit and ref:
            self.entity_selected.emit(ref)

    def _recolor(self, gi, color: Optional[QColor]) -> None:
        if color is None:
            orig = gi.data(1)
            if orig is None:
                return
            color = orig
        elif gi.data(1) is None:
            src = gi.brush().color() if isinstance(gi, QGraphicsSimpleTextItem) else gi.pen().color()
            gi.setData(1, QColor(src))
        if isinstance(gi, QGraphicsSimpleTextItem):
            gi.setBrush(QBrush(color))
            return
        pen = gi.pen()
        pen.setColor(color)
        gi.setPen(pen)
        if hasattr(gi, "brush") and gi.brush().style() != Qt.BrushStyle.NoBrush:
            gi.setBrush(QBrush(color))

    def activate(self, ref: str) -> None:
        if self._is_node(ref):
            self.node_double_clicked.emit(ref)
        else:
            self.pipe_double_clicked.emit(ref)

    def can_drag(self, ref: str) -> bool:
        return (self.current_view in ("plan", "elevation") and self._is_node(ref)
                and self._sheet is not None and self._sheet.fit is not None)

    def preview_move(self, ref: str, d: QPointF) -> None:
        for gi in self._items.get(ref, []):
            base = gi.data(2)
            if base is None:
                gi.setData(2, gi.pos())
                base = gi.pos()
            gi.setPos(base + d)

    def finish_move(self, ref: str, d: QPointF) -> None:
        for gi in self._items.get(ref, []):
            if gi.data(2) is not None:
                gi.setPos(gi.data(2))
                gi.setData(2, None)
        if abs(d.x()) < 0.8 and abs(d.y()) < 0.8:
            return                                  # 단순 클릭
        attrs = self.moved_attrs(ref, d.x(), -d.y())
        if attrs:
            self.node_moved.emit(ref, attrs)

    def moved_attrs(self, ref: str, dx_mm: float, dy_mm: float) -> Dict[str, str]:
        """용지 위 이동량(mm, y 위쪽) → DSL 좌표 속성. 평면도 = (x, y), 정면도 = (x, z)."""
        em = self._result.entity_map
        ent = em.get_node_entity(ref)
        scale = self._sheet.fit[0]
        if ent is None or scale <= 0:
            return {}
        dx, dy = dx_mm / scale, dy_mm / scale
        attrs = {"x": f"{ent.x + dx:.1f}"}
        if self.current_view == "plan":
            attrs["y"] = f"{ent.y + dy:.1f}"
        else:
            attrs["z"] = f"{ent.elevation + dy:.2f}m"
            attrs.setdefault("y", f"{ent.y:.1f}")
        return attrs

    # ------------------------------------------------------------------
    def export_dialog(self) -> None:
        if self._result is None or getattr(self._result, "entity_map", None) is None:
            self.message.emit("도면 내보내기: 먼저 해석을 실행하세요.", "WARNING")
            return
        base = os.path.join(os.path.expanduser("~"), f"{self._project or 'fhdl'}_drawing")
        path, flt = QFileDialog.getSaveFileName(self, "도면 내보내기", base, _EXPORT_FILTERS)
        if not path:
            return
        ext = flt.split("*.")[-1].rstrip(")")
        if not path.lower().endswith("." + ext):
            path += "." + ext
        self.export(path)

    def export(self, path: str, views: Optional[List[str]] = None) -> str:
        """views 생략 시: svg/png = 현재 도면, pdf/dxf = 전체(ISO·평면·정면·P&ID)."""
        if self._result is None or getattr(self._result, "entity_map", None) is None:
            self.message.emit("도면 내보내기: 먼저 해석을 실행하세요.", "WARNING")
            return ""
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if views is None and ext in ("svg", "png"):
            views = [self.current_view]
        try:
            msg = export_drawing(self._result, path, views=views, project=self._project)
        except Exception as e:  # 파일 쓰기·의존성 오류를 로그로
            self.message.emit(f"도면 내보내기 실패: {e}", "ERROR")
            return ""
        self.message.emit(f"도면 내보내기: {msg}", "OK")
        return msg
