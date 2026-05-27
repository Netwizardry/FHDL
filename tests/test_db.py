"""DB 레이어 테스트."""
import sys
import tempfile
import os
sys.path.insert(0, "src")

from fhdl.db.library_db import LibraryDB
from fhdl.db.project_db import ProjectDB
from fhdl.core.pipeline import AnalysisPipeline
from fhdl.core.models import AnalysisResult


def test_library_db_standard_sizes():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = LibraryDB(path)
        sizes = db.get_standard_sizes("KS")
        assert len(sizes) > 0
        # 50A가 있어야 함
        names = [s[0] for s in sizes]
        assert "50A" in names
        db.close()
    finally:
        os.unlink(path)


def test_library_db_material():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = LibraryDB(path)
        mat = db.get_material("Steel")
        assert mat is not None
        assert "roughness_m" in mat
        assert mat["roughness_m"] > 0
        db.close()
    finally:
        os.unlink(path)


def test_library_db_fitting_k():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = LibraryDB(path)
        k = db.get_fitting_k("ELBOW90")
        assert k > 0
        k_gate = db.get_fitting_k("GATE_VALVE")
        assert k_gate < k  # 게이트 밸브가 엘보보다 낮아야 함
        db.close()
    finally:
        os.unlink(path)


def test_project_db_save_result():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        code = """
        system main { unit_system = METRIC; fluid = water; temp = 20; }
        tank src { elevation = 5m; }
        terminal t1 { elevation = 0m; required_q = 60lpm; }
        pipe p1 { start = src; end = t1; length = 20m; diameter = 50mm; material = Steel; }
        connect src -> t1;
        """
        pipeline = AnalysisPipeline()
        result = pipeline.run(code)
        assert result.status in ("OK", "PARTIAL")

        db = ProjectDB(path)
        run_id = db.save_analysis_result(result)
        assert run_id != ""

        summary = db.get_last_summary()
        assert summary is not None

        diags = db.get_diagnostics(run_id)
        assert isinstance(diags, list)
        db.close()
    finally:
        os.unlink(path)


def test_project_db_meta():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        db = ProjectDB(path)
        db.set_meta("test_key", "test_value")
        val = db.get_meta("test_key")
        assert val == "test_value"
        db.close()
    finally:
        os.unlink(path)
