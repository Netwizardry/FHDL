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


_LEX = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


def mask(text: str) -> str:
    """구조 찾기용 사본 (길이·줄 위치 보존): 주석은 공백, 문자열 안 글자는 '_'.
    문자열 안의 // · { } · ; 가 주석·블록 경계로 오인되지 않는다."""
    def sub(m):
        g = m.group()
        if g.startswith('"'):
            return '"' + re.sub(r"[^\n]", "_", g[1:-1]) + '"'
        return re.sub(r"[^\n]", " ", g)
    return _LEX.sub(sub, text)


def _strip_comments(text: str) -> str:
    """주석만 지운 사본(문자열은 그대로) — 하위 호환."""
    return _LEX.sub(lambda m: m.group() if m.group().startswith('"') else re.sub(r"[^\n]", " ", m.group()), text)


_ESC = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}


def unquote(raw: str) -> str:
    """'"펌프 \\"A\\""' → 펌프 "A" — \\" \\\\ \\n \\t 만 풀고 나머지는 글자 그대로 (한글 안전)."""
    return re.sub(r'\\(["\\nt])', lambda m: _ESC[m.group(1)], raw[1:-1])


def _span(src: str, start: int, end: int) -> SourceSpan:
    line = src.count("\n", 0, start) + 1
    col = start - (src.rfind("\n", 0, start) + 1)
    end_line = src.count("\n", 0, end) + 1
    end_col = end - (src.rfind("\n", 0, end) + 1)
    return SourceSpan(line=line, col=col, end_line=end_line, end_col=end_col)


def parse(source: str) -> Tuple[List[Block], List[DiagnosticItem]]:
    diags: List[DiagnosticItem] = []
    clean = mask(source)
    blocks: List[Block] = []
    covered: List[Tuple[int, int]] = []
    for m in _BLOCK.finditer(clean):
        span = _span(source, m.start(), m.end())
        b = Block(type=m.group(1), id=m.group(2), span=span)
        body = m.group(3)
        off = m.start(3)
        for a in _ATTR.finditer(body):
            key = a.group(1).lower()
            raw = source[off + a.start(2): off + a.end(2)].strip()           # 값은 원문에서 (문자열 내용 보존)
            if key in b.attrs:
                diags.append(DiagnosticItem("ESYN002", "WARNING",
                                            f"'{b.id}' 의 속성 '{key}' 가 두 번 지정되었습니다 (뒤의 값 사용).",
                                            span, b.id, "중복된 속성을 지우세요."))
            b.raw[key] = raw
            if raw.startswith('"'):
                b.attrs[key] = unquote(raw)
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
    # 블록 밖에 남은 글자 — 하이픈 ID('panel LP-1 {'), 중괄호 없는 블록 등은 조용히 버리지 않는다
    rest = list(clean)
    for s, e in covered:
        rest[s:e] = " " * (e - s)
    for m in re.finditer(r"[^\s;]+(?:[^\n;{}]*\{[^}]*\}|[^\n;]*;?)", "".join(rest)):
        frag = m.group().strip()
        if not frag:
            continue
        if any(d.code == "ESYN003" and _span(source, m.start(), m.end()).line == d.source_span.line for d in diags):
            continue
        hy = re.match(r"(\w+)\s+([\w-]*-[\w-]*)\s*\{", frag)
        msg = (f"ID '{hy.group(2)}' 에는 '-' 를 쓸 수 없습니다 — '{hy.group(2).replace('-', '_')}' 처럼 '_' 를 쓰세요 "
               "(표시 이름은 name 속성)" if hy and hy.group(1) in BLOCK_TYPES
               else f"블록으로 해석할 수 없는 내용: '{frag[:40]}'")
        diags.append(DiagnosticItem("ESYN001", "ERROR", msg, _span(source, m.start(), m.end()), "",
                                    "형식: <종류> <ID> { 속성 = 값; ... }  (ID 는 영문·숫자·_)"))
    if not blocks and source.strip():
        diags.append(DiagnosticItem("ESYN001", "ERROR", "인식된 블록이 없습니다.", SourceSpan(), "",
                                    "예: load M1 { rating = 37kW; ... }"))
    return blocks, diags
