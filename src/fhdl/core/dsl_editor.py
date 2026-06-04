"""DSL 텍스트 인플레이스 편집 유틸 (Inverse Sync 기반).

GUI(토폴로지 뷰)에서 발생한 편집 의도를 FHDL 소스 텍스트에 반영한다.
파서를 거치지 않고 텍스트를 직접 조작하므로, 사용자의 주석·서식·순서를
최대한 보존한다. 모든 함수는 부수효과 없는 순수 함수이며 새 소스를 반환한다.

지원:
- set_node_attributes : 노드 블록의 속성값 교체/추가 (속성 편집 · 좌표 역반영)
- add_connection / remove_connection : connect 문 추가/삭제
- add_pipe / remove_pipe : pipe 블록 추가/삭제
- add_link / remove_link : pipe + connect 를 한 쌍으로 추가/삭제 (드래그 연결)
"""
from __future__ import annotations

import re
from typing import Dict, Optional

_NODE_TYPES = ("tank", "pump", "junction", "terminal")


# ---------------------------------------------------------------------------
# 노드 블록 속성 편집
# ---------------------------------------------------------------------------

def _find_node_block(source: str, node_id: str) -> Optional[re.Match]:
    """node_id 의 블록을 찾아 Match 반환 (group1=헤더+{, group2=본문, group3=})."""
    types = "|".join(_NODE_TYPES)
    pattern = re.compile(
        rf"(\b(?:{types})\s+{re.escape(node_id)}\s*\{{)(.*?)(\}})",
        re.DOTALL,
    )
    return pattern.search(source)


def set_node_attributes(source: str, node_id: str, attrs: Dict[str, str]) -> str:
    """노드 블록의 속성을 교체(없으면 추가)한다.

    attrs 값은 단위를 포함한 문자열 그대로 기록된다. 예: {"z": "12m", "x": "5"}.
    값이 빈 문자열인 키는 건드리지 않는다(미입력 보존).
    """
    m = _find_node_block(source, node_id)
    if not m:
        return source

    head, body, tail = m.group(1), m.group(2), m.group(3)
    indent = _detect_indent(body)

    for key, value in attrs.items():
        if value is None or value == "":
            continue
        body = _set_attr_in_body(body, key, str(value), indent)

    new_block = head + body + tail
    return source[:m.start()] + new_block + source[m.end():]


def _detect_indent(body: str) -> str:
    for line in body.splitlines():
        stripped = line.lstrip(" \t")
        if stripped and "=" in stripped:
            return line[: len(line) - len(stripped)]
    return "    "


def _set_attr_in_body(body: str, key: str, value: str, indent: str) -> str:
    """본문 내 `key = ...;` 를 교체, 없으면 추가."""
    attr_re = re.compile(rf"(^|\n)([ \t]*){re.escape(key)}\s*=\s*[^;\n]*;",
                         re.MULTILINE)
    replacement = rf"\g<1>\g<2>{key} = {value};"
    new_body, n = attr_re.subn(replacement, body)
    if n:
        return new_body

    # 미존재 → 닫는 중괄호 직전에 추가
    insertion = f"{indent}{key} = {value};\n"
    if body.endswith("\n"):
        return body + insertion
    return body + "\n" + insertion


# ---------------------------------------------------------------------------
# connect 문 편집
# ---------------------------------------------------------------------------

def _has_connection(source: str, from_id: str, to_id: str) -> bool:
    pat = re.compile(
        rf"\bconnect\b[^;]*\b{re.escape(from_id)}\b\s*->\s*\b{re.escape(to_id)}\b",
    )
    return bool(pat.search(source))


def add_connection(source: str, from_id: str, to_id: str) -> str:
    """`connect from -> to;` 추가 (이미 있으면 그대로)."""
    if _has_connection(source, from_id, to_id):
        return source
    line = f"connect {from_id} -> {to_id};"
    sep = "" if source.endswith("\n") else "\n"
    return source + sep + line + "\n"


def remove_connection(source: str, from_id: str, to_id: str) -> str:
    """단순 `connect from -> to;` 문을 제거한다 (해당 줄만)."""
    pat = re.compile(
        rf"^[ \t]*connect\s+{re.escape(from_id)}\s*->\s*{re.escape(to_id)}\s*;[ \t]*\n?",
        re.MULTILINE,
    )
    return pat.sub("", source)


# ---------------------------------------------------------------------------
# pipe 블록 편집
# ---------------------------------------------------------------------------

def default_pipe_id(start: str, end: str) -> str:
    return f"pipe_{start}_{end}"


def add_pipe(source: str, pipe_id: str, start: str, end: str,
             length: str = "10m", diameter: str = "auto",
             material: str = "Steel") -> str:
    """pipe 블록을 추가한다 (같은 id 가 있으면 그대로)."""
    if _find_pipe_block(source, pipe_id):
        return source
    block = (
        f"pipe {pipe_id} {{\n"
        f"    start = {start};\n"
        f"    end = {end};\n"
        f"    length = {length};\n"
        f"    diameter = {diameter};\n"
        f"    material = {material};\n"
        f"}}\n"
    )
    sep = "" if source.endswith("\n") else "\n"
    return source + sep + block


def _find_pipe_block(source: str, pipe_id: str) -> Optional[re.Match]:
    pattern = re.compile(rf"(\bpipe\s+{re.escape(pipe_id)}\s*\{{)(.*?)(\}})\s*\n?",
                         re.DOTALL)
    return pattern.search(source)


def set_pipe_attributes(source: str, pipe_id: str, attrs: Dict[str, str]) -> str:
    """pipe 블록의 속성을 교체(없으면 추가)한다 (length/diameter/material/k_factor 등)."""
    m = _find_pipe_block(source, pipe_id)
    if not m:
        return source
    head, body, tail = m.group(1), m.group(2), m.group(3)
    indent = _detect_indent(body)
    for key, value in attrs.items():
        if value is None or value == "":
            continue
        body = _set_attr_in_body(body, key, str(value), indent)
    return source[:m.start()] + head + body + tail + source[m.end(3):]


def remove_pipe(source: str, pipe_id: str) -> str:
    m = _find_pipe_block(source, pipe_id)
    if not m:
        return source
    return source[:m.start()] + source[m.end():]


# ---------------------------------------------------------------------------
# 연결(드래그) = pipe + connect 한 쌍
# ---------------------------------------------------------------------------

def add_node(source: str, ntype: str, node_id: str, attrs: Dict[str, str]) -> str:
    """노드 블록을 새로 추가한다 (같은 id 가 이미 있으면 그대로)."""
    if _find_node_block(source, node_id):
        return source
    lines = [f"{ntype} {node_id} {{"]
    for key, value in attrs.items():
        if value not in (None, ""):
            lines.append(f"    {key} = {value};")
    lines.append("}")
    block = "\n".join(lines) + "\n"
    sep = "" if source.endswith("\n") else "\n"
    return source + sep + block


def remove_node(source: str, node_id: str) -> str:
    """노드 블록과 그 노드에 연결된 배관·connect 문을 함께 제거한다.

    - tank/pump/junction/terminal 블록 삭제
    - start 또는 end 가 node_id 인 pipe 블록 삭제
    - node_id 가 포함된 connect 문 삭제
    """
    # 1) 노드에 연결된 배관 id 수집 후 pipe 블록·connect 제거
    types = "|".join(_NODE_TYPES)
    pipe_iter = re.finditer(
        r"\bpipe\s+(\w+)\s*\{(.*?)\}", source, re.DOTALL)
    related_pipes = []
    for m in pipe_iter:
        body = m.group(2)
        if re.search(rf"\bstart\s*=\s*{re.escape(node_id)}\b", body) or \
           re.search(rf"\bend\s*=\s*{re.escape(node_id)}\b", body):
            related_pipes.append(m.group(1))
    for pid in related_pipes:
        source = remove_pipe(source, pid)

    # 2) 노드 블록 삭제
    block_re = re.compile(
        rf"\b(?:{types})\s+{re.escape(node_id)}\s*\{{.*?\}}\s*\n?", re.DOTALL)
    source = block_re.sub("", source)

    # 3) connect 문에서 node_id (및 삭제된 pipe id) 가 든 줄 제거
    drop_ids = {node_id, *related_pipes}
    out_lines = []
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("connect"):
            tokens = re.split(r"->|\s|;", stripped)
            if any(tok in drop_ids for tok in tokens if tok):
                continue
        out_lines.append(line)
    return "".join(out_lines)


def set_constraint_attributes(source: str, attrs: Dict[str, str]) -> str:
    """constraint 블록의 속성을 교체/추가한다. 블록이 없으면 새로 만든다."""
    m = re.search(r"(\bconstraint\s*\{)(.*?)(\})", source, re.DOTALL)
    if m:
        head, body, tail = m.group(1), m.group(2), m.group(3)
        indent = _detect_indent(body)
        for key, value in attrs.items():
            if value is None or value == "":
                continue
            body = _set_attr_in_body(body, key, str(value), indent)
        return source[:m.start()] + head + body + tail + source[m.end():]
    # 미존재 → 새 블록 추가
    lines = ["constraint {"]
    for key, value in attrs.items():
        if value:
            lines.append(f"    {key} = {value};")
    lines.append("}")
    block = "\n".join(lines) + "\n"
    sep = "" if source.endswith("\n") else "\n"
    return source + sep + block


def has_link(source: str, start: str, end: str,
             pipe_id: Optional[str] = None) -> bool:
    """start→end 연결(connect 또는 pipe 블록)이 존재하는지."""
    pid = pipe_id or default_pipe_id(start, end)
    return _has_connection(source, start, end) or bool(_find_pipe_block(source, pid))


def add_link(source: str, start: str, end: str,
             pipe_id: Optional[str] = None, length: str = "10m") -> str:
    """노드 간 연결을 pipe 블록 + connect 문으로 함께 추가한다."""
    pid = pipe_id or default_pipe_id(start, end)
    source = add_pipe(source, pid, start, end, length=length)
    source = add_connection(source, start, end)
    return source


def remove_link(source: str, start: str, end: str,
                pipe_id: Optional[str] = None) -> str:
    """노드 간 연결(pipe + connect)을 함께 제거한다."""
    pid = pipe_id or default_pipe_id(start, end)
    source = remove_pipe(source, pid)
    source = remove_connection(source, start, end)
    return source
