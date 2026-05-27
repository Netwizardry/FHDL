"""
FHDL 분석 파이프라인 오케스트레이터.
Parse → Semantic → Solve → Report 순서로 실행.
각 단계 FAIL 시 즉시 반환.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from .models import AnalysisResult, DiagnosticItem, EntityMap, SourceSpan
from .parser import FHDLParser
from .semantic import SemanticAnalyzer
from .solver import HydraulicSolver
from .report_generator import generate_reports


class AnalysisPipeline:

    def run(
        self,
        source_code: str,
        output_dir: Optional[str] = None,
        cancel_fn: Optional[Callable[[], bool]] = None,
        status_fn: Optional[Callable[[str], None]] = None,
    ) -> AnalysisResult:
        """
        FHDL 소스 코드를 전체 분석한다.
        cancel_fn(): True이면 중단.
        status_fn(msg): 진행 상태 메시지 콜백.
        """
        result = AnalysisResult()

        def _status(msg: str):
            if status_fn:
                status_fn(msg)

        # --- Step 1: 파싱 ---
        _status("파싱 중...")
        parser = FHDLParser()
        ast, syn_diags = parser.parse(source_code)
        result.diagnostics.extend(syn_diags)

        if any(d.is_blocking for d in syn_diags):
            result.status = "FAILED"
            return result

        if not ast:
            result.diagnostics.append(DiagnosticItem(
                code="SYN001", severity="ERROR",
                message="입력 코드가 비어 있거나 파싱할 수 없습니다.",
                source_span=SourceSpan(),
                suggested_action="올바른 FHDL 코드를 입력하세요.",
            ))
            result.status = "FAILED"
            return result

        # --- Step 2: 의미 분석 ---
        _status("의미 분석 중...")
        analyzer = SemanticAnalyzer()
        em, sem_diags = analyzer.analyze(ast)
        result.diagnostics.extend(sem_diags)
        result.entity_map = em

        if any(d.is_blocking for d in sem_diags):
            result.status = "FAILED"
            return result

        # --- Step 3: 수리 해석 ---
        _status("수리 해석 중...")
        solver = HydraulicSolver(em, cancel_fn=cancel_fn)
        node_results, pipe_results, summary = solver.solve()
        result.diagnostics.extend(solver.diagnostics)
        result.node_results = node_results
        result.pipe_results = pipe_results
        result.summary = summary

        if any(d.severity == "FATAL" for d in solver.diagnostics):
            result.status = "FAILED"
            return result

        has_errors = any(d.is_blocking for d in solver.diagnostics)
        result.status = "PARTIAL" if has_errors else "OK"

        # --- Step 4: 리포트 저장 ---
        if output_dir and result.status != "FAILED":
            _status("리포트 저장 중...")
            try:
                paths = generate_reports(result, output_dir)
                result.summary.provenance_map["_output_paths"] = paths
            except Exception as e:
                result.diagnostics.append(DiagnosticItem(
                    code="CAL003", severity="WARNING",
                    message=f"리포트 저장 실패: {e}",
                    source_span=SourceSpan(),
                ))

        _status("완료")
        return result
