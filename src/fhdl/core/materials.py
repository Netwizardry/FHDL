"""배관 재질 단일 진실원 — 재질 id → 물성(조도·C계수·허용압력·압력파속도).

core(해석)·db(라이브러리)·gui(드롭다운)가 모두 이 표를 참조한다.
재질을 선택하면 해당 조도/C계수가 자동 적용된다(semantic).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# id → (표시명, roughness_m, c_factor_hw, max_pressure_pa, wave_velocity_ms)
MATERIALS: Dict[str, Tuple[str, float, float, float, float]] = {
    "Steel":       ("강관 (탄소강)",     0.000045,  120, 2_000_000, 1200),
    "Cast_Iron":   ("주철관",           0.000260,  100, 1_800_000, 1100),
    "PVC":         ("PVC 경질관",       0.0000015, 150, 1_000_000,  400),
    "PE":          ("폴리에틸렌 (PE)",   0.000007,  145, 1_500_000,  350),
    "HDPE":        ("고밀도 PE (HDPE)",  0.000007,  145, 1_600_000,  350),
    "SUS304":      ("스테인리스 304",    0.000015,  140, 2_500_000, 1350),
    "SUS316":      ("스테인리스 316",    0.000015,  140, 2_500_000, 1350),
    "Copper":      ("구리관",           0.0000015, 135, 2_000_000, 1300),
    "Double_Wall": ("이중벽관",          0.000050,  120, 2_000_000, 1200),
    "Perforated":  ("유공관",           0.000200,  110, 1_000_000,  800),
}

# 구 DB/별칭 표기 → 정본 id
_ALIASES: Dict[str, str] = {
    "STS": "SUS304", "STS304": "SUS304", "STS316": "SUS316",
    "CI": "Cast_Iron", "CASTIRON": "Cast_Iron", "CAST_IRON": "Cast_Iron",
    "CARBON_STEEL": "Steel", "SS": "Steel",
}


def canonical(material_id: str) -> str:
    """재질 id 정규화 (별칭·대소문자 허용). 미정의면 빈 문자열."""
    key = (material_id or "").strip()
    if key in MATERIALS:
        return key
    up = key.upper()
    for mid in MATERIALS:
        if mid.upper() == up:
            return mid
    if up in _ALIASES:
        return _ALIASES[up]
    return ""


def material_properties(material_id: str) -> Optional[Dict]:
    """재질 물성 dict 반환 (미정의면 None)."""
    canon = canonical(material_id)
    if not canon:
        return None
    name, rough, c, maxp, wave = MATERIALS[canon]
    return {
        "material_id": canon, "name": name,
        "roughness_m": rough, "c_factor_hw": c,
        "max_pressure_pa": maxp, "wave_velocity_ms": wave,
    }


def list_materials() -> List[Tuple[str, str]]:
    """(id, 표시명) 목록 — GUI 드롭다운용."""
    return [(mid, props[0]) for mid, props in MATERIALS.items()]


def seed_rows() -> List[Tuple[str, str, float, float, float, float]]:
    """라이브러리 DB 시드용 (id, name, roughness, c, max_p, wave)."""
    return [(mid, p[0], p[1], p[2], p[3], p[4]) for mid, p in MATERIALS.items()]
