"""T-LIB: 부품 라이브러리 DB ↔ 해석 연결 — 재질·부속 K·관경 표준이 라이브러리 편집을 따른다."""
import sys
sys.path.insert(0, "src")

import pytest

from fhdl.core.pipeline import AnalysisPipeline
from fhdl.core.pipe_sizes import KS_PIPE_SIZES
from fhdl.db.library_db import LibraryDB, _LEGACY_KS

SRC = """system main { fluid = water; temp = 20; friction_model = DW; }
%s
tank T { z = 10m; }
terminal E { z = 0m; required_q = 200lpm; }
pipe p1 { start = T; end = E; length = 30m; diameter = %s; material = %s; %s }
connect T -> p1 -> E;
"""


@pytest.fixture
def lib(tmp_path):
    db = LibraryDB(str(tmp_path / "lib.db"))
    yield db
    db.close()


def run(lib, constraint="", dia="50mm", mat="Steel", extra=""):
    return AnalysisPipeline().run(SRC % (constraint, dia, mat, extra), library=lib)


def test_material_edit_in_library_changes_calculation(lib):
    base = run(lib).entity_map.pipes["p1"].roughness
    lib.upsert_material("Steel", "탄소강", roughness_m=0.5e-3, c_factor_hw=100.0)
    r = run(lib)
    assert r.entity_map.pipes["p1"].roughness == pytest.approx(0.5e-3) != base
    lib.upsert_material("PE200", "사용자 재질", roughness_m=0.01e-3, c_factor_hw=150.0)
    r = run(lib, mat="PE200")
    assert r.entity_map.pipes["p1"].c_factor == 150.0 and not any(d.code == "SEM004" for d in r.diagnostics)


def test_library_fitting_k_used_and_not_flagged_unknown(lib):
    lib.upsert_fitting("custom_valve", 7.5)
    r = run(lib, extra="fittings = [custom_valve];")
    assert r.entity_map.pipes["p1"].manual_k == pytest.approx(7.5)
    assert not any(d.code == "SEM015" for d in r.diagnostics)


def test_pipe_standard_selects_library_sizes(lib):
    jis = sorted(d for _, d in lib.get_standard_sizes("JIS"))
    r = run(lib, constraint="constraint { pipe_standard = JIS; }", dia="auto")
    assert r.pipe_results[0].diameter in jis
    r = run(lib, constraint="constraint { pipe_standard = XYZ; }", dia="auto")
    assert any(d.code == "SEM016" for d in r.diagnostics)
    assert r.pipe_results[0].diameter in [s.inner_d_m for s in KS_PIPE_SIZES]


def test_ks_seed_matches_core_and_legacy_seed_is_replaced(tmp_path):
    db = LibraryDB(str(tmp_path / "old.db"))
    db._conn.execute("DELETE FROM pipe_sizes WHERE standard='KS'")
    db._conn.executemany("INSERT INTO pipe_sizes(standard,nominal_size,inner_diameter) VALUES('KS',?,?)",
                         list(_LEGACY_KS.items()))
    db._conn.commit()
    db.close()
    db = LibraryDB(str(tmp_path / "old.db"))                 # 다시 열면 이전 시드 교체
    assert dict(db.get_standard_sizes("KS"))["15A"] == pytest.approx(0.0159)
    assert [d for _, d in db.get_standard_sizes("KS")] == [s.inner_d_m for s in KS_PIPE_SIZES]
    db.close()


def test_surge_index_uses_material_wave_speed(lib):
    r1 = run(lib)
    lib.upsert_material("Steel", "탄소강", wave_velocity_ms=600.0)
    r2 = run(lib)
    assert r2.pipe_results[0].surge_index == pytest.approx(r1.pipe_results[0].surge_index / 2, rel=1e-6)
