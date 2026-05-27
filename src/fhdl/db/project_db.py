"""
프로젝트별 SQLite DB 관리자.
각 프로젝트의 계산 결과, 메타데이터, 진단 이력을 관리한다.
원자적 저장 및 저널링 지원.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.models import AnalysisResult, DiagnosticItem, NodeCalcResult, PipeCalcResult


_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes_result (
    node_id TEXT PRIMARY KEY,
    type TEXT DEFAULT 'JUNCTION',
    x REAL DEFAULT 0, y REAL DEFAULT 0, z REAL DEFAULT 0,
    head_total REAL DEFAULT 0,
    p_gauge REAL DEFAULT 0,
    flow_req REAL DEFAULT 0,
    flow_actual REAL DEFAULT 0,
    npsha REAL DEFAULT 0,
    sizing_mode TEXT DEFAULT 'MANUAL',
    provenance_formula TEXT DEFAULT '',
    diagnostic_code TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipes_result (
    pipe_id TEXT PRIMARY KEY,
    start_node TEXT DEFAULT '',
    end_node TEXT DEFAULT '',
    diameter REAL DEFAULT 0,
    velocity REAL DEFAULT 0,
    flow REAL DEFAULT 0,
    h_loss_total REAL DEFAULT 0,
    surge_index REAL DEFAULT 0,
    status TEXT DEFAULT 'OK',
    sizing_mode TEXT DEFAULT 'MANUAL',
    formula_id TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_summary (
    run_id TEXT PRIMARY KEY,
    total_flow REAL DEFAULT 0,
    total_head REAL DEFAULT 0,
    worst_path TEXT DEFAULT '',
    pump_flow REAL DEFAULT 0,
    pump_head REAL DEFAULT 0,
    tank_volume REAL DEFAULT 0,
    run_time_ms INTEGER DEFAULT 0,
    status TEXT DEFAULT 'OK',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT DEFAULT '',
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT DEFAULT '',
    related_id TEXT DEFAULT '',
    source_line INTEGER DEFAULT 0,
    source_col INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_meta (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT DEFAULT '',
    journal_status TEXT DEFAULT 'CLEAN'
);
"""


class ProjectDB:
    """프로젝트별 SQLite DB."""

    def __init__(self, db_path: str):
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # 결과 저장
    # ------------------------------------------------------------------

    def save_analysis_result(self, result: AnalysisResult, run_id: str = "") -> str:
        if not run_id:
            run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

        self._set_journal_dirty()

        with self._conn:
            # 노드 결과
            self._conn.execute("DELETE FROM nodes_result")
            for nr in result.node_results:
                self._conn.execute(
                    """INSERT OR REPLACE INTO nodes_result
                    (node_id, head_total, p_gauge, flow_req, flow_actual, npsha, sizing_mode, provenance_formula)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (nr.node_id, nr.head_total, nr.p_gauge,
                     nr.flow_in, nr.flow_out, nr.npsha,
                     nr.sizing_mode, nr.provenance_formula),
                )

            # 배관 결과
            self._conn.execute("DELETE FROM pipes_result")
            for pr in result.pipe_results:
                self._conn.execute(
                    """INSERT OR REPLACE INTO pipes_result
                    (pipe_id, diameter, velocity, flow, h_loss_total, surge_index, status, sizing_mode, formula_id)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (pr.pipe_id, pr.diameter, pr.velocity, pr.flow,
                     pr.h_loss_total, pr.surge_index, pr.status,
                     pr.sizing_mode, pr.formula_id),
                )

            # 시스템 요약
            s = result.summary
            self._conn.execute(
                """INSERT OR REPLACE INTO system_summary
                (run_id, total_flow, total_head, worst_path, pump_flow, pump_head, tank_volume, status)
                VALUES (?,?,?,?,?,?,?,?)""",
                (run_id, s.total_flow, s.required_head,
                 json.dumps(s.worst_path), s.recommended_pump_flow,
                 s.recommended_pump_head, s.recommended_tank_volume, result.status),
            )

            # 진단
            for d in result.diagnostics:
                self._conn.execute(
                    """INSERT INTO diagnostics (run_id, code, severity, message, related_id, source_line, source_col)
                    VALUES (?,?,?,?,?,?,?)""",
                    (run_id, d.code, d.severity, d.message,
                     d.related_id, d.source_span.line, d.source_span.col),
                )

        self._set_journal_clean()
        return run_id

    # ------------------------------------------------------------------
    # 메타데이터
    # ------------------------------------------------------------------

    def set_meta(self, key: str, value: str, checksum: str = ""):
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO project_meta (key, value, checksum) VALUES (?,?,?)",
                (key, value, checksum),
            )

    def get_meta(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM project_meta WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def _set_journal_dirty(self):
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO project_meta (key, value, journal_status) VALUES ('_journal','1','DIRTY')"
            )

    def _set_journal_clean(self):
        with self._conn:
            self._conn.execute(
                "UPDATE project_meta SET journal_status='CLEAN' WHERE key='_journal'"
            )

    def is_dirty(self) -> bool:
        row = self._conn.execute(
            "SELECT journal_status FROM project_meta WHERE key='_journal'"
        ).fetchone()
        return (row["journal_status"] == "DIRTY") if row else False

    # ------------------------------------------------------------------
    # 원자적 저장 (Stage → Verify → Swap)
    # ------------------------------------------------------------------

    def atomic_save_fhd(self, fhd_path: str, content: str):
        """FHD 파일을 원자적으로 저장한다."""
        checksum = hashlib.sha256(content.encode()).hexdigest()
        tmp = fhd_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            # Verify
            with open(tmp, "r", encoding="utf-8") as f:
                verify = hashlib.sha256(f.read().encode()).hexdigest()
            if verify != checksum:
                raise IOError("체크섬 불일치: 임시 파일 손상")
            # Swap
            os.replace(tmp, fhd_path)
            self.set_meta("last_checksum", checksum)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # ------------------------------------------------------------------
    # 조회
    # ------------------------------------------------------------------

    def get_last_summary(self) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT * FROM system_summary ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def get_diagnostics(self, run_id: str = "") -> List[Dict]:
        if run_id:
            rows = self._conn.execute(
                "SELECT * FROM diagnostics WHERE run_id=? ORDER BY id", (run_id,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM diagnostics ORDER BY id DESC LIMIT 200"
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()
