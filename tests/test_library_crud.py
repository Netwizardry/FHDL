"""T-LIB: 부품 라이브러리 DB CRUD (신설/수정/삭제)."""
import sys
import os
import tempfile
sys.path.insert(0, "src")

from fhdl.db.library_db import LibraryDB


def _db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return LibraryDB(path), path


def test_pipe_size_crud():
    db, path = _db()
    try:
        db.upsert_pipe_size("KS", "350A", 0.3500)          # 신설
        assert any(s["nominal_size"] == "350A" for s in db.list_pipe_sizes("KS"))
        db.upsert_pipe_size("KS", "350A", 0.3600)          # 수정
        row = [s for s in db.list_pipe_sizes("KS") if s["nominal_size"] == "350A"][0]
        assert abs(row["inner_diameter"] - 0.36) < 1e-9
        assert db.delete_pipe_size("KS", "350A") == 1      # 삭제
        assert not any(s["nominal_size"] == "350A" for s in db.list_pipe_sizes("KS"))
    finally:
        db.close(); os.unlink(path)


def test_material_crud():
    db, path = _db()
    try:
        db.upsert_material("PE100", "Polyethylene", roughness_m=0.0000015, c_factor_hw=150)
        assert db.get_material("PE100")["c_factor_hw"] == 150
        db.upsert_material("PE100", "PE100 updated", c_factor_hw=155)   # 수정
        assert db.get_material("PE100")["c_factor_hw"] == 155
        assert db.delete_material("PE100") == 1
        assert db.get_material("PE100") is None
    finally:
        db.close(); os.unlink(path)


def test_fitting_crud():
    db, path = _db()
    try:
        db.upsert_fitting("custom_valve", 7.5, description="특수 밸브")
        assert db.get_fitting_k("custom_valve") == 7.5
        db.upsert_fitting("custom_valve", 8.0)             # 수정
        assert db.get_fitting_k("custom_valve") == 8.0
        assert db.delete_fitting("custom_valve") == 1
        assert db.get_fitting_k("custom_valve") == 1.0     # 미정의 기본
    finally:
        db.close(); os.unlink(path)


def test_pump_curve_crud():
    db, path = _db()
    try:
        db.upsert_pump_curve("CR32-2", manufacturer="Grundfos", rated_flow=0.005, rated_head=30,
                             points=[(0.0, 35, 0.0), (0.005, 30, 0.7), (0.01, 20, 0.6)])
        assert any(c["curve_id"] == "CR32-2" for c in db.list_pump_curves())
        pts = db.get_pump_curve_points("CR32-2")
        assert len(pts) == 3 and pts[1][1] == 30
        db.upsert_pump_curve("CR32-2", points=[(0.0, 40, 0.0)])   # 점 교체
        assert len(db.get_pump_curve_points("CR32-2")) == 1
        assert db.delete_pump_curve("CR32-2") == 1
        assert db.get_pump_curve_points("CR32-2") == []
    finally:
        db.close(); os.unlink(path)


def test_fluid_crud():
    db, path = _db()
    try:
        db.upsert_fluid("oil", 20.0, density=850, viscosity=0.04, vapor_pressure=100)
        f = db.get_fluid_properties("oil", 20.0)
        assert f and abs(f["density"] - 850) < 1e-6
        db.upsert_fluid("oil", 20.0, density=860, viscosity=0.038)   # 수정
        assert db.get_fluid_properties("oil", 20.0)["density"] == 860
        assert db.delete_fluid("oil", 20.0) == 1
    finally:
        db.close(); os.unlink(path)
