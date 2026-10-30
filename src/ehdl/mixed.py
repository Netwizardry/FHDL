"""혼합 모드 (SPEC 4.3) — 기존 설비 규격은 고정, 신규 부하(stage = new)를 더했을 때 무엇이 병목이 되는가.

'existing' 시나리오(신규 부하 제외)와 판정 시나리오(신규 포함)의 같은 양을 비교해, 기존 설비마다
신규 부하 추가 전·후 사용률과 '신규 부하로 초과'(병목) 여부를 낸다. 신규 설비는 요구규격 산정 대상이다.
"""
from __future__ import annotations

from typing import List

from .model import EResult

_QTY = {"board_rating": "current", "breaker_load": "current", "cable_ampacity": "current",
        "transformer_rating": "S", "source_limit": None}


def _value(res: EResult, sid: str, c) -> float:
    m = res.model
    node = c.target if c.target in m.nodes else m.edges[c.target].to_id
    r = res.scenarios[sid].nodes.get(node)
    if r is None:
        return None
    q = _QTY[c.kind] or ("P" if c.unit == "W" else "S")
    return r.current if q == "current" else (r.P if q == "P" else r.S)


def is_mixed(res: EResult) -> bool:
    return "existing" in res.scenarios


def mixed_impact(res: EResult) -> List[dict]:
    """기존 설비의 용량 검사마다 신규 부하 전·후 비교. 혼합 모드가 아니면 []."""
    if not is_mixed(res):
        return []
    m = res.model
    out = []
    for c in res.checks:
        if c.kind not in _QTY or c.installed is None or c.actual is None:
            continue
        ent = m.nodes.get(c.target) or m.edges.get(c.target)
        if ent is None or ent.stage != "existing":
            continue
        before = _value(res, "existing", c)
        after = c.actual
        if before is None or abs(after - before) <= 1e-9 * max(abs(after), 1.0):
            continue                                    # 신규 부하가 지나가지 않는 설비
        if after > c.installed and before <= c.installed:
            verdict = "신규 부하로 초과"
        elif after > c.installed:
            verdict = "기존 상태에서 이미 초과"
        else:
            verdict = "여유 내"
        out.append({"target": c.target, "check": c.id, "title": c.title, "unit": c.unit, "installed": c.installed,
                    "before": before, "after": after, "util_before": before / c.installed,
                    "util_after": after / c.installed, "verdict": verdict,
                    "new_loads": [i for i, _ in c.evidence.contributors if m.nodes.get(i) is not None
                                  and i not in res.scenarios["existing"].on_loads]})
    return out


def annotate(res: EResult) -> None:
    """신규 부하로 초과한 FAIL 의 설명·질문에 혼합 모드 정보를 덧붙인다."""
    for row in mixed_impact(res):
        if row["verdict"] != "신규 부하로 초과":
            continue
        c = next(x for x in res.checks if x.id == row["check"])
        new = ", ".join(row["new_loads"]) or "신규 부하"
        c.evidence.values["신규 부하 전 사용률(%)"] = round(row["util_before"] * 100, 1)
        c.explanation += (f" 기존 상태에서는 사용률 {row['util_before'] * 100:.0f}% 로 여유가 있었으나 신규 부하({new}) 추가로 "
                          f"{row['util_after'] * 100:.0f}% 가 되어 이 기존 설비가 병목입니다.")
        c.questions.append(f"신규 부하({new}) 를 다른 계통으로 옮기거나 기존 {c.target} 를 증설하는 방안을 검토하셨나요?")
