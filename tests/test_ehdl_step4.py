"""T-EP4: EHDL 혼합 모드(SPEC 4.3) · 기동 방식(검사·점검 기준 240.3.1) · 차단기 설정(SPEC 3.4) · 변경 이력(SPEC 8)."""
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.mixed import mixed_impact
from ehdl.pipeline import analyze

BASE = """system plant { frequency = 60Hz; earthing = TN-S; }
source S { voltage = 22.9kV; phases = 3; sc_mva = 500MVA; rx = 0.1; }
transformer T { feed = S; primary = 22.9kV; secondary = 380V; rated = 1000kVA; uk = 6%; ur = 1%; }
switchboard MDB { feed = T; rated_current = 2000A; }
"""


def run(body, head=BASE):
    r = analyze(head + body)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    return r


def chk(r, cid):
    return next(c for c in r.checks if c.id == cid)


# ---- 혼합 모드 ---------------------------------------------------------------------------------
MIXED = """panel P { parent = MDB; rated_current = 100A; }
load A { parent = P; kind = heater; rating = 40kW; pf = 1; phases = 3; }
load B { parent = P; kind = heater; rating = 30kW; pf = 1; phases = 3; stage = new; }
"""


def test_mixed_mode_existing_scenario_and_bottleneck():
    r = run(MIXED)
    assert set(r.scenarios["existing"].on_loads) == {"A"}
    row = next(x for x in mixed_impact(r) if x["target"] == "P")
    assert row["verdict"] == "신규 부하로 초과" and row["util_before"] < 1 < row["util_after"] and row["new_loads"] == ["B"]
    c = chk(r, "P:board_rating")
    assert c.status == "FAIL" and "병목" in c.explanation and c.evidence.values["신규 부하 전 사용률(%)"] < 100
    from ehdl.judge import bottlenecks
    assert next(b for b in bottlenecks(r) if b["target"] == "P")["new_load_caused"]


def test_new_panel_makes_its_loads_new():
    r = run("""panel Q { parent = MDB; rated_current = 100A; stage = new; }
load C { parent = Q; kind = heater; rating = 10kW; pf = 1; phases = 3; }""")
    assert "C" not in r.scenarios["existing"].on_loads


def test_no_new_means_no_mixed_scenario():
    r = run(MIXED.replace(" stage = new;", ""))
    assert "existing" not in r.scenarios and mixed_impact(r) == []


def test_invalid_stage_is_error():
    r = analyze(BASE + MIXED.replace("stage = new", "stage = future"))
    assert any(d.code == "ESEM005" for d in r.diagnostics)


# ---- 기동 방식 ---------------------------------------------------------------------------------
MOTOR = """breaker CB { parent = MDB; rated_current = 100A; curve = C; breaking_capacity = 50kA; }
cable C1 { from = CB; to = M; length = 20m; material = Cu; size = 25mm2; }
load M { kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; start_multiplier = 6; start_pf = 0.3;
         start_time = 5s; %s }
"""


def _ist(r):
    return chk(r, "M:motor_start_protection").evidence.values["Ims(A)"]


def test_start_method_coefficients():
    dol = _ist(run(MOTOR % ""))
    assert _ist(run(MOTOR % "start_method = star_delta;")) == pytest.approx(dol * 0.33, abs=1)
    assert _ist(run(MOTOR % "start_method = reactor; start_tap = 0.65;")) == pytest.approx(dol * 0.65, abs=1)
    ir = run(MOTOR % "").scenarios["rated"].nodes["M"].current
    assert _ist(run(MOTOR % "start_method = inverter; start_limit = 1.5;")) == pytest.approx(1.5 * ir, abs=1)
    c = chk(run(MOTOR % ""), "M:motor_start_vd")
    assert any("전전압 기동" in d for d in c.evidence.defaults)       # 미입력 = 보수적 기본


def test_soft_starter_without_limit_asks():
    c = chk(run(MOTOR % "start_method = soft_starter;"), "M:motor_start_vd")
    assert c.status == "UNKNOWN" and any("3.5∼5" in x for x in c.missing)


def test_star_delta_avoids_instantaneous_trip():
    # 전전압 6 × 54 A ≈ 322 A → C 곡선 100 A 순시 하한 500 A 아래지만 δ 미입력 → REVIEW, Y-△ 로 기동전류 1/3
    r = run(MOTOR % "start_method = star_delta;")
    assert chk(r, "M:motor_start_protection").evidence.values["Ims/In"] < 2


# ---- 차단기 설정 ---------------------------------------------------------------------------------
LOAD = """breaker CB { parent = MDB; rated_current = 100A; standard = IEC60947-2; instantaneous = 10; breaking_capacity = 50kA;
                %s }
cable C1 { from = CB; to = L; length = 30m; material = Cu; size = 25mm2; ampacity = 90A; }
load L { kind = heater; rating = 40kW; pf = 1; phases = 3; }
"""


def test_ir_setting_used_for_overload_and_coordination():
    r = run(LOAD % "")
    assert chk(r, "C1:breaker_cable_coord").status == "FAIL"          # In 100 > Iz 90
    r = run(LOAD % "ir_setting = 0.8;")
    assert chk(r, "CB:breaker_load").installed == pytest.approx(80)
    assert chk(r, "C1:breaker_cable_coord").status in ("PASS", "REVIEW")


def test_short_time_zone_counts_as_operation():
    far = LOAD.replace("length = 30m", "length = 400m")
    c = chk(run(far % ""), "CB:sc_min_trip")
    assert c.status == "REVIEW" and c.actual < c.installed
    c = chk(run(far % "short_time = 2; short_time_delay = 0.2s;"), "CB:sc_min_trip")
    assert c.actual >= c.installed == pytest.approx(200) and not any("장한시" in a for a in c.evidence.assumptions)


def test_ics_below_fault_is_review_and_rated_voltage():
    r = run(LOAD % "ics = 5kA; rated_voltage = 220V;")
    c = chk(r, "CB:breaking_capacity")
    assert c.status == "REVIEW" and any("Ics" in a for a in c.evidence.assumptions)
    assert chk(r, "CB:rated_voltage").status == "FAIL"
    assert chk(run(LOAD % "rated_voltage = 415V;"), "CB:rated_voltage").status == "PASS"


def test_rcd_series_selectivity():
    body = """rcd R1 { parent = MDB; rated_current = 100A; sensitivity = 300mA; rcd_type = %s; }
rcd R2 { feed = R1; rated_current = 40A; sensitivity = 30mA; rcd_type = fast; }
load L { feed = R2; kind = general; rating = 3kW; pf = 0.9; phases = 3; }
"""
    c = chk(run(body % "fast"), "R2:rcd_selectivity")
    assert c.status == "REVIEW" and c.evidence.assumptions and c.questions
    c = chk(run(body % "delayed"), "R2:rcd_selectivity")
    assert c.status == "REVIEW" and not c.evidence.assumptions and not c.questions   # 시간·감도 분리, 조항 미확인
    assert c.evidence.rule.id == "RCD_TYPES"


# ---- 변경 이력 ---------------------------------------------------------------------------------
def test_block_diff_and_history_file(tmp_path):
    from ehdl.history import append, block_diff, describe, for_target, load, make_entry
    old = BASE + MIXED
    new = old.replace("rated_current = 100A; }", "rated_current = 125A; }").replace(
        "load B {", "load D { parent = P; kind = heater; rating = 1kW; pf = 1; phases = 3; }\nload B {")
    edits = {e["id"]: e for e in block_diff(old, new)}
    assert edits["P"]["change"] == "modified" and edits["P"]["attrs"]["rated_current"] == ["100A", "125A"]
    assert edits["D"]["change"] == "added" and "B" not in edits
    e = make_entry(old, new, run(MIXED), run(new[len(BASE):]))
    assert "개선" in e["verdict"] and e["counts"]
    ehd = tmp_path / "main.ehd"
    append(str(ehd), e)
    (tmp_path / "main.history.jsonl").open("a").write("{broken\n")      # 손상된 줄은 건너뜀
    hist = load(str(ehd))
    assert len(hist) == 1 and for_target(hist, "P")[0][1] == describe(edits["P"])
    assert make_entry(old, old) is None


def test_gui_save_records_history(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ehdl.gui.main_window import EHDLMainWindow
    p = tmp_path / "main.ehd"
    p.write_text(BASE + MIXED, encoding="utf-8")
    w = EHDLMainWindow()
    w.open_file(str(p))
    w.editor.set_source(w.editor.get_source().replace("100A", "125A"))
    w._run()
    w._save()
    assert len(w.history) == 1 and w.history[0]["edits"][0]["id"] == "P"
    assert w.results.t_history.rowCount() == 1
    from ehdl.report import export_report
    out = export_report(w.result, str(tmp_path / "r.html"), "t", history=w.history)
    assert "변경 이력" in open(out, encoding="utf-8").read()
    w._dirty = False
    w.close()
