"""T-PUMP: 펌프 커브 기반 운전점 해석."""
import os
import sys
import tempfile
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline
from fhdl.core.solver import HydraulicSolver
from fhdl.db.library_db import LibraryDB


def test_curve_head_interpolation():
    pts = [(0.0, 40, 0.0), (0.002, 35, 0.6), (0.004, 28, 0.7), (0.006, 18, 0.6)]
    f = HydraulicSolver._curve_head
    assert f(pts, 0.0) == 40            # 하한
    assert f(pts, 0.01) == 18           # 상한 클램프
    assert abs(f(pts, 0.003) - 31.5) < 1e-6   # 35↔28 중간


def _run_with_curve(q_lpm):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = LibraryDB(path)
    db.upsert_pump_curve("CR-1", rated_flow=0.003, rated_head=30,
                         points=[(0.0, 40, 0.0), (0.002, 35, 0.6),
                                 (0.004, 28, 0.7), (0.006, 18, 0.6)])
    code = f"""
system m {{ unit_system=METRIC; fluid=water; temp=20; }}
tank res {{ z=2m; level_max=1m; }}
pump pp {{ z=0m; curve_id=CR-1; }}
terminal t {{ z=5m; required_q={q_lpm}lpm; }}
pipe suc {{ start=res; end=pp; length=2m;  diameter=100mm; material=Steel; }}
pipe dis {{ start=pp;  end=t;  length=10m; diameter=100mm; material=Steel; }}
connect res -> pp -> t;
"""
    try:
        r = AnalysisPipeline().run(code, library=db)
        return next(n.head_total for n in r.node_results if n.node_id == "pp")
    finally:
        db.close()
        os.unlink(path)


def test_operating_point_follows_curve():
    """요구 유량이 클수록 커브 양정이 낮아 펌프 수두도 낮아야 한다."""
    h120 = _run_with_curve(120)   # 0.002 m³/s → 양정 35
    h240 = _run_with_curve(240)   # 0.004 m³/s → 양정 28
    h360 = _run_with_curve(360)   # 0.006 m³/s → 양정 18
    assert h120 > h240 > h360
    # 펌프노드 수두 ≈ 흡입수두(≈3) + 커브 양정
    assert abs(h240 - (3.0 + 28.0)) < 1.0


def test_no_library_keeps_fixed_head():
    """라이브러리 미제공 시 기존 동작(MANUAL/AUTO head) 유지."""
    code = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank res { z=2m; level_max=1m; }
pump pp { z=0m; head=25m; flow=200lpm; }
terminal t { z=5m; required_q=200lpm; }
pipe suc { start=res; end=pp; length=2m; diameter=100mm; material=Steel; }
pipe dis { start=pp; end=t; length=10m; diameter=100mm; material=Steel; }
connect res -> pp -> t;
"""
    r = AnalysisPipeline().run(code)   # library 미제공
    h = next(n.head_total for n in r.node_results if n.node_id == "pp")
    assert abs(h - (3.0 + 25.0)) < 0.5
