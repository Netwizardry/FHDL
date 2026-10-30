"""T-EDX: DXF 전기 설계도 가져오기 — 부하 일람표·CABLE SCHEDULE(블록 안)·단선결선도·전동기 SCHEDULE.

국내 도면 양식을 흉내 낸 합성 DXF: 머리글은 칸 가운데, 값은 칸 왼쪽 정렬, 병합 셀(차단기 규격은 첫 행만),
표 아래 ELB 주기, 도면끼리 어긋난 차단기 규격.
"""
import sys
sys.path.insert(0, "src")

import pytest

ezdxf = pytest.importorskip("ezdxf")

from ehdl.dxf_import import import_dxf, parse_feeder  # noqa: E402
from ehdl.pipeline import analyze  # noqa: E402


def _t(msp, s, x, y, h=10.0):
    msp.add_text(s, dxfattribs={"height": h, "insert": (x, y)})


@pytest.fixture
def drawing(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    # --- 단선결선도 (신설 수전반)
    _t(msp, "(금회 신설)", 0, 1012)
    _t(msp, "T.R : 3%%c 500kVA x1EA", 0, 1000)
    _t(msp, "P.V : 22.9kV", 0, 988)
    _t(msp, "S.V : 380V/220V", 0, 976)
    _t(msp, "ACB 4P", 10, 900)
    _t(msp, "800AF (700A)", 10, 890)
    _t(msp, "660V 50kA", 10, 880)
    _t(msp, "Set. 80%%%", 10, 870)
    _t(msp, "LOAD NAME", 0, 500)
    for x, name, va, ka, af, at in ((30, "LP-1  PANEL", "2,100 VA", "460V  37kA", "125", "50"),
                                    (60, "MCC-1  PANEL", "9,500 VA", "460V  37kA", "125", "30")):
        _t(msp, name, x, 500)
        _t(msp, va, x, 590)
        _t(msp, ka, x, 560)
        _t(msp, at, x + 12, 540)
        _t(msp, af, x + 12, 525)
        _t(msp, "4", x + 12, 512)
    _t(msp, "22.9kV-Y 부전기실 ONE LINE DIAGRAM (신설)", 0, 400)
    # --- 부하 일람표
    _t(msp, '지하층 "LP-1" PANEL', 0, 0)
    _t(msp, "FROM: 수배전반", 5, -20)
    for s, x, y in (("번호", 60, -40), ("칭", 100, -40), ("(VA)", 200, -40), ("L1", 230, -45), ("L2", 245, -45),
                    ("L3", 260, -45), ("기", 285, -45), ("P", 300, -45), ("AF", 315, -45), ("AT", 335, -45),
                    ("(KA)", 355, -45)):
        _t(msp, s, x, y)
    rows = [(-60, ["TOTAL LOAD@85", "2100@195", "MCCB@278", "4@300", "50@316", "50@336", "18@358"]),
            (-80, ["L1@60", "전 등@85", "1500@195", "1500@232", "ELB@278", "2@300", "30@316", "20@336", "2.5@358"]),
            (-95, ["R1@60", "전 열@85", "600@195", "600@247"]),               # 병합 셀 — 차단기 규격 이어받기
            (-110, ["SP@60", "예 비@85"])]
    for y, cells in rows:
        for c in cells:
            s, x = c.rsplit("@", 1)
            _t(msp, s, float(x), y)
    _t(msp, "ELB는, 정격감도전류 15mA,", 60, -150)
    _t(msp, "동작시간 0.03초 이하 전류동작형 설치", 60, -162)
    # --- CABLE SCHEDULE (블록 안, 2배 축척으로 삽입)
    blk = doc.blocks.new("CS")
    for s, x, y in (("CABLE SCHEDULE", 0, 100), ("NO.", 0, 80), ("FROM", 40, 80), ("TO", 100, 80),
                    ("FEEDER", 200, 80), ("REMARK'S", 330, 80),
                    ("BA", 2, 60), ("수배전반", 30, 60), ("LP-1", 80, 60), ("F-CV 4/C 10%%D & 10%%D(E) 42C", 150, 60),
                    ("4P 50/50", 320, 60),
                    ("BB", 2, 45), ("수배전반", 30, 45), ("MCC-1", 80, 45), ("F-CV 4/C 6%%D & 6%%D(E) 36C", 150, 45),
                    ("4P 50/30", 320, 45)):
        blk.add_text(s, dxfattribs={"height": 5.0, "insert": (x, y)})
    msp.add_blockref("CS", (1000, 0), dxfattribs={"xscale": 2, "yscale": 2})
    # --- 전동기 SCHEDULE
    _t(msp, "MCC-1", 2000, 100)
    _t(msp, "FROM: 수배전반", 2000, 90)
    _t(msp, "SCHEDULE", 2000, 50)
    for s, y in (("UNIT NO.", 40), ("EQPT. NAME", 30), ("kW", 20), ("VA", 10), ("MCCB P-AF/AT", 0), ("기 동 방 식", -10)):
        _t(msp, s, 2000, y)
    for x, vals in ((2100, ["F1", "소화펌프", "3%%c 5.5kW", "7500", "3P 50/40", "직입기동"]),
                    (2160, ["F2", "배수펌프", "3%%c 1.5kW", "2000", "3P 50/20", "직입기동"])):
        for v, y in zip(vals, (40, 30, 20, 10, 0, -10)):
            _t(msp, v, x, y)
    _t(msp, "1. 접 지 방 식 : 통합접지", 3000, 0)
    p = tmp_path / "plan.dxf"
    doc.saveas(p)
    return str(p)


def test_import_reads_all_tables(drawing):
    res = import_dxf(drawing)
    lp = res.panels["LP-1"]
    assert [c["no"] for c in lp["circuits"]] == ["L1", "R1"]                 # 예비 제외
    assert lp["circuits"][1]["at"] == "20" and lp["circuits"][1]["type"] == "ELB"   # 병합 셀 이어받기
    assert lp["circuits"][0]["phases"] == {"L1": 1500} and lp["circuits"][1]["phases"] == {"L2": 600}
    assert lp["main"]["at"] == "50" and lp["elb"] == {"ma": 15.0, "fast": True}
    b = res.boards[0]
    assert b["tr_kva"] == 500 and b["stage"] == "new" and b["acb"]["af"] == 800 and b["acb"]["set"] == 0.8
    assert {f["panel"] for f in b["feeders"]} == {"LP-1", "MCC-1"}
    cab = {c["to"]: c for c in res.cables}
    assert cab["LP-1"]["feeder"]["size"] == 10 and cab["LP-1"]["feeder"]["pe"] == 10 and cab["LP-1"]["breaker"] == (50, 50)
    ms = res.motors["MCC-1"]
    assert [(m["name"], m["kw"], m["va"], m["at"], m["start"]) for m in ms] == [
        ("소화펌프", 5.5, 7500, 40, "dol"), ("배수펌프", 1.5, 2000, 20, "dol")]


def test_cross_checks_and_questions(drawing):
    res = import_dxf(drawing)
    assert any("MCC-1" in w and "125AF/30AT" in w for w in res.warnings)      # 단선결선도 ≠ CABLE SCHEDULE
    assert any("통합접지" in n for n in res.notes)
    assert any("길이" in q for q in res.questions) and any("역률" in q for q in res.questions)


def test_imported_model_analyzes_without_inventing_values(drawing):
    res = import_dxf(drawing)
    src = res.source
    code = "\n".join(ln.split("//")[0] for ln in src.splitlines())
    assert "pf =" not in code and "length =" not in code and "sc_mva" not in code and "earthing" not in code
    r = analyze(src)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    assert r.scenarios["rated"].nodes["LP_1"].S == pytest.approx(2100)
    assert r.scenarios["rated"].nodes["MCC_1"].S == pytest.approx(9500)
    c = next(c for c in r.checks if c.id == "LP_1_R1:rcd_socket")
    assert c.status != "FAIL"                                                 # ELB 15 mA 주기 반영
    assert next(c for c in r.checks if c.id == "TR1:transformer_rating").status in ("PASS", "REVIEW")


def test_parse_feeder_forms():
    assert parse_feeder("F-CV 1/C 240㎟ x 4L & 120㎟(E) 104C") == {
        "text": "F-CV 1/C 240㎟ x 4L & 120㎟(E) 104C", "size": 240, "pe": 120, "insulation": "XLPE"}
    f = parse_feeder("1/C 150㎟ x4LINE,3FEEDER & FGV 240㎟ x1LINE (E) (ELP 100Ø x3)")
    assert f["size"] == 150 and f["parallel"] == 3 and f["pe"] == 240
    assert parse_feeder("T-FR-8(830℃/120min) 4/C 16㎟ & 16㎟(E) 54C")["size"] == 16


def test_gui_import(drawing):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ehdl.command import execute_command
    from ehdl.gui.main_window import EHDLMainWindow
    assert execute_command("", f"import {drawing}").action == "import"
    w = EHDLMainWindow()
    w._dirty = False
    res = w.import_dxf(drawing)
    assert res is not None and w.result.status == "OK" and w.path is None and w._dirty
    w._dirty = False
    w.close()
