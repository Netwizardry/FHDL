"""하단 콘솔용 명령 인터프리터 — 명령어로 GUI/모델을 조작한다.

GUI 메뉴·다이얼로그로 하던 작업(노드 추가/수정/삭제·연결·해석·저장)을
명령어로도 수행할 수 있게 한다. DSL 변형은 core.dsl_editor 를 재사용한다.

순수 함수 execute_command 가 (new_source, messages, action) 을 돌려주고,
GUI 는 new_source 로 에디터를 갱신하고 action(run/save/clear) 을 처리한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .dsl_editor import (
    add_link, add_node, remove_link, remove_node, remove_pipe,
    set_constraint_attributes, set_node_attributes, set_pipe_attributes,
)
from .language import COMPONENT_TYPES, NODE_TYPES


HELP_TEXT = [
    "명령어 목록:",
    "  add <tank|pump|junction|terminal> <id> [key=value ...]   노드 추가",
    "  set <id> key=value [key=value ...]                       노드/배관 속성 수정",
    "  del <id>                                                 노드(연결 포함)/배관 삭제",
    "  link <A> <B> [length=10m]                                A→B 연결(pipe+connect) 추가",
    "  unlink <A> <B>                                           A→B 연결 삭제",
    "  constraint key=value ...                                 제약(유속·안전율) 설정",
    "  ls                                                       노드/배관 목록",
    "  run | save | clear | help                                해석/저장/로그지우기/도움말",
]


@dataclass
class CommandResult:
    new_source: Optional[str] = None      # 에디터에 반영할 새 소스 (없으면 None)
    messages: List[str] = field(default_factory=list)
    action: Optional[str] = None          # 'run' | 'save' | 'clear'
    level: str = "INFO"                    # 메시지 레벨
    rerun: bool = True                     # new_source 반영 후 자동 재해석 여부


def _split_kv(tokens):
    kv, pos = {}, []
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            kv[k.strip()] = v.strip()
        else:
            pos.append(t)
    return pos, kv


def execute_command(source: str, command: str, entity_map=None) -> CommandResult:
    cmd = (command or "").strip()
    if not cmd:
        return CommandResult(rerun=False)

    parts = cmd.split()
    verb = parts[0].lower()
    pos, kv = _split_kv(parts[1:])

    def err(msg):
        return CommandResult(messages=[msg], level="ERROR", rerun=False)

    # --- 앱 액션 ---
    if verb in ("help", "h", "?"):
        return CommandResult(messages=list(HELP_TEXT), rerun=False)
    if verb == "run":
        return CommandResult(action="run", messages=["해석 실행"], level="RUN", rerun=False)
    if verb == "save":
        return CommandResult(action="save", messages=["저장"], rerun=False)
    if verb == "clear":
        return CommandResult(action="clear", rerun=False)
    if verb in ("ls", "list"):
        return _list(entity_map)

    # --- DSL 변형 ---
    if verb == "add":
        if len(pos) < 2:
            return err("사용법: add <type> <id> [key=value ...]")
        ntype, nid = pos[0].lower(), pos[1]
        if ntype not in COMPONENT_TYPES:
            return err(f"알 수 없는 타입 '{ntype}' (가능: {', '.join(COMPONENT_TYPES)})")
        if ntype == "pipe":
            start, end = kv.pop("start", ""), kv.pop("end", "")
            if not start or not end:
                return err("배관 추가는 'add pipe <id> start=A end=B ...' 형식입니다.")
            kv.setdefault("diameter", "auto")
            kv.setdefault("material", "Steel")
            attrs = {"start": start, "end": end, **kv}
            new = add_node(source, "pipe", nid, attrs)
            new = _ensure_connect(new, start, end)
            return CommandResult(new, [f"배관 '{nid}' 추가: {start} → {end}"], level="OK")
        new = add_node(source, ntype, nid, kv)
        return CommandResult(new, [f"{ntype} '{nid}' 추가"], level="OK")

    if verb == "set":
        if not pos or not kv:
            return err("사용법: set <id> key=value [...]")
        nid = pos[0]
        if entity_map is not None and nid in getattr(entity_map, "pipes", {}):
            new = set_pipe_attributes(source, nid, kv)
        else:
            new = set_node_attributes(source, nid, kv)
        if new == source:
            return err(f"'{nid}' 를 찾지 못했거나 변경 사항이 없습니다.")
        return CommandResult(new, [f"'{nid}' 수정: {', '.join(f'{k}={v}' for k,v in kv.items())}"], level="OK")

    if verb in ("del", "rm", "delete"):
        if not pos:
            return err("사용법: del <id>")
        nid = pos[0]
        if entity_map is not None and nid in getattr(entity_map, "pipes", {}):
            new = remove_pipe(source, nid)
            return CommandResult(new, [f"배관 '{nid}' 삭제"], level="WARNING")
        new = remove_node(source, nid)
        if new == source:
            return err(f"'{nid}' 를 찾지 못했습니다.")
        return CommandResult(new, [f"노드 '{nid}' 삭제(연결 포함)"], level="WARNING")

    if verb == "link":
        if len(pos) < 2:
            return err("사용법: link <A> <B> [length=10m]")
        new = add_link(source, pos[0], pos[1], length=kv.get("length", "10m"))
        return CommandResult(new, [f"연결 추가: {pos[0]} → {pos[1]}"], level="OK")

    if verb == "unlink":
        if len(pos) < 2:
            return err("사용법: unlink <A> <B>")
        new = remove_link(source, pos[0], pos[1])
        return CommandResult(new, [f"연결 삭제: {pos[0]} → {pos[1]}"], level="WARNING")

    if verb in ("constraint", "constr"):
        if not kv:
            return err("사용법: constraint velocity_max=2.5m ...")
        new = set_constraint_attributes(source, kv)
        return CommandResult(new, ["제약 조건 갱신"], level="OK")

    return err(f"알 수 없는 명령 '{verb}'. 'help' 입력.")


def _ensure_connect(source: str, a: str, b: str) -> str:
    from .dsl_editor import add_connection
    return add_connection(source, a, b)


def _list(entity_map) -> CommandResult:
    if entity_map is None:
        return CommandResult(messages=["(해석된 모델이 없습니다. 먼저 run)"], rerun=False)
    msgs = []
    nodes = []
    for t, d in (("tank", entity_map.tanks), ("pump", entity_map.pumps),
                 ("junction", entity_map.junctions), ("terminal", entity_map.terminals)):
        for nid in d:
            nodes.append(f"{nid}({t})")
    msgs.append("노드: " + (", ".join(nodes) if nodes else "(없음)"))
    pipes = [f"{p.entity_id}:{p.start_id}->{p.end_id}" for p in entity_map.pipes.values()]
    msgs.append("배관: " + (", ".join(pipes) if pipes else "(없음)"))
    return CommandResult(messages=msgs, rerun=False)
