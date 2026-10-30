"""변경 이력 (SPEC 8 — '사용자 수동 변경 이력') — 저장할 때마다 무엇을 바꿨고 판정이 어떻게 달라졌는지 남긴다.

이력 파일: `<이름>.history.jsonl` (.ehd 옆, 한 줄 = 한 번의 저장). 항목:
  time · sha256(저장한 소스) · edits(블록 단위 추가/삭제/속성 변경) · verdict(판정 변화 요약 — impact.summary)
  · counts(저장 시점 판정 건수)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .parser import parse


def history_path(ehd_path: str) -> str:
    base, _ = os.path.splitext(ehd_path)
    return base + ".history.jsonl"


def _blocks(src: str) -> Dict[str, Tuple[str, Dict[str, str]]]:
    blocks, _ = parse(src or "")
    return {b.id: (b.type, {k: str(v).strip() for k, v in b.raw.items()}) for b in blocks}


def block_diff(old_src: str, new_src: str) -> List[dict]:
    """블록(설비·배선·시나리오…) 단위 변경 — [{id, type, change: added/removed/modified, attrs: {k: [이전, 이후]}}]."""
    a, b = _blocks(old_src), _blocks(new_src)
    out = []
    for bid in sorted(set(a) | set(b)):
        if bid not in a:
            out.append({"id": bid, "type": b[bid][0], "change": "added", "attrs": {k: [None, v] for k, v in b[bid][1].items()}})
        elif bid not in b:
            out.append({"id": bid, "type": a[bid][0], "change": "removed", "attrs": {k: [v, None] for k, v in a[bid][1].items()}})
        else:
            oa, na = a[bid][1], b[bid][1]
            ch = {k: [oa.get(k), na.get(k)] for k in sorted(set(oa) | set(na)) if oa.get(k) != na.get(k)}
            if ch or a[bid][0] != b[bid][0]:
                out.append({"id": bid, "type": b[bid][0], "change": "modified", "attrs": ch})
    return out


def describe(edit: dict) -> str:
    ch = edit.get("change", "modified")
    name = {"added": "추가", "removed": "삭제", "modified": "수정"}.get(ch, ch)
    if ch == "modified":
        parts = []
        for k, v in (edit.get("attrs") or {}).items():
            o, n = (list(v) + [None, None])[:2] if isinstance(v, (list, tuple)) else (None, v)
            parts.append(f"{k} {o if o is not None else '∅'}→{n if n is not None else '∅'}")
        return f"{edit['id']} {name}: " + ", ".join(parts)
    return f"{edit['id']}({edit.get('type', '?')}) {name}"


def make_entry(old_src: str, new_src: str, old_res=None, new_res=None, note: str = "") -> Optional[dict]:
    """저장 한 번의 이력 항목. 바뀐 것이 없으면 None."""
    from .impact import diff, summary
    edits = block_diff(old_src, new_src)
    if not edits and old_src == new_src:
        return None
    changes = diff(old_res, new_res) if (old_res is not None and new_res is not None) else []
    counts = {}
    if new_res is not None:
        for c in new_res.checks:
            counts[c.status] = counts.get(c.status, 0) + 1
    return {"time": datetime.now().isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(new_src.encode("utf-8")).hexdigest(),
            "edits": edits, "verdict": summary(changes) if changes else ("판정 변화 없음" if old_res else ""),
            "worse": [f"{c['target']} {c['title']} {c['old']}→{c['new']}" for c in changes if c["change"] == "worse"][:10],
            "counts": counts, "note": note}


def append(ehd_path: str, entry: dict) -> str:
    p = history_path(ehd_path)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return p


def load(ehd_path: Optional[str]) -> List[dict]:
    if not ehd_path:
        return []
    p = history_path(ehd_path)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue                    # 손상된 줄은 건너뛴다 (나머지 이력 보존)
                if isinstance(e, dict) and isinstance(e.get("time"), str) and isinstance(e.get("edits", []), list):
                    e["edits"] = [x for x in e.get("edits", []) if isinstance(x, dict) and "id" in x]
                    out.append(e)
    return out


def for_target(entries: List[dict], target: str) -> List[Tuple[str, str]]:
    """이 설비·배선이 바뀐 저장 시점들 — [(시각, 설명)]."""
    return [(e["time"], describe(x)) for e in entries for x in e.get("edits", []) if x.get("id") == target]


def table(entries: List[dict]) -> dict:
    t = {"title": "변경 이력 (저장 시점별 — SPEC 8)", "columns": ["시각", "변경", "판정 변화", "판정 건수"], "rows": []}
    for e in reversed(entries):
        t["rows"].append([e["time"].replace("T", " "), "; ".join(describe(x) for x in e.get("edits", [])) or "-",
                          e.get("verdict") or "-",
                          " ".join(f"{k} {v}" for k, v in sorted(e.get("counts", {}).items()))])
    return t
