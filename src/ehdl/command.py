"""EHDL 하단 콘솔 명령 — GUI 작업을 명령으로 (FHDL command.py 와 같은 형식·동작).

순수 함수 execute_command 가 (new_source, messages, action, args) 를 돌려주고 GUI 가 반영한다.
DSL 변형은 ehdl.dsl_editor 를 재사용한다.
"""
from __future__ import annotations

import re
from typing import Optional

from fhdl.core.command import CommandResult, _split_kv

from .dsl_editor import add_block, add_cable, block_type, remove_block, set_attrs, unique_id
from .language import BLOCK_TYPES, EDGE_TYPES, NODE_TYPES

HELP_TEXT = [
    "명령어 목록:",
    "  add <종류> <id> [key=value ...]        설비 추가 (종류: " + ", ".join(NODE_TYPES) + ")",
    "  set <id> key=value [...]               설비·배선 속성 수정 (key=- 이면 속성 삭제)",
    "  del <id>                               설비(연결 배선 포함)·배선 삭제",
    "  link <A> <B> [length=20m ...]          A→B 배선(cable) 추가",
    "  scenario <id> on=A,B [off=C]           운전 시나리오 추가",
    "  why <id>                               이 설비 판정의 근거·질문",
    "  impact                                 직전 해석 대비 판정 변화 (설계 변경 영향)",
    "  history [id]                           저장 시점별 변경 이력 (설비 지정 시 그 설비만)",
    "  import <파일.dxf>                      DXF 전기 설계도 가져오기 (부하 일람표·CABLE SCHEDULE·단선결선도)",
    "  ls                                     설비·배선 목록",
    "  dwg [export <파일.pdf|svg|dxf|png>]     계통 구성도 보기/내보내기",
    "  report <파일.pdf|csv|json>             검산 보고서 (요구규격·검산·시나리오·근거·질문서)",
    "  run | save | clear | help              해석/저장/로그지우기/도움말",
]


def execute_command(source: str, command: str, result=None) -> CommandResult:
    cmd = (command or "").strip()
    if not cmd:
        return CommandResult(rerun=False)
    import shlex
    try:
        parts = shlex.split(cmd, posix=True)          # name="펌프 1" 처럼 따옴표 값 보존
    except ValueError as e:
        return CommandResult(messages=[f"명령을 해석할 수 없습니다: {e} (따옴표 짝 확인)"], level="ERROR", rerun=False)
    if not parts:
        return CommandResult(rerun=False)
    verb = parts[0].lower()
    pos, kv = _split_kv(parts[1:])

    def err(msg):
        return CommandResult(messages=[msg], level="ERROR", rerun=False)

    if verb in ("help", "h", "?"):
        return CommandResult(messages=list(HELP_TEXT), rerun=False)
    if verb in ("run", "save", "clear"):
        return CommandResult(action=verb, messages=[{"run": "해석 실행", "save": "저장", "clear": ""}[verb]],
                             level="RUN" if verb == "run" else "INFO", rerun=False)
    if verb in ("ls", "list"):
        return _list(result)
    if verb == "why":
        return _why(result, pos[0] if pos else "")
    if verb == "impact":
        return CommandResult(action="impact", messages=[], rerun=False)
    if verb == "import":
        if not pos or not pos[0].lower().endswith(".dxf"):
            return err("사용법: import <파일.dxf>")
        return CommandResult(action="import", args={"path": pos[0]}, messages=[f"DXF 가져오기 ← {pos[0]}"], rerun=False)
    if verb == "history":
        return CommandResult(action="history", args={"id": pos[0] if pos else ""}, messages=[], rerun=False)
    if verb == "add":
        if len(pos) < 2:
            return err("사용법: add <종류> <id> [key=value ...]")
        t, nid = pos[0].lower(), pos[1]
        if not re.fullmatch(r"\w+", nid):
            return err(f"ID '{nid}' 에는 영문·숫자·_ 만 쓸 수 있습니다 (표시 이름은 name=…)")
        if t not in BLOCK_TYPES or t == "system":
            return err(f"알 수 없는 종류 '{t}' (가능: {', '.join(t for t in BLOCK_TYPES if t != 'system')})")
        if block_type(source, nid):
            return err(f"'{nid}' 는 이미 있습니다.")
        return CommandResult(add_block(source, t, nid, kv), [f"{t} '{nid}' 추가"], level="OK")
    if verb == "set":
        if not pos or not kv:
            return err("사용법: set <id> key=value [...]")
        attrs = {k: (None if v == "-" else v) for k, v in kv.items()}
        new = set_attrs(source, pos[0], attrs)
        if new == source:
            return err(f"'{pos[0]}' 를 찾지 못했거나 바뀐 것이 없습니다.")
        return CommandResult(new, [f"'{pos[0]}' 수정: " + ", ".join(f"{k}={v}" for k, v in kv.items())], level="OK")
    if verb in ("del", "rm", "delete"):
        if not pos:
            return err("사용법: del <id>")
        new = remove_block(source, pos[0])
        if new == source:
            return err(f"'{pos[0]}' 를 찾지 못했습니다.")
        return CommandResult(new, [f"'{pos[0]}' 삭제 (연결 배선·소속 참조 포함)"], level="WARNING")
    if verb == "link":
        if len(pos) < 2:
            return err("사용법: link <A> <B> [length=20m material=Cu size=16mm2 ...]")
        for x in pos[:2]:
            if not block_type(source, x):
                return err(f"'{x}' 가 없습니다.")
        cid = kv.pop("id", None) or unique_id(source, f"C_{pos[1]}_")
        return CommandResult(add_cable(source, cid, pos[0], pos[1], kv), [f"배선 '{cid}' 추가: {pos[0]} → {pos[1]}"],
                             level="OK")
    if verb == "scenario":
        if not pos:
            return err("사용법: scenario <id> on=A,B [off=C]")
        attrs = {k: "[" + ", ".join(x for x in v.split(",") if x) + "]" for k, v in kv.items() if k in ("on", "off")}
        new = (set_attrs(source, pos[0], attrs) if block_type(source, pos[0]) == "scenario"
               else add_block(source, "scenario", pos[0], attrs))
        return CommandResult(new, [f"시나리오 '{pos[0]}' 갱신"], level="OK")
    if verb in ("dwg", "drawing"):
        if pos and pos[0].lower() == "export" and len(pos) >= 2:
            return CommandResult(action="drawing", args={"path": pos[1]}, messages=[f"계통 구성도 → {pos[1]}"],
                                 rerun=False)
        return CommandResult(action="drawing", args={}, messages=["계통 구성도 보기"], rerun=False)
    if verb == "report":
        if not pos:
            return err("사용법: report <파일.pdf|csv|json>")
        return CommandResult(action="report", args={"path": pos[0]}, messages=[f"보고서 → {pos[0]}"], rerun=False)
    return err(f"알 수 없는 명령 '{verb}'. 'help' 입력.")


def _list(result) -> CommandResult:
    m = getattr(result, "model", None)
    if m is None:
        return CommandResult(messages=["(해석된 모델이 없습니다. 먼저 run)"], rerun=False)
    nodes = ", ".join(f"{n.id}({NODE_TYPES[n.type][0]})" for n in m.nodes.values())
    cables = ", ".join(f"{e.id}:{e.from_id}->{e.to_id}" for e in m.edges.values())
    return CommandResult(messages=[f"설비: {nodes or '(없음)'}", f"배선: {cables or '(없음)'}"], rerun=False)


def _why(result, target: str) -> CommandResult:
    if result is None or not target:
        return CommandResult(messages=["사용법: why <id> (먼저 run)"], level="ERROR", rerun=False)
    cs = result.checks_for(target)
    if not cs:
        return CommandResult(messages=[f"'{target}' 에 대한 판정이 없습니다."], rerun=False)
    msgs = []
    for c in cs:
        msgs.append(f"[{c.status}] {c.title}: {c.explanation}")
        if c.evidence.formula:
            msgs.append(f"    식: {c.evidence.formula}")
        if c.evidence.rule:
            msgs.append(f"    기준: {c.evidence.rule.title} — {c.evidence.rule.citation or c.evidence.rule.clause}")
        for q in c.questions:
            msgs.append(f"    질문: {q}")
    worst = result.node_status(target)
    level = {"FAIL": "ERROR", "UNKNOWN": "WARNING", "REVIEW": "WARNING"}.get(worst, "OK")
    return CommandResult(messages=msgs, level=level, rerun=False)
