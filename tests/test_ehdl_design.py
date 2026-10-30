"""T-EDS: EHDL 기본설계 — 전선 규격 후보(SPEC 5.3)·최소 단락전류 순시 동작/차단 범위(SPEC 5.7·5.8)."""
import os
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.pipeline import analyze
from ehdl.rules import load_ruleset
from ehdl.sizing import STANDARD_SIZES, _dv_at

DB = os.path.join(os.path.dirname(__file__), "..", "data", "ehdl_kb.db")

BASE = """system plant { frequency = 60Hz; earthing = TN-S; }
source S { voltage = 22.9kV; phases = 3; sc_mva = 500MVA; rx = 0.1; }
transformer T { feed = S; primary = 22.9kV; secondary = 380V; rated = 1000kVA; uk = 6%%; ur = 1%%; }
switchboard MDB { feed = T; rated_current = 2000A; }
breaker CB { parent = MDB; rated_current = %(In)sA; curve = C; breaking_capacity = 50kA; trip_time = 0.02s; }
cable C1 { from = CB; to = L; length = %(L)sm; material = Cu; insulation = PVC; %(extra)s }
load L { kind = heater; rating = %(kw)skW; pf = 1; phases = 3; }
"""


def run(**kw):
    v = {"In": 63, "L": 200, "kw": 20, "extra": ""}
    v.update(kw)
    r = analyze(BASE % v)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    return r


def chk(r, cid):
    return next(c for c in r.checks if c.id == cid)


def test_design_mode_gives_size_from_voltage_drop():
    r = run()                                         # 단면적 미입력 = 기본설계
    c = chk(r, "C1:cable_size")
    assert c.installed is None and c.actual in STANDARD_SIZES
    assert "전압강하" in c.required.quantity
    # 산정값은 허용치를 만족하고 한 단계 아래 표준 단면적은 만족하지 않는다
    rules = load_ruleset("kec_lv")
    nr = r.scenarios[r.design_scenario].nodes["L"]
    from ehdl.judge import vd_limit
    lim = vd_limit(r, rules, "L", nr)
    i = STANDARD_SIZES.index(c.actual)
    assert _dv_at(r, rules, "C1", nr, c.actual) <= lim < _dv_at(r, rules, "C1", nr, STANDARD_SIZES[i - 1])
    assert c.evidence.values["후보1(㎟)"] == c.actual and c.evidence.values["후보2(㎟)"] == STANDARD_SIZES[i + 1]
    assert r.model.edges["C1"].installed.get("size") is None     # 산정 중 모델을 바꾸지 않음
    # 허용전류 조건은 공사방법 등이 없어 산정 불가 → 판정 보류(가정하지 않음)
    assert c.status == "UNKNOWN" and any("허용전류" in x for x in c.missing)


def test_installed_size_checked_against_requirement():
    need = chk(run(), "C1:cable_size").actual
    small = STANDARD_SIZES[STANDARD_SIZES.index(need) - 1]
    c = chk(run(extra=f"size = {small}mm2; ampacity = 200A;"), "C1:cable_size")
    assert c.status == "FAIL" and c.installed == small
    c = chk(run(extra=f"size = {need}mm2; ampacity = 200A;"), "C1:cable_size")
    assert c.status in ("PASS", "REVIEW")


@pytest.mark.skipif(not os.path.exists(DB), reason="지식 DB 없음")
def test_ampacity_and_coordination_condition_from_table():
    # 짧은 배선 → 허용전류·In 협조가 지배. In 63 A 이므로 IZ ≥ 63 A 인 최소 단면적
    c = chk(run(L=5, kw=30, extra="install_method = C; ambient = 30C; grouping = 1;"), "C1:cable_size")
    v = c.evidence.values
    assert v["필요 IZ(A)"] >= 63 and v["IZ(S)(A)"] >= 63
    assert c.actual >= v["허용전류·보호협조 최소(㎟)"] and c.status == "N/A"      # 모든 조건 산정 → 판정 대상 아님(기본설계)
    # 변압기 가까이(약 20 kA, 0.02 s): PVC 는 열적 내량이 지배한다 — 식 212.5-1
    assert v["단락 열적 내량 최소(㎟)"] >= v["S ≥ Is·√t/k(㎟)"]


def test_thermal_condition_uses_min_short_circuit():
    c = chk(run(L=5), "C1:cable_size")
    v = c.evidence.values
    assert v["단락 열적 내량 최소(㎟)"] >= v["S ≥ Is·√t/k(㎟)"] and v["k"] == 115


def test_sc_min_trip_long_line_is_review_with_curve_question():
    c = chk(run(In=16, L=400, kw=2, extra="size = 2.5mm2;"), "CB:sc_min_trip")
    assert c.actual < c.installed == pytest.approx(10 * 16)
    assert c.status == "REVIEW" and any("장한시" in a for a in c.evidence.assumptions) and c.questions
    assert c.evidence.values["차단 범위 부하 수"] == 1


def test_sc_min_trip_short_line_instantaneous():
    c = chk(run(In=16, L=5, kw=2, extra="size = 2.5mm2;"), "CB:sc_min_trip")
    assert c.actual >= c.installed and c.status in ("PASS", "REVIEW")
    assert not any("장한시" in a for a in c.evidence.assumptions)
