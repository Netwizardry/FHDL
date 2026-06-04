"""T-MAT: 재질 단일 진실원 + 물성 연동."""
import sys
sys.path.insert(0, "src")

from fhdl.core.materials import (
    canonical, list_materials, material_properties, MATERIALS,
)
from fhdl.core.pipeline import AnalysisPipeline

_H = ("system m { unit_system=METRIC; fluid=water; temp=20; }\n"
      "tank s { z=20m; }\nterminal t { z=0m; required_q=100lpm; }\n")


def _pipe(material: str, extra: str = ""):
    code = _H + f"pipe p {{ start=s; end=t; length=30m; diameter=50mm; material={material}; {extra} }}\nconnect s->t;"
    return AnalysisPipeline().run(code).entity_map.pipes["p"]


def test_material_lookup_and_alias():
    assert material_properties("PVC")["roughness_m"] == 0.0000015
    assert canonical("CI") == "Cast_Iron"          # 별칭
    assert canonical("STS") == "SUS304"
    assert canonical("nonexistent") == ""
    assert material_properties("nonexistent") is None


def test_list_materials_for_gui():
    ids = [m[0] for m in list_materials()]
    assert "Steel" in ids and "Cast_Iron" in ids and "PVC" in ids
    assert len(ids) == len(MATERIALS)


def test_material_drives_properties():
    """재질 선택이 조도/C계수에 자동 반영되어야 한다."""
    steel = _pipe("Steel")
    pvc = _pipe("PVC")
    ci = _pipe("Cast_Iron")
    assert steel.roughness != pvc.roughness        # 재질별 조도 다름
    assert pvc.c_factor == 150 and ci.c_factor == 100
    assert abs(ci.roughness - 0.00026) < 1e-9


def test_material_alias_in_dsl():
    """DSL 에서 별칭(CI/STS)을 써도 정본 물성 적용."""
    ci = _pipe("CI")
    assert ci.material == "Cast_Iron"
    assert ci.c_factor == 100


def test_explicit_override_wins():
    p = _pipe("PVC", extra="roughness=0.2mm; c_factor=99;")
    assert abs(p.roughness - 0.0002) < 1e-9
    assert p.c_factor == 99


def test_material_friction_differs():
    """재질이 다르면 마찰손실도 달라야 한다(연동 확인)."""
    code_s = _H + "pipe p { start=s; end=t; length=100m; diameter=50mm; material=Steel; friction_model=HW; }\nconnect s->t;"
    # HW 는 c_factor 사용 — 재질로 결정됨
    rs = AnalysisPipeline().run(_H.replace("temp=20;", "temp=20; friction_model=HW;") +
                                "pipe p { start=s; end=t; length=100m; diameter=50mm; material=Steel; }\nconnect s->t;")
    rc = AnalysisPipeline().run(_H.replace("temp=20;", "temp=20; friction_model=HW;") +
                                "pipe p { start=s; end=t; length=100m; diameter=50mm; material=Cast_Iron; }\nconnect s->t;")
    hs = rs.pipe_results[0].h_loss_f
    hc = rc.pipe_results[0].h_loss_f
    assert hc > hs    # 주철(C=100)이 강관(C=120)보다 손실 큼
