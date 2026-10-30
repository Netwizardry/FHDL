"""FHDL 수리 계산 보고서 (R-FR-012 · 13_REPORTING) — HTML / PDF.

머리말(엔진 버전·마찰 모델·유체 물성·소스 SHA-256·수렴), 요약(총유량·요구/권장 양정·최불리 경로),
노드·배관 결과 표, 진단, 적용한 기본값을 한 문서로 낸다. 표시 단위는 unit_system 을 따른다.
CSV·JSON(report_generator) 과 같은 결과를 쓴다.
"""
from __future__ import annotations

import hashlib
import html
import os
from datetime import datetime

from .models import AnalysisResult
from .units import display_units


def header_info(result: AnalysisResult, source: str = "") -> dict:
    from .. import __version__
    em = result.entity_map
    f = em.fluid if em else None
    s = result.summary
    return {
        "engine": f"FHDL {__version__}",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": result.status,
        "friction_model": (f.friction_model if f else "-"),
        "fluid": (f.fluid_type if f else "-"),
        "temp_c": (f.temp if f else None),
        "density": (round(f.density, 2) if f else None),
        "kinematic_viscosity": (f.kinematic_viscosity if f else None),
        "altitude_m": (f.altitude if f else None),
        "unit_system": (f.unit_system if f else "METRIC"),
        "pipe_standard": (em.constraints.pipe_standard if em else "KS"),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest() if source else "",
        "converged": s.converged, "iterations": s.solve_iterations, "residual_m": s.residual,
    }


def _table(cols, rows) -> str:
    return ("<table border=1 cellspacing=0 cellpadding=3 width='100%'><tr>"
            + "".join(f"<th bgcolor='#E8E8E8'>{html.escape(c)}</th>" for c in cols) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>" for r in rows)
            + "</table>")


def report_html(result: AnalysisResult, source: str = "", project: str = "") -> str:
    h = header_info(result, source)
    u = display_units(h["unit_system"])
    fq, lq = u["flow"]
    fp, lp = u["press"]
    fl, ll = u["length"]
    fd, ld = u["dia"]
    s = result.summary
    lengths = {p.entity_id: p.length for p in result.entity_map.pipes.values()} if result.entity_map else {}
    parts = [f"<h1>FHDL 수리 계산 보고서 — {html.escape(project or '-')}</h1>",
             _table(["항목", "값"], [
                 ["엔진", h["engine"]], ["생성", h["generated"]], ["해석 상태", h["status"]],
                 ["마찰 모델", h["friction_model"]],
                 ["유체", f"{h['fluid']} {h['temp_c']:g}°C · ρ {h['density']:g} kg/m³ · ν {h['kinematic_viscosity']:.3e} m²/s"
                  if h["density"] else "-"],
                 ["기준 해발", f"{h['altitude_m']:g} m" if h["altitude_m"] is not None else "-"],
                 ["관경 표준", h["pipe_standard"]],
                 ["수렴", f"{'예' if h['converged'] else '아니오'} · 반복 {h['iterations']} · 잔차 {h['residual_m']:.2e} m"],
                 ["소스 SHA-256", h["source_sha256"] or "-"]]),
             "<h2>요약</h2>",
             _table(["항목", "값"], [
                 ["총 유량", f"{s.total_flow * fq:.2f} {lq}"],
                 ["요구 양정", f"{s.required_head * fl:.2f} {ll}"],
                 ["권장 펌프", f"{s.recommended_pump_flow * fq:.2f} {lq} · {s.recommended_pump_head * fl:.2f} {ll}"],
                 ["권장 탱크 용량", f"{s.recommended_tank_volume:.2f} m³"],
                 ["최불리 경로", " → ".join(s.worst_path) or "-"]])]
    parts.append("<h2>노드</h2>" + _table(
        ["ID", "종류", "z(m)", f"수두({ll})", f"압력({lp})", f"유입({lq})", "NPSHa(m)"],
        [[n.node_id, n.node_type, f"{n.z:g}", f"{n.head_total * fl:.3f}", f"{n.p_gauge * fp:.4f}",
          f"{n.flow_in * fq:.2f}", f"{n.npsha:.2f}" if n.node_type == "pump" else "-"] for n in result.node_results]))
    parts.append("<h2>배관</h2>" + _table(
        ["ID", "구간", f"관경({ld})", "산정", f"길이({ll})", f"유량({lq})", "유속(m/s)", "마찰(m)", "국부(m)", "K",
         "수충격 지수", "상태"],
        [[p.pipe_id, f"{p.start_id}→{p.end_id}", f"{p.diameter * fd:.1f}", p.sizing_mode,
          f"{(p.length or lengths.get(p.pipe_id, 0)) * fl:.2f}", f"{p.flow * fq:.2f}", f"{p.velocity:.3f}",
          f"{p.h_loss_f:.3f}", f"{p.h_loss_k:.3f}", f"{p.k_total:.2f}", f"{p.surge_index:.2f}", p.status]
         for p in result.pipe_results]))
    if result.diagnostics:
        parts.append("<h2>진단</h2>" + _table(
            ["코드", "심각도", "내용", "줄"],
            [[d.code, d.severity, d.message, d.source_span.line or "-"] for d in result.diagnostics]))
    if result.entity_map and result.entity_map.defaults_applied:
        parts.append("<h2>적용한 기본값 (입력 없음)</h2>" + _table(
            ["항목", "값", "대상"],
            [[w, v, ", ".join(ids)] for (w, v), ids in result.entity_map.defaults_applied.items()]))
    parts.append("<p><i>국부 손실은 입력한 부속(fittings·k_factor)과 경로 꺾임 자동 엘보만 반영한다. "
                 "결과는 설계 검토용이며 시공 문서가 아니다.</i></p>")
    return ("<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;font-size:9pt} "
            "h1{font-size:15pt} h2{font-size:11pt;margin-top:14px} td,th{font-size:8pt}</style></head><body>"
            + "".join(parts) + "</body></html>")


def export_calc_report(result: AnalysisResult, path: str, source: str = "", project: str = "") -> str:
    ext = os.path.splitext(path)[1].lower()
    doc = report_html(result, source, project)
    if ext in (".html", ".htm"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        return path
    if ext != ".pdf":
        raise ValueError(f"지원하지 않는 보고서 형식: {ext} (pdf, html)")
    from ..drawing.render_qt import ensure_app
    ensure_app()
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    w = QPdfWriter(path)
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape,
                                QMarginsF(12, 12, 12, 12)))
    w.setTitle("FHDL 수리 계산 보고서")
    w.setResolution(96)
    d = QTextDocument()
    d.setHtml(doc)
    d.print_(w)
    return path
