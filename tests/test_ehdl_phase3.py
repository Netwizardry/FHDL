"""T-EP3: EHDL Phase 3 — 접지계통·고장보호(전원 자동차단)·PE·등전위본딩·수전 종합·설계 변경 영향.

고장보호: KEC 211.2.5(TN) Zs×Ia ≤ U0, 211.2.6(TT) RA×IΔn ≤ 50 V, 211.2.7(IT) RA×Id ≤ 50 V — 손 계산과 비교.
"""
import math
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.impact import diff, summary
from ehdl.pipeline import analyze
from ehdl.report import tables

BASE = """system plant { frequency = 60Hz; %s }
source S { voltage = 22.9kV; phases = 3; sc_mva = 500MVA; rx = 0.1; }
transformer T { feed = S; primary = 22.9kV; secondary = 380V; rated = 1000kVA; uk = 6%%; ur = 1%%; }
switchboard MDB { feed = T; rated_current = 2000A; }
"""

FINAL = """breaker CB { parent = MDB; rated_current = %(In)sA; curve = C; breaking_capacity = 50kA; }
cable C1 { from = CB; to = L; length = %(L)sm; material = Cu; size = 2.5mm2; pe_size = 2.5mm2; length_basis = measured; }
load L { kind = heater; rating = 2kW; pf = 1; phases = 3; }
"""


def run(body, sys_extra="earthing = TN-S;"):
    r = analyze(BASE % sys_extra + body)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    return r


def chk(r, cid):
    return next(c for c in r.checks if c.id == cid)


def _zs(L):
    zb = 380 ** 2 / 1e6
    zt = complex(0.01 * zb, math.sqrt(0.06 ** 2 - 0.01 ** 2) * zb)
    return zt + complex(0.0225 * L / 2.5 * 2, 0.08e-3 * L)


def test_tn_fault_loop_matches_hand_calculation():
    r = run(FINAL % {"In": 16, "L": 50})
    c = chk(r, "L:fault_protection")
    u0 = 380 / math.sqrt(3)
    assert c.actual == pytest.approx(u0 / abs(_zs(50)), rel=1e-6)
    assert c.installed == pytest.approx(10 * 16)                   # C 곡선 순시 상한 10·In (표 212.3-3)
    assert c.evidence.values["허용 차단시간(s)"] == 0.4             # 표 211.2-1 TN 230 V 분기회로
    assert c.status == "REVIEW"                                    # 충족, 변압기 영상 임피던스 가정 → REVIEW
    assert "211.2.5" in c.evidence.rule.citation


def test_tn_long_final_circuit_fails():
    c = chk(run(FINAL % {"In": 16, "L": 120}), "L:fault_protection")
    assert c.status == "FAIL" and c.actual < c.installed


def test_over_32a_uses_5s_and_asks_for_curve():
    c = chk(run(FINAL % {"In": 63, "L": 120}), "L:fault_protection")
    assert c.evidence.values["허용 차단시간(s)"] == 5               # 32 A 초과 → TN 5 s
    assert c.status == "REVIEW" and any("제조사" in a for a in c.evidence.assumptions)


def test_missing_earthing_is_unknown():
    c = chk(run(FINAL % {"In": 16, "L": 50}, sys_extra=""), "L:fault_protection")
    assert c.status == "UNKNOWN" and "계통접지" in c.missing[0]


TT_BODY = """rcd R { parent = MDB; rated_current = 40A; sensitivity = 30mA; }
cable C1 { from = R; to = L; length = 30m; material = Cu; size = 4mm2; pe_size = 4mm2; }
load L { kind = general; rating = 3kW; pf = 0.9; phases = 3; }
"""


@pytest.mark.parametrize("ra,status", [(100, "PASS"), (2000, "FAIL")])
def test_tt_ra_times_idn(ra, status):
    c = chk(run(TT_BODY, sys_extra=f"earthing = TT; ra = {ra};"), "L:fault_protection")
    assert c.actual == pytest.approx(ra * 0.03) and c.status == status
    assert "211.2.6" in c.evidence.rule.citation


def test_tn_c_forbids_rcd():
    r = run(TT_BODY, sys_extra="earthing = TN-C;")
    assert chk(r, "R:tnc_rcd").status == "FAIL"


@pytest.mark.parametrize("extra,status", [("", "REVIEW"), ("insulation_monitor = yes;", "PASS")])
def test_it_first_fault(extra, status):
    r = run(FINAL % {"In": 16, "L": 50}, sys_extra=f"earthing = IT; ra = 10; id_first_fault = 1A; {extra}")
    c = chk(r, "S:it_first_fault")
    assert c.actual == pytest.approx(10.0) and c.status == status
    assert not any(x.kind == "fault_protection" for x in r.checks)  # IT 는 1차 고장 판정만


def test_pe_minimum_table():
    body = """breaker CB { parent = MDB; rated_current = 200A; curve = C; breaking_capacity = 50kA; }
cable C1 { from = CB; to = L; length = 20m; material = Cu; size = 95mm2; pe_size = 35mm2; }
load L { kind = heater; rating = 50kW; pf = 1; phases = 3; }
"""
    c = chk(run(body), "C1:pe_size")
    assert c.required.value == pytest.approx(47.5) and c.actual == 35 and c.status == "FAIL"   # S > 35 → S/2
    c = chk(run(body.replace("pe_size = 35mm2", "pe_size = 50mm2")), "C1:pe_size")
    assert c.status == "PASS"
    from ehdl.judge3 import pe_min
    from ehdl.rules import load_ruleset
    rules = load_ruleset("kec_lv")
    assert [pe_min(rules, s) for s in (10, 25, 70)] == [10, 16, 35]


@pytest.mark.parametrize("size,status", [(4, "FAIL"), (6, "PASS")])
def test_main_bonding_minimum(size, status):
    body = FINAL % {"In": 16, "L": 50} + f"""earth MET {{ kind = main_terminal; }}
earth W {{ kind = extraneous; }}
bond B {{ from = MET; to = W; kind = main; material = Cu; size = {size}mm2; }}
"""
    c = chk(run(body), "B:bonding")
    assert c.required.value == 6 and c.actual == size and c.status == status                    # max(Cu 6, 2.5/2)


def test_supply_summary_and_contract():
    body = FINAL % {"In": 16, "L": 50}
    c = chk(run(body, sys_extra="earthing = TN-S; contract_kw = 1kW;"), "S:supply_summary")
    assert c.status == "FAIL" and c.actual == pytest.approx(2000)
    c = chk(run(body, sys_extra="earthing = TN-S; contract_kw = 100kW;"), "S:supply_summary")
    assert c.status == "REVIEW"                                    # 계약전력 규칙 원문 미확인
    assert c.evidence.values["최대수요전력(kW)"] == pytest.approx(2.0)
    assert tables(run(body))["SUPPLY"]["rows"]


def test_design_change_impact():
    old = run(FINAL % {"In": 16, "L": 50})
    new = run(FINAL % {"In": 16, "L": 120})
    ch = diff(old, new)
    fp = next(d for d in ch if d["id"] == "L:fault_protection")
    assert fp["change"] == "worse" and fp["old"] == "REVIEW" and fp["new"] == "FAIL"
    assert ch[0]["change"] == "worse" and "악화" in summary(ch)
    assert diff(old, run(FINAL % {"In": 16, "L": 50})) == []
    assert summary([]) == "판정 변화 없음"
