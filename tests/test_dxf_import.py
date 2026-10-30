"""T-DXF: 사용자 기호표·도면 양식 DXF → FHDL 기호/양식 데이터 이식.

대상:
  - drawing/dxf_symbols.py → data/iso_symbols.json (기호 15종, 방향 변형)
  - drawing/dxf_form.py → data/iso_form.json (A3 배관 ISO 양식, 채움 칸)
  - 저장된 데이터가 archive/dxf 원본에서 그대로 재생성되는지(재현성)
"""
import json
import os
import sys
sys.path.insert(0, "src")

import pytest

from fhdl.core.fittings import FITTING_SYMBOLS
from fhdl.drawing.frame import FORM_PATH, company_form
from fhdl.drawing.sheet import Polyline
from fhdl.drawing.symbols import IMPORTED_PATH, available_symbols, imported_symbols, render_symbol

ROOT = os.path.join(os.path.dirname(__file__), "..")
SYM_DXF = os.path.join(ROOT, "archive", "dxf", "Piping_admin_65hoiqch_Isometric-Piping.dxf")
FORM_DXF = os.path.join(ROOT, "archive", "dxf", "도면FORM 및 SYMBOL 1 (3).dxf")


def test_imported_symbols_cover_sheet_valves_and_fittings():
    syms = imported_symbols()
    expected = {"valve_gate", "valve_globe", "valve_ball", "valve_plug", "valve_needle",
                "valve_butterfly", "valve_diaphragm", "valve_check", "expansion_joint", "union",
                "orifice", "reducer", "reducer_ecc", "sight_glass", "flow_arrow"}
    assert expected <= set(syms)
    # 대칭 밸브는 6방향(배관 축 3 × 평면 2) 모두
    assert set(syms["valve_gate"]["variants"]) == {"E/N", "E/U", "N/E", "N/U", "U/E", "U/N"}
    assert syms["valve_check"]["directional"] and syms["flow_arrow"]["directional"]
    # 모든 부속 기호 키가 그릴 수 있는 기호를 가리킨다
    assert set(FITTING_SYMBOLS.values()) <= set(available_symbols())


def test_unit_is_gate_valve_half_length():
    gate = imported_symbols()["valve_gate"]["local"]
    xs = [p[0] for part in gate for p in part["pts"]]
    assert min(xs) == pytest.approx(-1.0, abs=1e-3) and max(xs) == pytest.approx(1.0, abs=1e-3)


def test_iso_rendering_uses_sheet_variant():
    var = imported_symbols()["valve_needle"]["variants"]["E/U"]
    items = render_symbol("valve_needle", (100.0, 50.0), (0.866, -0.5), (0.0, 1.0), 2.0,
                          axes=("E", "+", "U"))
    assert len(items) == len(var)
    x0, y0 = var[0]["pts"][0]
    assert items[0].pts[0] == pytest.approx((100.0 + 2.0 * x0, 50.0 + 2.0 * y0))


def test_directional_symbol_mirrors_for_reverse_flow():
    """화살촉(체크 밸브)이 반대 방향 변형만 있으면 배관 축 방향으로 반사한다."""
    sym = imported_symbols()["valve_check"]
    assert "+E/U" in sym["variants"] and "-E/U" not in sym["variants"]
    a_dir = (0.866, -0.5)

    def tip_side(axes):
        items = render_symbol("valve_check", (0.0, 0.0), a_dir, (0.0, 1.0), 1.0, axes=axes)
        solid = next(i for i in items if isinstance(i, Polyline) and i.fill)
        cx = sum(p[0] for p in solid.pts) / len(solid.pts)
        cy = sum(p[1] for p in solid.pts) / len(solid.pts)
        far = max(solid.pts, key=lambda p: abs((p[0] - cx) * a_dir[0] + (p[1] - cy) * a_dir[1]))
        return (far[0] - cx) * a_dir[0] + (far[1] - cy) * a_dir[1]

    assert tip_side(("E", "+", "U")) > 0 > tip_side(("E", "-", "U"))


def test_diagonal_pipe_falls_back_to_local_shape():
    items = render_symbol("valve_gate", (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 1.0, axes=None)
    xs = [p[0] for i in items for p in i.pts]
    assert min(xs) == pytest.approx(-1.0, abs=1e-3)


def test_company_form_structure():
    form = company_form()
    assert form and (form["width"], form["height"]) == (420.0, 297.0)
    texts = {t["text"] for t in form["texts"]}
    assert {"BILL OF MATERIAL", "LINE NO.", "COMMODITY", "SHT.NO.", "DRAWN", "OPERATION",
            "HYDROSTATIC TEST", "NOTES:"} <= texts
    # 샘플 값은 채움 칸으로 바뀌고 글자에서 빠진다
    assert not ({"DS-생-017", "J.con", "AS-BUILT", "2011", "06.30"} & texts)
    assert {"line_no", "commodity", "job_no", "sheet", "rev", "rev_year", "rev_md", "drawn",
            "oper_press", "oper_temp"} <= set(form["fields"])
    assert form["bom"]["rows"] == 29 and form["bom"]["columns"][0] == "CODE"


@pytest.mark.skipif(not os.path.exists(SYM_DXF), reason="기호표 DXF 없음")
def test_symbol_data_regenerates_from_dxf():
    from fhdl.drawing.dxf_symbols import extract_iso_symbols
    with open(IMPORTED_PATH, encoding="utf-8") as f:
        saved = json.load(f)
    assert json.loads(json.dumps(extract_iso_symbols(SYM_DXF))) == saved


@pytest.mark.skipif(not os.path.exists(FORM_DXF), reason="도면 양식 DXF 없음")
def test_form_data_regenerates_from_dxf():
    from fhdl.drawing.dxf_form import extract_form
    with open(FORM_PATH, encoding="utf-8") as f:
        saved = json.load(f)
    data = json.loads(json.dumps(extract_form(FORM_DXF)))
    assert data == saved
    # 회사 로고(SR02)·BOM 샘플(DEM MTEXT)은 양식 레이어가 아니라 들어오지 않는다
    assert len(data["polys"]) + len(data["lines"]) < 400
