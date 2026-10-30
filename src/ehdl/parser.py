"""EHDL DSL 파서 — 텍스트 → 블록 목록 (예외 없이 진단으로 오류 반환).

문법 (FHDL 과 같은 블록 형식):

    <종류> <ID> { 속성 = 값; ... }

종류: language.BLOCK_TYPES. 값: 수치+단위(37kW), 문자열("..."), 목록([A, B]), 이름(Cu).
주석: // 행, /* */ 블록.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union

from fhdl.core.models import DiagnosticItem, SourceSpan

from .language import BLOCK_TYPES

Value = Union[str, List[str]]


@dataclass
class Block:
    type: str
    id: str
    attrs: Dict[str, Value] = field(default_factory=dict)
    raw: Dict[str, str] = field(default_factory=dict)
    span: SourceSpan = field(default_factory=SourceSpan)


_BLOCK = re.compile(r"\b(" + "|".join(BLOCK_TYPES) + r")\s+(\w+)\s*\{([^}]*)\}", re.DOTALL)
_ATTR = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^;]+?)\s*;')
_WORD = re.compile(r"\b(\w+)\s+(\w+)\s*\{")


def _strip_comments(text: str) -> str:
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group())
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", blank, text)


def _span(src: str, start: int, end: int) -> SourceSpan:
    line = src.count("\n", 0, start) + 1
    col = start - (src.rfind("\n", 0, start) + 1)
    end_line = src.count("\n", 0, end) + 1
    end_col = end - (src.rfind("\n", 0, end) + 1)
    return SourceSpan(line=line, col=col, end_line=end_line, end_col=end_col)


def parse(source: str) -> Tuple[List[Block], List[DiagnosticItem]]:
    diags: List[DiagnosticItem] = []
    clean = _strip_comments(source)
    blocks: List[Block] = []
    covered: List[Tuple[int, int]] = []
    for m in _BLOCK.finditer(clean):
        span = _span(source, m.start(), m.end())
        b = Block(type=m.group(1), id=m.group(2), span=span)
        body = m.group(3)
        for a in _ATTR.finditer(body):
            key, raw = a.group(1).lower(), a.group(2).strip()
            if key in b.attrs:
                diags.append(DiagnosticItem("ESYN002", "WARNING",
                                            f"'{b.id}' 의 속성 '{key}' 가 두 번 지정되었습니다 (뒤의 값 사용).",
                                            span, b.id, "중복된 속성을 지우세요."))
            b.raw[key] = raw
            if raw.startswith('"'):
                b.attrs[key] = bytes(raw[1:-1], "utf-8").decode("unicode_escape") if "\\" in raw else raw[1:-1]
            elif raw.startswith("["):
                b.attrs[key] = [t.strip() for t in raw[1:-1].split(",") if t.strip()]
            else:
                b.attrs[key] = raw
        leftover = _ATTR.sub("", body).strip()
        if leftover:
            diags.append(DiagnosticItem("ESYN001", "ERROR",
                                        f"'{b.id}' 블록에서 해석할 수 없는 내용: '{leftover[:40]}'",
                                        span, b.id, "속성은 '이름 = 값;' 형식으로 쓰고 끝에 ; 를 붙이세요."))
        blocks.append(b)
        covered.append((m.start(), m.end()))
    # 알 수 없는 블록 종류
    for m in _WORD.finditer(clean):
        if any(s <= m.start() < e for s, e in covered):
            continue
        if m.group(1) not in BLOCK_TYPES:
            diags.append(DiagnosticItem("ESYN003", "ERROR", f"알 수 없는 블록 종류 '{m.group(1)}'",
                                        _span(source, m.start(), m.end()), m.group(2),
                                        f"사용 가능: {', '.join(BLOCK_TYPES)}"))
    if not blocks and source.strip():
        diags.append(DiagnosticItem("ESYN001", "ERROR", "인식된 블록이 없습니다.", SourceSpan(), "",
                                    "예: load M1 { rating = 37kW; ... }"))
    return blocks, diags
