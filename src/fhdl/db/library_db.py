"""
전역 부품 라이브러리 DB.
data/library.db에 관경, 재질, 피팅, 유체 물성 테이블을 관리한다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipe_sizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard TEXT NOT NULL,
    nominal_size TEXT NOT NULL,
    inner_diameter REAL NOT NULL,
    outer_diameter REAL,
    wall_thickness REAL,
    UNIQUE(standard, nominal_size)
);

CREATE TABLE IF NOT EXISTS pipe_materials (
    material_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    roughness_m REAL DEFAULT 0.000045,
    c_factor_hw REAL DEFAULT 120.0,
    max_pressure_pa REAL DEFAULT 2000000.0,
    wave_velocity_ms REAL DEFAULT 1200.0
);

CREATE TABLE IF NOT EXISTS fitting_kfactors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fitting_type TEXT NOT NULL,
    nominal_size TEXT NOT NULL DEFAULT 'all',
    k_factor REAL NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS pump_curves (
    curve_id TEXT PRIMARY KEY,
    manufacturer TEXT DEFAULT '',
    model TEXT DEFAULT '',
    rated_flow REAL DEFAULT 0,
    rated_head REAL DEFAULT 0,
    npshr REAL DEFAULT 0.5
);

CREATE TABLE IF NOT EXISTS pump_curve_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    curve_id TEXT NOT NULL,
    flow REAL NOT NULL,
    head REAL NOT NULL,
    efficiency REAL DEFAULT 0.75
);

CREATE TABLE IF NOT EXISTS fluid_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fluid_type TEXT NOT NULL,
    temperature REAL NOT NULL,
    density REAL NOT NULL,
    viscosity REAL NOT NULL,
    vapor_pressure REAL DEFAULT 0,
    UNIQUE(fluid_type, temperature)
);
"""

# KS 관경 단일 진실원은 core.pipe_sizes.KS_PIPE_SIZES 이다 (nominal, inner_m).
from ..core.pipe_sizes import KS_PIPE_SIZES as _CORE_KS

_KS_SIZES = [(f"{s.nominal_a}A", s.inner_d_m) for s in _CORE_KS]

# 이전 시드(호칭과 내경이 한 칸 어긋남 — 15A 에 10A 내경). 이 값 그대로면 _seed_data 가 교체한다.
_LEGACY_KS = {
    "15A": 0.01270, "20A": 0.01590, "25A": 0.02110, "32A": 0.02670, "40A": 0.03520, "50A": 0.04220,
    "65A": 0.05280, "80A": 0.06860, "100A": 0.08250, "125A": 0.10230, "150A": 0.12630, "200A": 0.15030,
    "250A": 0.20270, "300A": 0.25270,
}

# 다른 관경 표준 (호칭, 외경 mm, 두께 mm) — 내경 = 외경 − 2·두께. 사용자가 라이브러리에서 고칠 수 있다.
# JIS G 3452 SGP (배관용 탄소강관)
_JIS_SGP = [
    ("15A", 21.7, 2.8), ("20A", 27.2, 2.8), ("25A", 34.0, 3.2), ("32A", 42.7, 3.5), ("40A", 48.6, 3.5),
    ("50A", 60.5, 3.8), ("65A", 76.3, 4.2), ("80A", 89.1, 4.2), ("100A", 114.3, 4.5), ("125A", 139.8, 4.5),
    ("150A", 165.2, 5.0), ("200A", 216.3, 5.8), ("250A", 267.4, 6.6), ("300A", 318.5, 6.9),
]
# ASME B36.10M Schedule 40
_ANSI_SCH40 = [
    ('1/2"', 21.34, 2.77), ('3/4"', 26.67, 2.87), ('1"', 33.40, 3.38), ('1-1/4"', 42.16, 3.56),
    ('1-1/2"', 48.26, 3.68), ('2"', 60.33, 3.91), ('2-1/2"', 73.03, 5.16), ('3"', 88.90, 5.49),
    ('4"', 114.30, 6.02), ('5"', 141.30, 6.55), ('6"', 168.28, 7.11), ('8"', 219.08, 8.18),
    ('10"', 273.05, 9.27), ('12"', 323.85, 10.31),
]
_OTHER_STANDARDS = {"JIS": _JIS_SGP, "ANSI": _ANSI_SCH40}

# 재질 물성 단일 진실원은 core.materials.MATERIALS 이다 (중복 정의 방지).
from ..core.materials import seed_rows as _material_seed_rows

_MATERIALS = _material_seed_rows()

# 부속 K-factor 단일 진실원은 core.fittings.FITTINGS 이다.
# 라이브러리 DB 는 이를 시드 데이터로 재사용한다 (중복 정의 방지).
from ..core.fittings import FITTINGS as _CORE_FITTINGS

_FITTINGS = [
    (name, "all", k, desc) for name, (k, desc) in _CORE_FITTINGS.items()
]


def default_library_path() -> str:
    """전역 라이브러리 위치 — 환경변수 FHDL_LIBRARY, 없으면 설치 폴더의 data/library.db (작업 폴더와 무관)."""
    import os
    env = os.environ.get("FHDL_LIBRARY")
    if env:
        return env
    return str(Path(__file__).resolve().parents[3] / "data" / "library.db")


class LibraryDB:
    """전역 부품 라이브러리 DB 관리자."""

    def __init__(self, db_path: str):
        self._path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._seed_data()

    def _init_schema(self):
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _seed_data(self):
        cur = self._conn
        # 관경 (표준별로 없을 때만). 이전의 어긋난 KS 시드는 정본으로 교체.
        ks = {r[0]: r[1] for r in cur.execute(
            "SELECT nominal_size, inner_diameter FROM pipe_sizes WHERE standard='KS'").fetchall()}
        if ks and ks == _LEGACY_KS:
            cur.execute("DELETE FROM pipe_sizes WHERE standard='KS'")
            ks = {}
        if not ks:
            cur.executemany(
                "INSERT OR IGNORE INTO pipe_sizes(standard,nominal_size,inner_diameter) VALUES(?,?,?)",
                [("KS", nm, d) for nm, d in _KS_SIZES],
            )
        for std, rows in _OTHER_STANDARDS.items():
            if cur.execute("SELECT COUNT(*) FROM pipe_sizes WHERE standard=?", (std,)).fetchone()[0] == 0:
                cur.executemany(
                    "INSERT OR IGNORE INTO pipe_sizes(standard,nominal_size,inner_diameter,outer_diameter,"
                    "wall_thickness) VALUES(?,?,?,?,?)",
                    [(std, nm, (od - 2 * t) / 1000.0, od / 1000.0, t / 1000.0) for nm, od, t in rows])
        # 재질
        if cur.execute("SELECT COUNT(*) FROM pipe_materials").fetchone()[0] == 0:
            cur.executemany(
                "INSERT OR IGNORE INTO pipe_materials"
                "(material_id,name,roughness_m,c_factor_hw,max_pressure_pa,wave_velocity_ms)"
                " VALUES(?,?,?,?,?,?)",
                _MATERIALS,
            )
        # 피팅
        if cur.execute("SELECT COUNT(*) FROM fitting_kfactors").fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO fitting_kfactors(fitting_type,nominal_size,k_factor,description)"
                " VALUES(?,?,?,?)",
                _FITTINGS,
            )
        # 유체 물성 (물, 0~100°C, 10도 간격)
        if cur.execute("SELECT COUNT(*) FROM fluid_properties").fetchone()[0] == 0:
            import math
            rows = []
            for T in range(0, 101, 10):
                rho = 999.84 + 0.0678 * T - 0.009 * T * T
                nu = 1.792e-6 / (1 + 0.0337 * T + 0.000221 * T * T)
                visc = nu * rho
                log_pv = 8.07131 - 1730.63 / (233.426 + T)
                pv = (10 ** log_pv) * 133.322
                rows.append(("water", float(T), rho, visc, pv))
            cur.executemany(
                "INSERT OR IGNORE INTO fluid_properties"
                "(fluid_type,temperature,density,viscosity,vapor_pressure) VALUES(?,?,?,?,?)",
                rows,
            )
        cur.commit()

    # ------------------------------------------------------------------
    # 조회 API
    # ------------------------------------------------------------------

    def get_standard_sizes(self, standard: str = "KS") -> List[Tuple[str, float]]:
        """(nominal_size, inner_diameter_m) 목록 반환."""
        rows = self._conn.execute(
            "SELECT nominal_size, inner_diameter FROM pipe_sizes WHERE standard=? ORDER BY inner_diameter",
            (standard,),
        ).fetchall()
        return [(r["nominal_size"], r["inner_diameter"]) for r in rows]

    def get_material(self, material_id: str) -> Optional[Dict]:
        from ..core.materials import canonical
        key = canonical(material_id) or material_id
        row = self._conn.execute(
            "SELECT * FROM pipe_materials WHERE material_id=?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def get_fitting_k(self, fitting_type: str, nominal_size: str = "all") -> float:
        # core.fittings 의 정본 키로 정규화 (대문자 별칭·대소문자 허용)
        from ..core.fittings import _canonical
        key = _canonical(fitting_type) or fitting_type
        row = self._conn.execute(
            "SELECT k_factor FROM fitting_kfactors WHERE fitting_type=? AND (nominal_size=? OR nominal_size='all') ORDER BY nominal_size DESC LIMIT 1",
            (key, nominal_size),
        ).fetchone()
        return row["k_factor"] if row else 1.0

    def find_fitting_k(self, fitting_type: str, nominal_size: str = "all") -> Optional[float]:
        """라이브러리에 있는 부속 K (없으면 None — get_fitting_k 와 달리 기본값을 지어내지 않는다)."""
        from ..core.fittings import _canonical
        key = _canonical(fitting_type) or fitting_type
        row = self._conn.execute(
            "SELECT k_factor FROM fitting_kfactors WHERE fitting_type=? AND (nominal_size=? OR nominal_size='all') "
            "ORDER BY nominal_size DESC LIMIT 1", (key, nominal_size)).fetchone()
        return row["k_factor"] if row else None

    def get_pump_curve_points(self, curve_id: str) -> List[Tuple[float, float, float]]:
        rows = self._conn.execute(
            "SELECT flow, head, efficiency FROM pump_curve_points WHERE curve_id=? ORDER BY flow",
            (curve_id,),
        ).fetchall()
        return [(r["flow"], r["head"], r["efficiency"]) for r in rows]

    def get_fluid_properties(self, fluid_type: str, temp: float) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT * FROM fluid_properties WHERE fluid_type=? ORDER BY ABS(temperature-?) LIMIT 1",
            (fluid_type, temp),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # CRUD — 부품 데이터 신설/수정/삭제 (최신 데이터 유지)
    # ------------------------------------------------------------------

    # --- 관경 ---
    def list_pipe_sizes(self, standard: str = "") -> List[Dict]:
        if standard:
            rows = self._conn.execute(
                "SELECT * FROM pipe_sizes WHERE standard=? ORDER BY inner_diameter", (standard,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM pipe_sizes ORDER BY standard, inner_diameter").fetchall()
        return [dict(r) for r in rows]

    def upsert_pipe_size(self, standard: str, nominal_size: str, inner_diameter: float,
                         outer_diameter: float = None, wall_thickness: float = None) -> None:
        self._conn.execute(
            """INSERT INTO pipe_sizes(standard,nominal_size,inner_diameter,outer_diameter,wall_thickness)
               VALUES(?,?,?,?,?)
               ON CONFLICT(standard,nominal_size) DO UPDATE SET
                 inner_diameter=excluded.inner_diameter,
                 outer_diameter=excluded.outer_diameter,
                 wall_thickness=excluded.wall_thickness""",
            (standard, nominal_size, inner_diameter, outer_diameter, wall_thickness),
        )
        self._conn.commit()

    def delete_pipe_size(self, standard: str, nominal_size: str) -> int:
        cur = self._conn.execute(
            "DELETE FROM pipe_sizes WHERE standard=? AND nominal_size=?", (standard, nominal_size))
        self._conn.commit()
        return cur.rowcount

    # --- 재질 ---
    def list_materials(self) -> List[Dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM pipe_materials ORDER BY material_id").fetchall()]

    def upsert_material(self, material_id: str, name: str, roughness_m: float = 0.000045,
                        c_factor_hw: float = 120.0, max_pressure_pa: float = 2_000_000.0,
                        wave_velocity_ms: float = 1200.0) -> None:
        self._conn.execute(
            """INSERT INTO pipe_materials(material_id,name,roughness_m,c_factor_hw,max_pressure_pa,wave_velocity_ms)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(material_id) DO UPDATE SET
                 name=excluded.name, roughness_m=excluded.roughness_m,
                 c_factor_hw=excluded.c_factor_hw, max_pressure_pa=excluded.max_pressure_pa,
                 wave_velocity_ms=excluded.wave_velocity_ms""",
            (material_id, name, roughness_m, c_factor_hw, max_pressure_pa, wave_velocity_ms),
        )
        self._conn.commit()

    def delete_material(self, material_id: str) -> int:
        cur = self._conn.execute("DELETE FROM pipe_materials WHERE material_id=?", (material_id,))
        self._conn.commit()
        return cur.rowcount

    # --- 피팅 K ---
    def list_fittings(self) -> List[Dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM fitting_kfactors ORDER BY fitting_type, nominal_size").fetchall()]

    def upsert_fitting(self, fitting_type: str, k_factor: float,
                       nominal_size: str = "all", description: str = "") -> None:
        # (fitting_type, nominal_size) 유일성 보장 (테이블엔 UNIQUE 없으므로 수동 갱신)
        row = self._conn.execute(
            "SELECT id FROM fitting_kfactors WHERE fitting_type=? AND nominal_size=?",
            (fitting_type, nominal_size)).fetchone()
        if row:
            self._conn.execute(
                "UPDATE fitting_kfactors SET k_factor=?, description=? WHERE id=?",
                (k_factor, description, row["id"]))
        else:
            self._conn.execute(
                "INSERT INTO fitting_kfactors(fitting_type,nominal_size,k_factor,description) VALUES(?,?,?,?)",
                (fitting_type, nominal_size, k_factor, description))
        self._conn.commit()

    def delete_fitting(self, fitting_type: str, nominal_size: str = "all") -> int:
        cur = self._conn.execute(
            "DELETE FROM fitting_kfactors WHERE fitting_type=? AND nominal_size=?",
            (fitting_type, nominal_size))
        self._conn.commit()
        return cur.rowcount

    # --- 펌프 커브 ---
    def list_pump_curves(self) -> List[Dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM pump_curves ORDER BY curve_id").fetchall()]

    def upsert_pump_curve(self, curve_id: str, manufacturer: str = "", model: str = "",
                          rated_flow: float = 0.0, rated_head: float = 0.0, npshr: float = 0.5,
                          points: List[Tuple[float, float, float]] = None) -> None:
        self._conn.execute(
            """INSERT INTO pump_curves(curve_id,manufacturer,model,rated_flow,rated_head,npshr)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(curve_id) DO UPDATE SET
                 manufacturer=excluded.manufacturer, model=excluded.model,
                 rated_flow=excluded.rated_flow, rated_head=excluded.rated_head, npshr=excluded.npshr""",
            (curve_id, manufacturer, model, rated_flow, rated_head, npshr))
        if points is not None:
            self._conn.execute("DELETE FROM pump_curve_points WHERE curve_id=?", (curve_id,))
            self._conn.executemany(
                "INSERT INTO pump_curve_points(curve_id,flow,head,efficiency) VALUES(?,?,?,?)",
                [(curve_id, f, h, e) for f, h, e in points])
        self._conn.commit()

    def delete_pump_curve(self, curve_id: str) -> int:
        self._conn.execute("DELETE FROM pump_curve_points WHERE curve_id=?", (curve_id,))
        cur = self._conn.execute("DELETE FROM pump_curves WHERE curve_id=?", (curve_id,))
        self._conn.commit()
        return cur.rowcount

    # --- 유체 물성 ---
    def list_fluids(self) -> List[Dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM fluid_properties ORDER BY fluid_type, temperature").fetchall()]

    def upsert_fluid(self, fluid_type: str, temperature: float, density: float,
                     viscosity: float, vapor_pressure: float = 0.0) -> None:
        self._conn.execute(
            """INSERT INTO fluid_properties(fluid_type,temperature,density,viscosity,vapor_pressure)
               VALUES(?,?,?,?,?)
               ON CONFLICT(fluid_type,temperature) DO UPDATE SET
                 density=excluded.density, viscosity=excluded.viscosity,
                 vapor_pressure=excluded.vapor_pressure""",
            (fluid_type, temperature, density, viscosity, vapor_pressure))
        self._conn.commit()

    def delete_fluid(self, fluid_type: str, temperature: float) -> int:
        cur = self._conn.execute(
            "DELETE FROM fluid_properties WHERE fluid_type=? AND temperature=?",
            (fluid_type, temperature))
        self._conn.commit()
        return cur.rowcount

    def close(self):
        self._conn.close()
