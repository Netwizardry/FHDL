"""설계 변경 영향 분석 (SPEC 원칙 8, Phase 3) — 이전 해석과 현재 해석의 판정·값 차이.

같은 검사 ID 끼리 비교해 상태 변화, 값 변화(상대 0.5% 이상), 새로 생기거나 없어진 검사를 돌려준다.
변경된 설비에서 전원 쪽으로 영향이 번진 경로(상위 설비 값 변화)도 이 목록에 그대로 나타난다.
"""
from __future__ import annotations

from typing import Dict, List

from .model import EResult

_RANK = {"FAIL": 0, "UNKNOWN": 1, "REVIEW": 2, "PASS": 3, "N/A": 4}


def diff(old: EResult, new: EResult, rel_tol: float = 0.005) -> List[dict]:
    if old is None or new is None or not old.checks or not new.checks:
        return []
    a: Dict[str, object] = {c.id: c for c in old.checks}
    b: Dict[str, object] = {c.id: c for c in new.checks}
    out = []
    for cid in sorted(set(a) | set(b)):
        ca, cb = a.get(cid), b.get(cid)
        if ca is None or cb is None:
            c = cb or ca
            out.append({"id": cid, "target": c.target, "title": c.title, "change": "added" if cb else "removed",
                        "old": None if cb else ca.status, "new": cb.status if cb else None,
                        "old_value": None, "new_value": cb.actual if cb else None, "unit": c.unit})
            continue
        changed_status = ca.status != cb.status
        va, vb = ca.actual, cb.actual
        changed_value = (va is None) != (vb is None) or (
            va is not None and vb is not None and abs(vb - va) > rel_tol * max(abs(va), abs(vb), 1e-9))
        if changed_status or changed_value:
            trend = ("worse" if _RANK[cb.status] < _RANK[ca.status] else
                     "better" if _RANK[cb.status] > _RANK[ca.status] else "value")
            out.append({"id": cid, "target": cb.target, "title": cb.title, "change": trend, "old": ca.status,
                        "new": cb.status, "old_value": va, "new_value": vb, "unit": cb.unit})
    order = {"worse": 0, "added": 1, "better": 2, "value": 3, "removed": 4}
    return sorted(out, key=lambda d: (order[d["change"]], d["id"]))


def summary(changes: List[dict]) -> str:
    if not changes:
        return "판정 변화 없음"
    w = sum(1 for c in changes if c["change"] == "worse")
    b = sum(1 for c in changes if c["change"] == "better")
    v = sum(1 for c in changes if c["change"] == "value")
    head = [f"{c['target']} {c['title']} {c['old']}→{c['new']}" for c in changes if c["change"] == "worse"][:3]
    return f"변경 영향: 악화 {w} · 개선 {b} · 값 변화 {v}" + (" — " + "; ".join(head) if head else "")
