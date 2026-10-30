"""EHDL 의미 분석 — 블록 → SystemModel (단위 정규화·참조 검사). 값을 지어내지 않는다.

진단 코드 (docs/ehdl/DIAGNOSTICS.md):
  ESEM001 중복 ID · ESEM002 정의되지 않은 참조 · ESEM003 값/단위 오류 · ESEM004 알 수 없는 속성
  ESEM005 선택지 밖의 값 · ESEM006 포함 관계(parent) 순환
"""
from __future__ import annotations

import math

from typing import Dict, List, Optional, Set

from fhdl.core.models import DiagnosticItem

from .language import (
    EDGE_ATTRS, EDGE_TYPES, GROUP_ATTRS, NODE_ATTRS, NODE_TYPES, SCENARIO_ATTRS, SYSTEM_ATTRS, Attr,
)
from .model import EEdge, ENode, Group, Scenario, SystemModel
from .parser import Block
from .units import parse_quantity

_COMMON_KEYS = {"name", "parent", "feed", "justification", "stage"}


class Analyzer:

    def analyze(self, blocks: List[Block]):
        self.d: List[DiagnosticItem] = []
        m = SystemModel()
        seen: Set[str] = set()
        for b in blocks:
            if b.type != "system" and b.id in seen:
                self._err("ESEM001", f"ID '{b.id}' 가 중복 정의되었습니다.", b, "ID 는 계통 전체에서 하나여야 합니다.")
                continue
            if b.type != "system":
                seen.add(b.id)
            if b.type == "system":
                m.name = b.id
                m.settings = self._values(b, SYSTEM_ATTRS)
            elif b.type in NODE_TYPES:
                m.nodes[b.id] = self._node(b)
            elif b.type in EDGE_TYPES:
                m.edges[b.id] = self._edge(b)
            elif b.type == "group":
                v = self._values(b, GROUP_ATTRS)
                m.groups[b.id] = Group(b.id, v.get("max_on"), b.span)
            elif b.type == "scenario":
                v = self._values(b, SCENARIO_ATTRS)
                on = v.get("on")
                m.scenarios[b.id] = Scenario(b.id, set(on) if on is not None else None,
                                             set(v.get("off") or []), span=b.span)
        self._check_refs(m, blocks)
        return m, self.d

    # ------------------------------------------------------------------
    def _node(self, b: Block) -> ENode:
        spec = NODE_ATTRS[b.type]
        n = ENode(b.id, b.type, str(b.attrs.get("name", b.id)), span=b.span)
        n.parent = b.attrs.get("parent") or None
        n.feed = b.attrs.get("feed") or None
        n.justification = str(b.attrs.get("justification", ""))
        n.stage = self._stage(b)
        vals = self._values(b, spec, n.unit_kinds)
        for k, v in vals.items():
            (n.installed if spec[k].role == "installed" else n.params)[k] = v
        return n

    def _edge(self, b: Block) -> EEdge:
        spec = EDGE_ATTRS[b.type]
        e = EEdge(b.id, b.type, str(b.attrs.get("from", "")), str(b.attrs.get("to", "")), span=b.span)
        e.justification = str(b.attrs.get("justification", ""))
        e.stage = self._stage(b)
        for k, v in self._values(b, spec).items():
            if spec[k].role == "link":
                continue
            (e.installed if spec[k].role == "installed" else e.params)[k] = v
        return e

    def _stage(self, b: Block) -> str:
        from .language import STAGES
        raw = str(b.attrs.get("stage", "existing")).lower()
        if raw not in STAGES:
            self._err("ESEM005", f"'{b.id}' 의 stage = {raw} 은(는) 허용 값이 아닙니다.", b, "가능: existing, new")
            return "existing"
        return raw

    def _values(self, b: Block, spec: Dict[str, Attr], kinds: Optional[dict] = None) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for key, raw in b.attrs.items():
            if key in _COMMON_KEYS:
                continue
            a = spec.get(key)
            if a is None:
                self._warn("ESEM004", f"'{b.id}' 의 '{key}' 는 {b.type} 에 없는 속성입니다 (무시).", b,
                           f"사용 가능: {', '.join(spec) or '-'}")
                continue
            v = self._convert(b, key, raw, a, kinds)
            if v is not None:
                out[key] = v
        return out

    def _convert(self, b: Block, key: str, raw, a: Attr, kinds):
        if a.kind in ("text",):
            return str(raw)
        if a.kind in ("id", "link"):
            return str(raw)
        if a.kind == "ids":
            return list(raw) if isinstance(raw, list) else [str(raw)]
        if a.kind == "enum":
            val = str(raw)
            match = next((c for c in a.choices if c.lower() == val.lower()), None)
            if match is None:
                self._err("ESEM005", f"'{b.id}' 의 {key} = {val} 은(는) 허용 값이 아닙니다.", b,
                          f"가능: {', '.join(a.choices)}")
            return match
        if a.kind == "number":
            try:
                v = float(str(raw))
            except ValueError:
                v = float("nan")
            if not math.isfinite(v):
                self._err("ESEM003", f"'{b.id}' 의 {key} 는 유한한 수치여야 합니다: '{raw}'", b)
                return None
            if v <= 0:
                self._err("ESEM003", f"'{b.id}' 의 {key} 는 0 보다 커야 합니다.", b)
                return None
            return v
        if a.kind == "int":
            try:
                fv = float(str(raw))
            except ValueError:
                fv = float("nan")
            if not math.isfinite(fv) or fv != int(fv) or fv < 1:
                self._err("ESEM003", f"'{b.id}' 의 {key} 는 1 이상의 정수여야 합니다: '{raw}'", b)
                return None
            v = int(fv)
            if a.choices and str(v) not in a.choices:
                self._err("ESEM005", f"'{b.id}' 의 {key} = {v} 은(는) 허용 값이 아닙니다.", b,
                          f"가능: {', '.join(a.choices)}")
                return None
            return v
        val, ukind, msg = parse_quantity(str(raw), a.kind, a.unit)
        if val is None:
            self._err("ESEM003", f"'{b.id}' 의 {key}: {msg}", b, "예: 37kW, 380V, 30m, 0.85")
            return None
        if not math.isfinite(val):
            self._err("ESEM003", f"'{b.id}' 의 {key} = {raw} 은(는) 유한한 수가 아닙니다.", b)
            return None
        if a.kind != "temperature" and val <= 0:
            self._err("ESEM003", f"'{b.id}' 의 {key} = {raw} 은(는) 0 보다 커야 합니다.", b,
                      "모르는 값은 0 이 아니라 쓰지 않습니다(미입력).")
            return None
        if a.kind == "ratio" and not (0 < val <= 1.0 + 1e-9):
            self._err("ESEM003", f"'{b.id}' 의 {key} = {raw} 은(는) 0~1(또는 0~100%) 범위여야 합니다.", b)
            return None
        if kinds is not None:
            kinds[key] = ukind
        return val

    def _check_refs(self, m: SystemModel, blocks: List[Block]):
        ids = set(m.nodes)
        span = {b.id: b for b in blocks}
        for n in m.nodes.values():
            for attr in ("parent", "feed"):
                ref = getattr(n, attr)
                if ref and ref not in ids:
                    self._err("ESEM002", f"'{n.id}' 의 {attr} = {ref} 은(는) 정의되지 않은 설비입니다.",
                              span[n.id], f"'{ref}' 를 먼저 정의하세요.")
                    setattr(n, attr, None)
            if n.parent and m.nodes.get(n.parent) and m.nodes[n.parent].type not in ("switchboard", "panel"):
                self._err("ESEM002", f"'{n.id}' 의 parent '{n.parent}' 는 배전반/분전반이 아닙니다.", span[n.id])
            if n.type == "load" and n.params.get("group") and n.params["group"] not in m.groups:
                self._warn("ESEM002", f"'{n.id}' 의 group '{n.params['group']}' 정의가 없습니다 (제약 없음으로 처리).",
                           span[n.id], f"group {n.params['group']} {{ max_on = N; }}")
        for e in m.edges.values():
            for attr, ref in (("from", e.from_id), ("to", e.to_id)):
                if not ref:
                    self._err("ESEM002", f"배선 '{e.id}' 에 {attr} 가 없습니다.", span[e.id])
                elif ref not in ids:
                    self._err("ESEM002", f"배선 '{e.id}' 의 {attr} = {ref} 은(는) 정의되지 않은 설비입니다.", span[e.id])
                elif e.type == "cable" and m.nodes[ref].type == "earth":
                    self._err("ESEM002", f"전력 배선 '{e.id}' 의 {attr} = {ref} 은(는) 접지 노드입니다.", span[e.id],
                              "접지·본딩 연결은 bond 블록으로 쓰세요.")
            if e.from_id and e.from_id == e.to_id:
                self._err("ESEM002", f"배선 '{e.id}' 의 from 과 to 가 같습니다 ({e.from_id}).", span[e.id])
        for s in m.scenarios.values():
            for ref in (s.on or set()) | s.off:
                if ref != "all" and ref not in ids and ref not in m.groups:
                    self._err("ESEM002", f"시나리오 '{s.id}' 의 '{ref}' 는 정의되지 않은 설비입니다.", span[s.id])
        # parent 순환
        for n in m.nodes.values():
            seen, cur = set(), n.id
            while cur and cur not in seen:
                seen.add(cur)
                cur = m.nodes[cur].parent if cur in m.nodes else None
            if cur:
                self._err("ESEM006", f"'{n.id}' 의 포함 관계(parent)가 순환합니다.", span[n.id])
                n.parent = None

    def _err(self, code, msg, b, action=""):
        self.d.append(DiagnosticItem(code, "ERROR", msg, b.span, b.id, action))

    def _warn(self, code, msg, b, action=""):
        self.d.append(DiagnosticItem(code, "WARNING", msg, b.span, b.id, action))
