"""FHDL 리포트 생성기. CSV/JSON 파일 출력."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from .models import AnalysisResult, NodeCalcResult, PipeCalcResult, SystemSummary


def generate_reports(result: AnalysisResult, output_dir: str) -> dict:
    """
    AnalysisResult → CSV/JSON 파일로 저장.
    반환: {nodes_csv: path, pipes_csv: path, summary_json: path}
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    nodes_path = _write_nodes_csv(result.node_results, run_dir)
    pipes_path = _write_pipes_csv(result.pipe_results, run_dir)
    summary_path = _write_summary_json(result, run_dir)

    return {
        "nodes_csv": str(nodes_path),
        "pipes_csv": str(pipes_path),
        "summary_json": str(summary_path),
        "run_dir": str(run_dir),
    }


def _write_nodes_csv(rows: List[NodeCalcResult], run_dir: Path) -> Path:
    path = run_dir / "Nodes_Report.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Node_ID", "Head(m)", "Pressure(MPa)", "Flow_In(L/min)",
            "Flow_Out(L/min)", "NPSHa(m)", "Sizing_Mode", "Formula",
        ])
        for r in rows:
            w.writerow([
                r.node_id,
                f"{r.head_total:.4f}",
                f"{r.p_gauge / 1e6:.4f}",
                f"{r.flow_in * 60000:.2f}",
                f"{r.flow_out * 60000:.2f}",
                f"{r.npsha:.3f}",
                r.sizing_mode,
                r.provenance_formula,
            ])
    return path


def _write_pipes_csv(rows: List[PipeCalcResult], run_dir: Path) -> Path:
    path = run_dir / "Pipes_Report.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Pipe_ID", "Diameter(mm)", "Length(m)", "Flow(L/min)",
            "Velocity(m/s)", "HeadLoss_F(m)", "HeadLoss_K(m)",
            "HeadLoss_Total(m)", "Surge_Index", "Status", "Formula",
        ])
        for r in rows:
            w.writerow([
                r.pipe_id,
                f"{r.diameter * 1000:.1f}",
                "",  # 길이는 별도 보관
                f"{r.flow * 60000:.2f}",
                f"{r.velocity:.3f}",
                f"{r.h_loss_f:.4f}",
                f"{r.h_loss_k:.4f}",
                f"{r.h_loss_total:.4f}",
                f"{r.surge_index:.3f}",
                r.status,
                r.formula_id,
            ])
    return path


def _write_summary_json(result: AnalysisResult, run_dir: Path) -> Path:
    path = run_dir / "Simulation_Summary.json"
    s = result.summary
    payload = {
        "status": result.status,
        "total_flow_m3h": s.total_flow * 3600,
        "required_head_m": s.required_head,
        "worst_path": s.worst_path,
        "recommended_pump": {
            "flow_m3h": s.recommended_pump_flow * 3600,
            "head_m": s.recommended_pump_head,
        },
        "recommended_tank_volume_m3": s.recommended_tank_volume,
        "converged": s.converged,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "related_id": d.related_id,
            }
            for d in result.diagnostics
        ],
        "provenance_map": s.provenance_map,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
