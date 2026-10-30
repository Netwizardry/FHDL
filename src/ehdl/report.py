"""EHDL 보고서 — SPEC 12 산출물 B~F (+ 병목). JSON(기계 판독) · CSV(표별) · PDF(사람용).

B 설비 요구규격표   각 설비·배선의 계산 요구조건
C 설계 검산표       요구 vs 실제 규격, 사용률, 판정, 적용 기준(원문 쪽)
D 운전 시나리오 분석표  시나리오별 정격 설비 사용률
E 설계 근거 분석표  요구·선정 규격, 여유율, 선정 근거
F 발주자 검토 질문서  설계자에게 물을 질문과 그 계산 근거
모든 행은 노드/배선 ID 를 첫 칸에 두어 그래프 위치와 연결된다.
"""
from __future__ import annotations

import csv
import datetime as _dt
import html
import json
import os
from typing import Dict, List

from .judge import bottlenecks
from .model import EResult
from .units import fmt

_CAP_KINDS = ("source_limit", "transformer_rating", "board_rating", "breaker_load", "cable_ampacity")


def _rule(c) -> str:
    r = c.evidence.rule
    if not r:
        return c.evidence.formula
    return f"{r.title} — {r.citation or r.clause}" + ("" if r.verified else " [원문 미확인]")


def tables(res: EResult) -> Dict[str, dict]:
    m = res.model
    B = {"title": "B. 설비 요구규격표", "columns": ["ID", "설비", "요구조건", "계산 근거", "운전 조건"], "rows": []}
    C = {"title": "C. 설계 검산표", "columns": ["ID", "항목", "요구", "실제 규격", "사용률", "판정", "적용 기준"], "rows": []}
    E = {"title": "E. 설계 근거 분석표", "columns": ["ID", "항목", "최대 예상", "선정 규격", "여유율", "선정 근거", "판정"],
         "rows": []}
    F = {"title": "F. 발주자 검토 질문서", "columns": ["ID", "판정", "질문", "계산 근거"], "rows": []}
    for c in res.checks:
        name = (m.nodes[c.target].name if c.target in m.nodes else c.target)
        if c.required is not None:
            B["rows"].append([c.target, name, c.required.text(), c.evidence.formula, c.evidence.scenario])
        if c.kind != "sizing_rationale":
            shown = c.actual if c.kind == "breaker_cable_coord" else c.installed   # 협조: 실제 = 배선 Iz
            C["rows"].append([c.target, c.title, c.required.text() if c.required else "-",
                              fmt(shown, c.unit) if shown is not None else "-",
                              f"{c.utilization * 100:.0f}%" if c.utilization is not None else "-",
                              c.status, _rule(c)])
        if c.kind in _CAP_KINDS and c.installed is not None and c.actual is not None:
            just = (m.nodes[c.target].justification if c.target in m.nodes else
                    m.edges[c.target].justification if c.target in m.edges else "")
            rat = next((x for x in res.checks if x.id == f"{c.target}:sizing_rationale"), None)
            E["rows"].append([c.target, c.title, fmt(c.actual, c.unit), fmt(c.installed, c.unit),
                              f"{(1 - c.utilization) * 100:.0f}%" if c.utilization is not None else "-",
                              just or "(없음)", rat.status if rat else c.status])
        for q in c.questions:
            F["rows"].append([c.target, c.status, q, c.explanation])
    D = {"title": "D. 운전 시나리오 분석표", "columns": ["ID", "정격"] + list(res.scenarios), "rows": []}
    for nid, n in m.nodes.items():
        rated = n.installed.get("rated_current") or n.installed.get("rated") or n.installed.get("limit_kw")
        if not rated:
            continue
        cells = []
        for sid, sr in res.scenarios.items():
            r = sr.nodes.get(nid)
            if r is None:
                cells.append("-")
                continue
            v = r.current if n.installed.get("rated_current") else (r.S if n.installed.get("rated") else r.P_max)
            cells.append(f"{v / rated * 100:.0f}%" if v is not None else "?")
        unit = "A" if n.installed.get("rated_current") else ("VA" if n.installed.get("rated") else "W")
        D["rows"].append([nid, fmt(rated, unit, 0)] + cells)
    EA = {"title": "접지·고장보호 (Phase 3)", "columns": ["ID", "항목", "계산", "기준", "판정", "적용 기준"], "rows": []}
    for c in res.checks:
        if c.kind in ("fault_protection", "pe_size", "bonding", "main_bonding", "tnc_rcd", "it_first_fault"):
            EA["rows"].append([c.target, c.title, fmt(c.actual, c.unit) if c.actual is not None else "-",
                               c.required.text() if c.required else "-", c.status, _rule(c)])
    SU = {"title": "수전 종합 — 설비용량 · 최대수요전력 · 계약전력 · 변압기 (SPEC 5.12)", "columns": ["항목", "값"],
          "rows": []}
    for c in res.checks:
        if c.kind == "supply_summary":
            SU["rows"] = [[k, f"{v:g}"] for k, v in c.evidence.values.items()] + [["판정", c.status]]
    G = {"title": "병목 (FAIL 경로)", "columns": ["ID", "초과 조건", "운전 조건", "원인 부하", "전원까지 경로"], "rows": []}
    for b in bottlenecks(res):
        G["rows"].append([b["target"], b["check"], b["scenario"], ", ".join(b["causes"]), " → ".join(b["path"])])
    from .mixed import mixed_impact
    MX = {"title": "혼합 모드 — 신규 부하 추가 전·후 기존 설비 (SPEC 4.3)",
          "columns": ["ID", "항목", "정격", "신규 전", "신규 후", "사용률 전→후", "결과", "신규 부하"], "rows": []}
    for r in mixed_impact(res):
        MX["rows"].append([r["target"], r["title"], fmt(r["installed"], r["unit"]), fmt(r["before"], r["unit"]),
                           fmt(r["after"], r["unit"]), f"{r['util_before'] * 100:.0f}% → {r['util_after'] * 100:.0f}%",
                           r["verdict"], ", ".join(r["new_loads"])])
    return {"B": B, "C": C, "D": D, "E": E, "F": F, "EARTH": EA, "SUPPLY": SU, "MIXED": MX, "BOTTLENECK": G}


def impact_table(changes) -> dict:
    t = {"title": "설계 변경 영향 (이전 해석 대비)", "columns": ["ID", "항목", "변화", "이전", "현재", "이전 값", "현재 값"],
         "rows": []}
    names = {"worse": "악화", "better": "개선", "value": "값 변화", "added": "추가", "removed": "삭제"}
    for d in changes:
        t["rows"].append([d["target"], d["title"], names[d["change"]], d["old"] or "-", d["new"] or "-",
                          fmt(d["old_value"], d["unit"]) if d["old_value"] is not None else "-",
                          fmt(d["new_value"], d["unit"]) if d["new_value"] is not None else "-"])
    return t


def summary(res: EResult) -> dict:
    counts = {s: sum(1 for c in res.checks if c.status == s) for s in ("FAIL", "UNKNOWN", "REVIEW", "PASS", "N/A")}
    rules = getattr(res, "rules", None)
    return {"system": res.model.name, "design_scenario": res.design_scenario, "counts": counts,
            "rules": getattr(rules, "version", ""), "generated": _dt.datetime.now().isoformat(timespec="seconds"),
            "diagnostics": [f"{d.code} {d.severity} {d.message}" for d in res.diagnostics]}


def export_report(res: EResult, path: str, project: str = "", baseline: EResult = None, history=None) -> str:
    """baseline 을 주면 설계 변경 영향 표, history(변경 이력 항목)를 주면 변경 이력 표를 함께 넣는다."""
    ext = os.path.splitext(path)[1].lower()
    tb = tables(res)
    if history:
        from .history import table as history_table
        tb["HISTORY"] = history_table(history)
    if baseline is not None:
        from .impact import diff
        tb["IMPACT"] = impact_table(diff(baseline, res))
    if ext == ".json":
        data = {"summary": summary(res), "tables": tb,
                "checks": [{"id": c.id, "target": c.target, "kind": c.kind, "status": c.status,
                            "required": c.required.text() if c.required else None, "actual": c.actual,
                            "installed": c.installed, "unit": c.unit, "utilization": c.utilization,
                            "explanation": c.explanation, "questions": c.questions, "missing": c.missing,
                            "evidence": {"inputs": c.evidence.inputs, "formula": c.evidence.formula,
                                         "values": c.evidence.values, "scenario": c.evidence.scenario,
                                         "assumptions": c.evidence.assumptions, "defaults": c.evidence.defaults,
                                         "rule": (c.evidence.rule.__dict__ if c.evidence.rule else None)}}
                           for c in res.checks]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return path
    if ext == ".csv":
        base = os.path.splitext(path)[0]
        written = []
        for key, t in tb.items():
            p = f"{base}_{key}.csv"
            with open(p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(t["columns"])
                w.writerows(t["rows"])
            written.append(p)
        return ", ".join(os.path.basename(p) for p in written)
    if ext in (".pdf", ".html", ".htm"):
        doc = report_html(res, project, tb)
        if ext != ".pdf":
            with open(path, "w", encoding="utf-8") as f:
                f.write(doc)
            return path
        from fhdl.drawing.render_qt import ensure_app
        ensure_app()
        from PySide6.QtCore import QMarginsF
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
        from fhdl.drawing.render_qt import check_writable
        check_writable(path)
        w = QPdfWriter(path)
        w.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape,
                                    QMarginsF(12, 12, 12, 12)))
        w.setTitle("EHDL 검산 보고서")
        w.setResolution(96)                    # 문서 배치는 화면 해상도 기준 — print_ 가 쪽을 나눈다
        d = QTextDocument()
        d.setHtml(doc)
        d.print_(w)
        from fhdl.drawing.render_qt import ensure_written
        return ensure_written(path)
    raise ValueError(f"지원하지 않는 보고서 형식: {ext} (pdf, html, csv, json)")


_ST_COLOR = {"FAIL": "#D0021B", "UNKNOWN": "#E67E22", "REVIEW": "#B7950B", "PASS": "#1E8449", "N/A": "#7F8C8D"}


def report_html(res: EResult, project: str = "", tb=None) -> str:
    tb = tb or tables(res)
    s = summary(res)
    head = (f"<h1>EHDL 검산 보고서 — {html.escape(project or s['system'])}</h1>"
            f"<p>생성 {s['generated']} · 판정 기준 운전 조건 <b>{s['design_scenario']}</b> · 적용 기준 "
            f"{html.escape(s['rules'])}</p><p>"
            + " · ".join(f"<span style='color:{_ST_COLOR[k]}'><b>{k}</b> {v}</span>" for k, v in s["counts"].items())
            + "</p><p><i>이 보고서는 설계 근거의 가시화·검산용이며 제품 선정·시공·적산 문서가 아니다. "
              "REVIEW 는 '추가 확인 필요'이고 과대 설계라는 단정이 아니다.</i></p>")
    parts = [head]
    for key in ("BOTTLENECK", "MIXED", "IMPACT", "C", "EARTH", "SUPPLY", "B", "D", "E", "F", "HISTORY"):
        if key not in tb:
            continue
        t = tb[key]
        if not t["rows"]:
            continue
        rows = []
        for r in t["rows"]:
            cells = []
            for v in r:
                v = html.escape(str(v))
                if v in _ST_COLOR:
                    v = f"<b style='color:{_ST_COLOR[v]}'>{v}</b>"
                cells.append(f"<td>{v}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        parts.append(f"<h2>{html.escape(t['title'])}</h2><table border=1 cellspacing=0 cellpadding=3 width='100%'>"
                     "<tr>" + "".join(f"<th bgcolor='#E8E8E8'>{html.escape(c)}</th>" for c in t["columns"]) + "</tr>"
                     + "".join(rows) + "</table>")
    if s["diagnostics"]:
        parts.append("<h2>진단</h2><ul>" + "".join(f"<li>{html.escape(d)}</li>" for d in s["diagnostics"]) + "</ul>")
    return "<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;font-size:9pt} "\
           "h1{font-size:15pt} h2{font-size:11pt;margin-top:14px} td,th{font-size:8pt}</style></head><body>" \
           + "".join(parts) + "</body></html>"
