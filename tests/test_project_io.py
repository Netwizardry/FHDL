"""T-OPS: 프로젝트 저장/로드/복원 (캐시 유효성 기반)."""
import sys
import tempfile
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline
from fhdl.core.project_io import load_project, save_project, read_meta

_SRC = """system m { unit_system=METRIC; fluid=water; temp=20; altitude=100m; }
tank src { z=10m; x=0; y=0; }
terminal t { z=0m; x=50; y=5; required_q=80lpm; }
pipe p1 { start=src; end=t; length=30m; diameter=50mm; material=Steel; fittings=[elbow_90]; }
connect src -> t;
"""


def test_save_creates_files():
    with tempfile.TemporaryDirectory() as d:
        r = AnalysisPipeline().run(_SRC)
        save_project(d, _SRC, r, name="proj")
        import os
        assert os.path.exists(os.path.join(d, "main.fhd"))
        assert os.path.exists(os.path.join(d, "state.db"))
        assert os.path.exists(os.path.join(d, "project.fhproj"))
        meta = read_meta(d)
        assert meta["project_name"] == "proj"
        assert meta["last_analyzed"]["status"] == r.status


def test_load_restores_results_without_recompute():
    """저장 후 로드 시 캐시가 유효하면 결과가 복원되어야 한다(재계산 없이)."""
    with tempfile.TemporaryDirectory() as d:
        r = AnalysisPipeline().run(_SRC)
        save_project(d, _SRC, r)
        loaded = load_project(d)
        assert loaded.cache_valid is True
        assert loaded.result is not None
        # 노드/배관 결과·토폴로지 복원
        assert len(loaded.result.node_results) == len(r.node_results)
        pr = {p.pipe_id: p for p in loaded.result.pipe_results}
        assert pr["p1"].start_id == "src" and pr["p1"].end_id == "t"
        assert pr["p1"].k_total > 0
        # entity_map 도 파싱으로 복원되어 뷰어 토폴로지 사용 가능
        assert "p1" in loaded.result.entity_map.pipes


def test_load_invalidates_cache_on_source_change():
    """저장 후 main.fhd 가 바뀌면 캐시 무효 → result=None."""
    with tempfile.TemporaryDirectory() as d:
        r = AnalysisPipeline().run(_SRC)
        save_project(d, _SRC, r)
        # 소스만 변경 저장 (결과 없이)
        changed = _SRC.replace("required_q=80lpm", "required_q=200lpm")
        save_project(d, changed, None)
        loaded = load_project(d)
        assert loaded.cache_valid is False
        assert loaded.result is None
        assert "200lpm" in loaded.source


def test_load_missing_project():
    with tempfile.TemporaryDirectory() as d:
        loaded = load_project(d)
        assert loaded.source == ""
        assert loaded.result is None
        assert loaded.cache_valid is False
