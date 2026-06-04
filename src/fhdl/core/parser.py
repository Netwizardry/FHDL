"""
FHDL DSL 파서.
입력: FHDL 텍스트 문자열
출력: (AST 노드 리스트, SyntaxDiagnostics)
예외를 던지지 않고 DiagnosticItem으로 에러를 반환한다.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

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
    m = re.match(r'^([+-]?[\d.]+(?:[eE][+-]?\d+)?)\s*([a-zA-Z%/³³]*)\s*$', raw)
    if not m:
        return (0.0, "")
    return (float(m.group(1)), m.group(2).strip())


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
        self._parse_statements(clean, source)

        return self._ast, self._diagnostics

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
        for comp_type in ("tank", "pump", "junction", "terminal"):
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
            r'(\w+)\s*=\s*([^;]+?)\s*;',
            block
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
        # 수치+단위
        val, unit = _parse_value_unit(raw)
        if unit or re.match(r'^[+-]?[\d.]+$', raw):
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
    """EntityMap 객체를 FHDL DSL 텍스트로 직렬화한다."""
    from .models import EntityMap, PipeEntity, SizingState
    em: EntityMap = entity_map
    lines = []

    fluid = em.fluid
    lines.append(f"system main {{")
    lines.append(f"    unit_system = {fluid.unit_system};")
    lines.append(f"    fluid = {fluid.fluid_type};")
    lines.append(f"    temp = {fluid.temp};")
    lines.append(f"    altitude = {fluid.altitude};")
    lines.append(f"    friction_model = {fluid.friction_model};")
    lines.append("}\n")

    for t in em.tanks.values():
        lines.append(f"tank {t.entity_id} {{")
        lines.append(f"    z = {t.elevation}m;")
        if t.x or t.y:
            lines.append(f"    x = {t.x}; y = {t.y};")
        if t.volume != float("inf"):
            lines.append(f"    volume = {t.volume}m3;")
        lines.append("}\n")

    for p in em.pumps.values():
        lines.append(f"pump {p.entity_id} {{")
        lines.append(f"    z = {p.elevation}m;")
        if p.x or p.y:
            lines.append(f"    x = {p.x}; y = {p.y};")
        if p.flow.mode == "MANUAL":
            lines.append(f"    flow = {p.flow.value}m3s;")
        if p.head.mode == "MANUAL":
            lines.append(f"    head = {p.head.value}m;")
        lines.append("}\n")

    for j in em.junctions.values():
        lines.append(f"junction {j.entity_id} {{")
        lines.append(f"    z = {j.elevation}m;")
        if j.x or j.y:
            lines.append(f"    x = {j.x}; y = {j.y};")
        lines.append("}\n")

    for t in em.terminals.values():
        lines.append(f"terminal {t.entity_id} {{")
        lines.append(f"    z = {t.elevation}m;")
        if t.x or t.y:
            lines.append(f"    x = {t.x}; y = {t.y};")
        if t.required_q > 0:
            lines.append(f"    required_q = {t.required_q * 1e6:.2f}Ls;")
        if t.required_p > 0:
            lines.append(f"    required_p = {t.required_p / 1e6:.4f}MPa;")
        lines.append("}\n")

    for pipe in em.pipes.values():
        lines.append(f"pipe {pipe.entity_id} {{")
        lines.append(f"    start = {pipe.start_id};")
        lines.append(f"    end = {pipe.end_id};")
        if pipe.length > 0:
            lines.append(f"    length = {pipe.length}m;")
        dia = pipe.diameter
        if dia.mode == "AUTO":
            lines.append(f"    diameter = auto;")
        else:
            lines.append(f"    diameter = {dia.value * 1000:.1f}mm;")
        lines.append(f"    material = {pipe.material};")
        lines.append("}\n")

    if em.connections:
        for from_id, to_id in em.connections:
            lines.append(f"connect {from_id} -> {to_id};")

    return "\n".join(lines)
