"""프로젝트 저장/로드/복원 오케스트레이션.

폴더 구조 (진실원 분리):
  projects/{name}/
    main.fhd        # 입력 진실원 (DSL: 토폴로지·파라미터·설정)
    state.db        # 결과 캐시 (재계산으로 재생성 가능) + 저널
    project.fhproj  # 메타 (JSON: 이름·일시·마지막 분석 정보)
    outputs/        # 내보낸 리포트

핵심 원칙:
  - 입력의 단일 진실원은 main.fhd. state.db 는 파생 캐시.
  - 캐시 유효성은 main.fhd 의 SHA-256 체크섬으로 판정한다. 결과를 저장할 때의
    소스 체크섬을 기록해두고, 로드 시 현재 소스 체크섬과 일치하면 재계산 없이
    DB 에서 결과를 복원한다(파싱은 저렴하므로 entity_map 만 새로 만든다).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AnalysisResult


SCHEMA_VERSION = "1.1.0"
MAIN_FHD = "main.fhd"
STATE_DB = "state.db"
PROJECT_META = "project.fhproj"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ProjectLoad:
    source: str                          # main.fhd 내용
    result: Optional[AnalysisResult]     # 캐시 유효 시 복원된 결과 (없으면 None)
    meta: dict                           # project.fhproj 내용
    cache_valid: bool                    # state.db 결과가 현재 소스와 일치하는지


def project_paths(project_dir: str) -> dict:
    return {
        "fhd": os.path.join(project_dir, MAIN_FHD),
        "db": os.path.join(project_dir, STATE_DB),
        "meta": os.path.join(project_dir, PROJECT_META),
        "outputs": os.path.join(project_dir, "outputs"),
    }


def read_meta(project_dir: str) -> dict:
    p = project_paths(project_dir)["meta"]
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(project_dir: str, meta: dict) -> None:
    p = project_paths(project_dir)["meta"]
    Path(p).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def save_project(project_dir: str, source: str,
                 result: Optional[AnalysisResult] = None,
                 name: str = "", write_fhd: bool = True) -> None:
    """프로젝트를 저장한다.

    - write_fhd=True 면 main.fhd 를 원자적으로 저장(stage→verify→swap).
      (분석 직후 결과만 캐시할 땐 write_fhd=False 로 파일 보존)
    - result 가 주어지면 state.db 에 결과를 캐시하고 그 소스 체크섬을 기록.
    - project.fhproj 메타(수정시각·마지막 분석 상태) 갱신.
    """
    from ..db.project_db import ProjectDB

    os.makedirs(project_dir, exist_ok=True)
    paths = project_paths(project_dir)
    checksum = _checksum(source)

    db = ProjectDB(paths["db"])
    try:
        if write_fhd:
            db.atomic_save_fhd(paths["fhd"], source)    # 원자적 저장
        if result is not None:
            db.save_analysis_result(result)
            db.set_meta("analyzed_checksum", checksum)  # 캐시 유효성 기준
    finally:
        db.close()

    meta = read_meta(project_dir)
    meta.setdefault("schema_version", SCHEMA_VERSION)
    meta.setdefault("project_name", name or meta.get("project_name") or Path(project_dir).name)
    meta.setdefault("created_at", datetime.now().isoformat())
    meta["modified_at"] = datetime.now().isoformat()
    meta["source_checksum"] = checksum
    if result is not None:
        meta["last_analyzed"] = {
            "at": datetime.now().isoformat(),
            "status": result.status,
            "checksum": checksum,
            "errors": len(result.errors),
            "warnings": len(result.warnings),
        }
    _write_meta(project_dir, meta)


def load_project(project_dir: str) -> ProjectLoad:
    """프로젝트를 로드한다.

    main.fhd 를 읽고, state.db 캐시가 현재 소스와 일치하면 결과를 복원한다.
    불일치(코드 수정됨)거나 캐시 없음이면 result=None (사용자가 재해석).
    """
    from ..db.project_db import ProjectDB

    paths = project_paths(project_dir)
    source = ""
    if os.path.exists(paths["fhd"]):
        source = Path(paths["fhd"]).read_text(encoding="utf-8")
    meta = read_meta(project_dir)

    result: Optional[AnalysisResult] = None
    cache_valid = False
    if source and os.path.exists(paths["db"]):
        db = ProjectDB(paths["db"])
        try:
            # 미완료 저장(DIRTY) 복구 — 복구되면 캐시를 신뢰하지 않음
            recovered = db.recover()
            analyzed = db.get_meta("analyzed_checksum")
            cache_valid = (not recovered) and bool(analyzed) and analyzed == _checksum(source)
            if recovered:
                meta = dict(meta)
                meta["recovered"] = True
            if cache_valid:
                # 파싱으로 entity_map 만 재구성(저렴) + DB 결과 복원(재계산 회피)
                em = _parse_entity_map(source)
                result = db.load_result(entity_map=em)
        finally:
            db.close()

    return ProjectLoad(source=source, result=result, meta=meta, cache_valid=cache_valid)


def _parse_entity_map(source: str):
    """소스를 파싱/의미분석하여 entity_map 만 만든다 (솔버 미실행)."""
    from .parser import FHDLParser
    from .semantic import SemanticAnalyzer
    ast, _ = FHDLParser().parse(source)
    em, _ = SemanticAnalyzer().analyze(ast)
    return em
