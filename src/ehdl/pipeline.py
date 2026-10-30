"""EHDL 분석 파이프라인: Parse → Semantic → Solve → Judge (예외 없이 EResult 반환).

같은 입력과 같은 규칙 버전은 같은 결과를 낸다 (SPEC 9.2) — 난수·시각·순서 의존 없음.
"""
from __future__ import annotations

from fhdl.core.models import DiagnosticItem, SourceSpan

from .engine import solve
from .judge import judge
from .model import EResult
from .parser import parse
from .rules import load_ruleset
from .semantic import Analyzer


def analyze(source: str) -> EResult:
    blocks, diags = parse(source)
    if any(d.is_blocking for d in diags):
        return EResult(status="FAILED", diagnostics=diags)
    model, sem = Analyzer().analyze(blocks)
    diags += sem
    if any(d.is_blocking for d in diags):
        return EResult(status="FAILED", model=model, diagnostics=diags)
    try:
        rules = load_ruleset(str(model.settings.get("rules") or "kec_lv"))
    except (OSError, KeyError, ValueError) as e:
        diags.append(DiagnosticItem("ESEM007", "ERROR", f"규칙 세트를 읽지 못했습니다: {e}", SourceSpan()))
        return EResult(status="FAILED", model=model, diagnostics=diags)
    try:
        return _solve_judge(model, rules, diags)
    except Exception as e:                       # 최후 방어선 — analyze 는 예외를 던지지 않는다
        diags.append(DiagnosticItem("EINT001", "FATAL", f"내부 오류로 해석을 끝내지 못했습니다: {type(e).__name__}: {e}",
                                    SourceSpan(), suggested_action="입력 값을 확인하세요. 계속되면 입력과 함께 보고해 주세요."))
        return EResult(status="FAILED", model=model, diagnostics=diags)


def _solve_judge(model, rules, diags) -> EResult:
    res = solve(model, rules, diags)
    res.diagnostics = diags
    if any(d.is_blocking for d in diags):
        res.status = "FAILED"
        return res
    from .kb import KB, DEFAULT_DB
    import os
    kb = KB(os.environ.get("EHDL_KB", DEFAULT_DB))
    from .shortcircuit import compute as short_circuit
    res.design_scenario = "max_demand" if "max_demand" in res.scenarios else "normal"
    res.sc = short_circuit(res, rules)
    res.checks = judge(res, rules, kb)
    res.rules = rules
    res.design_scenario = "max_demand" if "max_demand" in res.scenarios else "normal"
    res.status = "OK"
    return res
