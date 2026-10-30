"""Sheet → QPainter 렌더링 (PDF·PNG 내보내기와 GUI 도면 보기가 공유).

PySide6 는 이 모듈 안에서만 가져온다 — drawing 패키지의 나머지는 GUI 비의존.
"""
from __future__ import annotations

from typing import Optional

from .sheet import LAYERS, Circle, Line, Polyline, Sheet, Text


def ensure_app():
    """QPainter 글꼴 처리를 위해 Qt 앱 객체가 필요하다 (없으면 생성).

    QGuiApplication 이 아니라 QApplication 을 만든다 — 같은 프로세스에서 나중에
    위젯(GUI)을 만들 때 QGuiApplication 이 있으면 Qt 가 중단(abort)된다.
    """
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        import os
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])
    return app


def paint_sheet(painter, sheet: Sheet, px_per_mm: float, highlight: Optional[set] = None) -> None:
    """painter 좌표 = 픽셀(원점 좌상단). 용지 mm → 픽셀 변환은 여기서 한다."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF

    k = px_per_mm
    H = sheet.height

    def pt(p):
        return QPointF(p[0] * k, (H - p[1]) * k)

    painter.fillRect(QRectF(0, 0, sheet.width * k, sheet.height * k), QColor("#FFFFFF"))
    painter.setRenderHint(painter.RenderHint.Antialiasing, True)
    hl = highlight or set()
    for it in sheet.items:
        color = QColor(LAYERS.get(it.layer, ("", "#000000"))[1])
        if hl and getattr(it, "ref", "") in hl:
            color = QColor("#FF8C00")
        pen = QPen(color, max(getattr(it, "width", 0.25) * k, 0.6))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(color) if getattr(it, "fill", False) else Qt.BrushStyle.NoBrush)
        if isinstance(it, Line):
            painter.drawLine(pt(it.p1), pt(it.p2))
        elif isinstance(it, Polyline):
            poly = QPolygonF([pt(p) for p in it.pts])
            if it.closed:
                painter.drawPolygon(poly)
            else:
                painter.drawPolyline(poly)
        elif isinstance(it, Circle):
            painter.drawEllipse(pt(it.center), it.r * k, it.r * k)
        elif isinstance(it, Text):
            font = QFont()
            font.setPixelSize(max(int(round(it.height * k * 1.25)), 1))
            painter.setFont(font)
            fm = painter.fontMetrics()
            w = fm.horizontalAdvance(it.text)
            dx = {"start": 0.0, "middle": -w / 2, "end": -w}.get(it.anchor, 0.0)
            dy = {"baseline": 0.0, "middle": (fm.ascent() - fm.descent()) / 2,
                  "top": float(fm.ascent())}.get(it.valign, 0.0)
            painter.save()
            painter.translate(pt(it.pos))
            if it.angle:
                painter.rotate(-it.angle)
            painter.drawText(QPointF(dx, dy), it.text)
            painter.restore()


def save_png(sheet: Sheet, path: str, px_per_mm: float = 6.0) -> str:
    ensure_app()
    from PySide6.QtGui import QImage, QPainter
    img = QImage(int(sheet.width * px_per_mm), int(sheet.height * px_per_mm), QImage.Format.Format_RGB32)
    painter = QPainter(img)
    paint_sheet(painter, sheet, px_per_mm)
    painter.end()
    img.save(path)
    return path


def save_pdf(sheets, path: str) -> str:
    """하나 이상의 Sheet 를 A3 가로 PDF(벡터)로 저장한다. 페이지 = 시트."""
    ensure_app()
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
    if isinstance(sheets, Sheet):
        sheets = [sheets]
    first = sheets[0]
    writer = QPdfWriter(path)
    writer.setResolution(300)
    size = QPageSize(QSizeF(first.width, first.height), QPageSize.Unit.Millimeter, "FHDL")
    writer.setPageLayout(QPageLayout(size, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
    writer.setTitle(first.title)
    writer.setCreator("FHDL")
    painter = QPainter(writer)
    px_per_mm = 300 / 25.4
    for i, sh in enumerate(sheets):
        if i:
            writer.newPage()
        paint_sheet(painter, sh, px_per_mm)
    painter.end()
    return path
