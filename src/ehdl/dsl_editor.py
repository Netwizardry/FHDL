"""EHDL DSL 인플레이스 편집 (Inverse Sync) — 그래프·명령 콘솔의 편집을 DSL 텍스트에 반영.

DSL 이 단일 진실원(결정 D1)이므로 모든 편집은 텍스트를 고친 새 텍스트를 돌려준다.
블록 구조·주석·순서를 보존하고 대상 속성 줄만 바꾼다.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from .language import BLOCK_TYPES


def _block(source: str, bid: str) -> Optional[re.Match]:
    return re.search(rf"\b({'|'.join(BLOCK_TYPES)})\s+{re.escape(bid)}\s*\{{([^}}]*)\}}", source)


def block_type(source: str, bid: str) -> Optional[str]:
    m = _block(source, bid)
    return m.group(1) if m else None


def _indent(body: str) -> str:
    for ln in body.splitlines():
        s = ln.lstrip(" \t")
        if s and "=" in s:
            return ln[: len(ln) - len(s)]
    return "    "


def _fmt_value(v: str) -> str:
    v = str(v).strip()
    if v and (" " in v or any(c in v for c in ";{}")) and not v.startswith(("\"", "[")):
        return '"' + v.replace('"', '\\"') + '"'
    return v


_VAL = r'(?:"(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^;\n]*)'


def _attr_re(key: str):
    return re.compile(rf"(?<![\w]){re.escape(key)}\s*=\s*{_VAL}\s*;")


def _remove_attr(body: str, key: str) -> str:
    m = _attr_re(key).search(body)
    if not m:
        return body
    s, e = m.span()
    while e < len(body) and body[e] in " \t":
        e += 1
    ls = body.rfind("\n", 0, s) + 1
    le = body.find("\n", e)
    le = len(body) if le < 0 else le
    if body[ls:s].strip() == "" and body[e:le].strip() == "" and "\n" in body[ls:]:
        return body[:ls] + body[le + 1:]                       # 그 속성만 있던 줄 통째로
    return body[:s] + body[e:]


def set_attrs(source: str, bid: str, attrs: Dict[str, str]) -> str:
    """블록의 속성을 바꾸거나 추가한다. 값이 None 이면 그 속성을 지우고, '' 이면 건드리지 않는다.
    대상 'key = value;' 부분만 바꾸므로 주석·들여쓰기·다른 속성은 그대로다."""
    m = _block(source, bid)
    if not m:
        return source
    body = m.group(2)
    one_line = "\n" not in body
    ind = _indent(body)
    for key, value in attrs.items():
        if value is None:
            body = _remove_attr(body, key)
            continue
        if value == "":
            continue
        val = _fmt_value(value)
        rx = _attr_re(key)
        if rx.search(body):
            body = rx.sub(lambda _m: f"{key} = {val};", body, count=1)
        elif one_line:
            body = body.rstrip() + f" {key} = {val}; "
        else:
            head = body.rstrip(" \t")
            if not head.endswith("\n"):
                head += "\n"
            body = head + f"{ind}{key} = {val};\n"
    start, end = m.span(2)
    return source[:start] + body + source[end:]


def add_block(source: str, btype: str, bid: str, attrs: Dict[str, str]) -> str:
    if _block(source, bid):
        return source
    inner = "".join(f"    {k} = {_fmt_value(v)};\n" for k, v in attrs.items() if v not in (None, ""))
    sep = "" if source.endswith("\n\n") or not source else ("\n" if source.endswith("\n") else "\n\n")
    return f"{source}{sep}{btype} {bid} {{\n{inner}}}\n"


def remove_block(source: str, bid: str, cascade: bool = True) -> str:
    """블록 삭제. cascade 면 이 설비를 끝점으로 하는 배선도 지우고, parent/feed 참조를 끊는다."""
    m = _block(source, bid)
    if not m:
        return source
    s, e = m.span()
    while e < len(source) and source[e] in " \t":
        e += 1
    if e < len(source) and source[e] == "\n":
        e += 1
    out = source[:s] + source[e:]
    if cascade:
        for cm in list(re.finditer(r"\bcable\s+(\w+)\s*\{([^}]*)\}", out)):
            if re.search(rf"\b(from|to)\s*=\s*{re.escape(bid)}\s*;", cm.group(2)):
                out = remove_block(out, cm.group(1), cascade=False)
        for bm in list(re.finditer(rf"\b({'|'.join(BLOCK_TYPES)})\s+(\w+)\s*\{{([^}}]*)\}}", out)):
            for ref in ("parent", "feed"):
                if re.search(rf"(?<![\w]){ref}\s*=\s*{re.escape(bid)}\s*;", bm.group(3)):
                    out = set_attrs(out, bm.group(2), {ref: None})
    return out


def add_cable(source: str, cable_id: str, frm: str, to: str, attrs: Dict[str, str]) -> str:
    return add_block(source, "cable", cable_id, {"from": frm, "to": to, **attrs})


def unique_id(source: str, base: str) -> str:
    i = 1
    while _block(source, f"{base}{i}"):
        i += 1
    return f"{base}{i}"
