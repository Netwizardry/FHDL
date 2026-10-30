"""
FHDL DSL 파서.
입력: FHDL 텍스트 문자열
출력: (AST 노드 리스트, SyntaxDiagnostics)
예외를 던지지 않고 DiagnosticItem으로 에러를 반환한다.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .language import BLOCK_KEYWORDS, NODE_TYPES
from .models import (
    ASTNode, ComponentASTNode, ConnectASTNode, ConstraintASTNode,
    DiagnosticItem, SourceSpan, SystemASTNode,
)


# ---------------------------------------------------------------------------
# 단위 정규화 헬퍼 (파서 단계: 수치+단위 → 수치 분리만)
# ---------------------------------------------------------------------------

def _parse_value_unit(raw: str) -> Tuple[float, str]:
    """'10m' -> (10.0, 'm'), '1.5MPa' -> (1.5, 'MPa'), '120' -> (120.0, '')"""
    raw = raw.strip()
    m = re.match(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([a-zA-Z%/³°][a-zA-Z0-9%/³°]*)?\s*$', raw)
    if not m:
        return (0.0, "")
    return (float(m.group(1)), (m.group(2) or "").strip())


# ---------------------------------------------------------------------------
# 파서 본체
# ---------------------------------------------------------------------------

class FHDLParser:
    """
    FHDL DSL을 AST 노드 리스트로 변환한다.
    에러는 DiagnosticItem으로 수집하여 반환하며, 가능한 한 계속 파싱한다.
    """

    def parse(self, source: str) -> Tuple[List[ASTNode], List[DiagnosticItem]]:
        self._source = source
        self._lines = source.splitlines()
        self._diagnostics: List[DiagnosticItem] = []
        self._ast: List[ASTNode] = []

        clean = self._strip_comments(source)
        # 값 안의 중괄호(fittings = {elbow_90*2}) 는 [ ] 로 — 블록 경계 { } 와 헷갈리지 않게(길이 보존)
        clean = re.sub(r"=\s*\{([^{}]*)\}", lambda m: m.group(0).replace("{", "[").replace("}", "]"), clean)
        self._check_braces(clean, source)
        self._parse_statements(clean, source)

        return self._ast, self._diagnostics

    def _check_braces(self, clean: str, raw: str):
        """중괄호 짝 검사 — 닫히지 않은 블록은 다음 블록 속성을 삼킨다(SYN003)."""
        depth, open_at = 0, None
        for i, ch in enumerate(clean):
            if ch == "{":
                if depth == 0:
                    open_at = i
                depth += 1
                if depth > 1:
                    self._add_error("SYN003", "블록 안에 다시 '{' 가 있습니다 — 앞 블록의 '}' 가 빠졌나요?",
                                    self._span_at(raw, open_at))
                    return
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    self._add_error("SYN003", "짝이 없는 '}' 입니다.", self._span_at(raw, i))
                    return
        if depth > 0:
            self._add_error("SYN003", "블록의 닫는 '}' 가 없습니다.", self._span_at(raw, open_at))

    def _span_at(self, raw: str, pos: int) -> SourceSpan:
        line = raw[:pos].count("\n") + 1
        col = pos - raw[:pos].rfind("\n") - 1
        return SourceSpan(line=line, col=col, end_line=line, end_col=col + 1)

    # ------------------------------------------------------------------
    # 주석 제거
    # ------------------------------------------------------------------

    def _strip_comments(self, text: str) -> str:
        # 블록 주석 (* ... *) → 줄바꿈 수 보존
        def replace_block(m):
            return "\n" * m.group().count("\n") + " " * (len(m.group()) - m.group().count("\n"))
        text = re.sub(r"/\*.*?\*/", replace_block, text, flags=re.DOTALL)
        # 행 주석
        text = re.sub(r"//[^\n]*", "", text)
        return text

    # ------------------------------------------------------------------
    # 전체 statement 파싱
    # ------------------------------------------------------------------

    def _parse_statements(self, clean: str, raw: str):
        """최상위 블록/문장을 순서대로 파싱한다."""
        # 모르는 블록 키워드 — 조용히 버리지 않는다 (SYN002)
        known = {k.lower() for k in BLOCK_KEYWORDS}
        for m in re.finditer(r'(?:^|[;}])\s*([A-Za-z_]\w*)\s+(?:\w+\s*)?\{', clean):
            kw = m.group(1)
            if kw.lower() not in known:
                self._add_error("SYN002", f"알 수 없는 블록 '{kw}' 은(는) 해석하지 않습니다.",
                                self._span_from_match(m, raw), action="가능한 블록: " + ", ".join(BLOCK_KEYWORDS))
        # system ... { ... }
        for m in re.finditer(
            r'\b(system)\s+(\w+)\s*\{([^}]*)\}',
            clean, re.IGNORECASE | re.DOTALL
        ):
            span = self._span_from_match(m, raw)
            node = SystemASTNode(
                name=m.group(2),
                attributes=self._parse_attributes(m.group(3)),
                span=span,
            )
            self._ast.append(node)

        # tank/pump/junction/terminal id { ... }
        for comp_type in NODE_TYPES:
            for m in re.finditer(
                rf'\b({comp_type})\s+(\w+)\s*\{{([^}}]*)\}}',
                clean, re.IGNORECASE | re.DOTALL
            ):
                span = self._span_from_match(m, raw)
                node = ComponentASTNode(
                    comp_type=comp_type.lower(),
                    comp_id=m.group(2),
                    attributes=self._parse_attributes(m.group(3)),
                    span=span,
                )
                self._ast.append(node)

        # pipe id { start=X; end=Y; ... }
        for m in re.finditer(
            r'\b(pipe)\s+(\w+)\s*\{([^}]*)\}',
            clean, re.IGNORECASE | re.DOTALL
        ):
            span = self._span_from_match(m, raw)
            attrs = self._parse_attributes(m.group(3))
            node = ComponentASTNode(
                comp_type="pipe",
                comp_id=m.group(2),
                attributes=attrs,
                span=span,
            )
            self._ast.append(node)

        # connect A -> B -> C;
        for m in re.finditer(
            r'\bconnect\s+([\w\s\->]+?)\s*;',
            clean, re.IGNORECASE
        ):
            span = self._span_from_match(m, raw)
            chain_str = m.group(1)
            chain = [tok.strip() for tok in re.split(r'\s*->\s*', chain_str) if tok.strip()]
            if len(chain) < 2:
                self._add_error(
                    "SYN001", f"connect 구문에 노드가 2개 이상 필요합니다: '{chain_str}'", span
                )
                continue
            node = ConnectASTNode(chain=chain, span=span)
            self._ast.append(node)

        # constraint { ... }
        for m in re.finditer(
            r'\bconstraint\s*\{([^}]*)\}',
            clean, re.IGNORECASE | re.DOTALL
        ):
            span = self._span_from_match(m, raw)
            node = ConstraintASTNode(
                attributes=self._parse_attributes(m.group(1)),
                span=span,
            )
            self._ast.append(node)

    # ------------------------------------------------------------------
    # 속성 블록 파싱: "key = value;" 여러 줄
    # ------------------------------------------------------------------

    def _parse_attributes(self, block: str) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        for m in re.finditer(
            r'(\w+)\s*=\s*([^;]+?)\s*(?:;|$)',          # 블록 마지막 속성은 ; 생략 가능
            block.strip()
        ):
            key = m.group(1).lower().strip()
            raw_val = m.group(2).strip()
            attrs[key] = self._coerce_value(raw_val)
        return attrs

    def _coerce_value(self, raw: str) -> Any:
        """문자열 값을 Python 타입으로 변환한다."""
        raw = raw.strip()
        # 불리언
        if raw.lower() in ("true", "yes"): return True
        if raw.lower() in ("false", "no"): return False
        # 수치+단위 (1.2.3 · . 같은 잘못된 수는 문자열로 남겨 의미 분석이 SEM012 로 알린다)
        if re.match(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*([a-zA-Z%/³°][a-zA-Z0-9%/³°]*)?\s*$', raw):
            val, unit = _parse_value_unit(raw)
            return (val, unit) if unit else val
        # 그 외 문자열
        return raw.strip('"\'')

    # ------------------------------------------------------------------
    # 위치 계산
    # ------------------------------------------------------------------

    def _span_from_match(self, m: re.Match, raw: str) -> SourceSpan:
        start = m.start()
        line = raw[:start].count("\n") + 1
        col = start - raw[:start].rfind("\n") - 1
        end = m.end()
        end_line = raw[:end].count("\n") + 1
        end_col = end - raw[:end].rfind("\n") - 1
        return SourceSpan(line=line, col=col, end_line=end_line, end_col=end_col)

    # ------------------------------------------------------------------
    # 진단 헬퍼
    # ------------------------------------------------------------------

    def _add_error(self, code: str, msg: str, span: SourceSpan,
                   severity: str = "ERROR", action: str = ""):
        self._diagnostics.append(DiagnosticItem(
            code=code, severity=severity, message=msg,
            source_span=span, suggested_action=action
        ))


# ---------------------------------------------------------------------------
# DSL → FHD 텍스트 직렬화 (역방향)
# ---------------------------------------------------------------------------

def serialize_entity_map_to_fhd(entity_map) -> str:
    """EntityMap → FHDL DSL 텍스트 (왕복 보존: 다시 파싱하면 같은 엔티티).

    값은 :g 로 정밀도 손실 없이 쓰고, 기본값과 다른 속성·명시한 속성을 모두 내보낸다."""
    from .models import EntityMap
    em: EntityMap = entity_map
    out = []

    def block(head, rows):
        out.append(head + " {")
        out.extend(f"    {r}" for r in rows if r)
        out.append("}\n")

    def xy(e):
        return f"x = {e.x:.12g}; y = {e.y:.12g};" if e.has_xy else ""

    f = em.fluid
    block("system main", [f"unit_system = {f.unit_system};", f"fluid = {f.fluid_type};", f"temp = {f.temp:.12g};",
                          f"altitude = {f.altitude:.12g}m;", f"friction_model = {f.friction_model};"])
    for t in em.tanks.values():
        block(f"tank {t.entity_id}", [f"z = {t.elevation:.12g}m;", xy(t),
                                      f"volume = {t.volume:.12g}m3;" if t.volume != float("inf") else "",
                                      f"level_max = {t.level_max:.12g}m;", f"level_min = {t.level_min:.12g}m;"])
    for p in em.pumps.values():
        block(f"pump {p.entity_id}", [
            f"z = {p.elevation:.12g}m;", xy(p),
            f"flow = {p.flow.value:.12g}m3s;" if p.flow.mode == "MANUAL" else "flow = auto;",
            f"head = {p.head.value:.12g}m;" if p.head.mode == "MANUAL" else "head = auto;",
            f"efficiency = {p.efficiency:.12g};", f"npshr = {p.npshr:.12g}m;", f"pump_type = {p.pump_type};",
            f"min_level = {p.min_level:.12g}m;" if p.min_level else "",
            f"submerge_ref = {p.submerge_ref};" if p.submerge_ref else "",
            f"curve_id = {p.curve_id};" if p.curve_id else ""])
    for j in em.junctions.values():
        block(f"junction {j.entity_id}", [f"z = {j.elevation:.12g}m;", xy(j)])
    for t in em.terminals.values():
        block(f"terminal {t.entity_id}", [
            f"z = {t.elevation:.12g}m;", xy(t),
            f"required_q = {t.required_q * 1e3:.12g}Ls;" if t.required_q > 0 else "",
            f"required_p = {t.required_p / 1e6:.12g}MPa;" if t.required_p > 0 else "",
            f"k_factor = {t.k_factor:.12g};" if t.k_factor else "",
            f"preset_id = {t.preset_id};" if t.preset_id else ""])
    for pipe in em.pipes.values():
        dia = pipe.diameter
        block(f"pipe {pipe.entity_id}", [
            f"start = {pipe.start_id};", f"end = {pipe.end_id};",
            f"length = {pipe.length:.12g}m;" if pipe.length > 0 else "",
            "diameter = auto;" if dia.mode == "AUTO" else f"diameter = {dia.value * 1000:.12g}mm;",
            f"material = {pipe.material};", f"roughness = {pipe.roughness * 1000:.12g}mm;",
            f"c_factor = {pipe.c_factor:.12g};",
            f"k_factor = {pipe.k_explicit:.12g};" if pipe.k_explicit else "",
            f"fittings = [{pipe.fittings.strip('[]{} ')}];" if pipe.fittings.strip("[]{} ") else "",
            ("via = [" + ", ".join(f"({x:.12g}, {y:.12g}, {z:.12g})" for x, y, z in pipe.via) + "];") if pipe.via else ""])
    c = em.constraints
    block("constraint", [f"velocity_min = {c.velocity_min:.12g}m/s;", f"velocity_max = {c.velocity_max:.12g}m/s;",
                         f"safety_factor_head = {c.safety_factor_head:.12g};",
                         f"safety_factor_npsh = {c.safety_factor_npsh:.12g};", f"pipe_standard = {c.pipe_standard};"])
    for from_id, to_id in em.connections:
        out.append(f"connect {from_id} -> {to_id};")
    return "\n".join(out)
