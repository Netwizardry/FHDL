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

# KS 표준 관경 기초 데이터 (nominal, inner_m)
_KS_SIZES = [
    ("15A",  0.01270), ("20A",  0.01590), ("25A",  0.02110),
    ("32A",  0.02670), ("40A",  0.03520), ("50A",  0.04220),
    ("65A",  0.05280), ("80A",  0.06860), ("100A", 0.08250),
    ("125A", 0.10230), ("150A", 0.12630), ("200A", 0.15030),
    ("250A", 0.20270), ("300A", 0.25270),
]

_MATERIALS = [
    ("Steel",  "Steel (Carbon)",   0.000045, 120, 2_000_000, 1200),
    ("STS",    "Stainless Steel",  0.000015, 140, 2_500_000, 1350),
    ("PVC",    "PVC",              0.0000015,150, 1_000_000,  400),
    ("HDPE",   "HDPE",             0.000007, 145, 1_600_000,  350),
    ("CI",     "Cast Iron",        0.00026,  100, 1_800_000, 1100),
]

# 부속 K-factor 단일 진실원은 core.fittings.FITTINGS 이다.
# 라이브러리 DB 는 이를 시드 데이터로 재사용한다 (중복 정의 방지).
from ..core.fittings import FITTINGS as _CORE_FITTINGS

_FITTINGS = [
    (name, "all", k, desc) for name, (k, desc) in _CORE_FITTINGS.items()
]


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
        # 관경 (없을 때만)
        if cur.execute("SELECT COUNT(*) FROM pipe_sizes").fetchone()[0] == 0:
            cur.executemany(
                "INSERT OR IGNORE INTO pipe_sizes(standard,nominal_size,inner_diameter) VALUES(?,?,?)",
                [("KS", nm, d) for nm, d in _KS_SIZES],
            )
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
        row = self._conn.execute(
            "SELECT * FROM pipe_materials WHERE material_id=?", (material_id,)
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

    def close(self):
        self._conn.close()
