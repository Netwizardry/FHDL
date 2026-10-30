"""FHDL 도면 생성 — 해석 결과에서 배관 도면(ISO 아이소메트릭·평면·정면)과 계통도(P&ID)를
만들고 SVG·PDF·DXF(·STEP) 로 내보낸다. core 처럼 GUI 비의존 (PDF/PNG 만 PySide6 사용).

    from fhdl.drawing import build_drawing, export_drawing
    sheet = build_drawing(result, "iso")
    export_drawing(result, "out.pdf", views=["iso", "plan", "elevation", "pid"])
"""
from __future__ import annotations

import os
from typing import Iterable, List, Optional

from .sheet import Sheet

VIEWS = ("iso", "plan", "elevation", "pid")
VIEW_NAMES = {"iso": "아이소메트릭", "plan": "평면도", "elevation": "정면도", "pid": "계통도(P&ID)"}
FORMATS = ("svg", "pdf", "dxf", "png", "step")


def build_drawing(result, view: str = "iso", project: str = "", sheet_no: str = "1/1",
                  form: str = "company") -> Sheet:
    """form: 배관 도면 양식 — "company"(도면 양식 DXF 추출, 기본) | "simple". 계통도는 간이 양식."""
    if view == "pid":
        from .pid import build_pid_sheet
        return build_pid_sheet(result, project, sheet_no)
    from .piping import build_piping_sheet
    return build_piping_sheet(result, view, project, sheet_no, form)


def build_set(result, views: Iterable[str] = VIEWS, project: str = "") -> List[Sheet]:
    views = list(views)
    return [build_drawing(result, v, project, f"{i}/{len(views)}") for i, v in enumerate(views, 1)]


def export_drawing(result, path: str, views: Optional[Iterable[str]] = None, project: str = "",
                   fmt: Optional[str] = None) -> str:
    """확장자(또는 fmt)로 형식 결정. svg/png 는 시트당 1파일(여러 장이면 _view 접미사),
    pdf 는 시트당 1페이지, dxf 는 한 파일에 나란히, step 은 3D 배관(선택 기능)."""
    fmt = (fmt or os.path.splitext(path)[1].lstrip(".")).lower()
    if fmt not in FORMATS:
        raise ValueError(f"지원하지 않는 형식: {fmt} (지원: {', '.join(FORMATS)})")
    if fmt == "step":
        from .export_step import export_step
        return export_step(result, path)["message"]
    views = list(views or (["iso"] if fmt in ("svg", "png") else VIEWS))
    sheets = build_set(result, views, project)
    if fmt == "pdf":
        from .render_qt import save_pdf
        save_pdf(sheets, path)
    elif fmt == "dxf":
        from .export_dxf import save_dxf
        save_dxf(sheets, path)
    else:
        base, ext = os.path.splitext(path)
        for v, sh in zip(views, sheets):
            p = path if len(sheets) == 1 else f"{base}_{v}{ext}"
            if fmt == "svg":
                from .export_svg import save_svg
                save_svg(sh, p)
            else:
                from .render_qt import save_png
                save_png(sh, p)
    return path
