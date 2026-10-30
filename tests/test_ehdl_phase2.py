"""T-EP2: EHDL Phase 2 — 단락전류·차단용량(TC-07)·열적 내량·보호협조·전동기 기동(TC-04)·누전·SPD·허용전류 보정.

단락: 전기설비 검사·점검 기준 220.1.2 (KS C IEC 60909-0) — 손 계산과 비교.
"""
import math
import os
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.pipeline import analyze

DB = os.path.join(os.path.dirname(__file__), "..", "data", "ehdl_kb.db")
SQ3 = math.sqrt(3)

BASE = """system plant { frequency = 60Hz; %s }
source S { voltage = 22.9kV; phases = 3; sc_mva = 500MVA; rx = 0.1; }
transformer T { feed = S; primary = 22.9kV; secondary = 380V; rated = 1000kVA; uk = 6%%; ur = 1%%; }
switchboard MDB { feed = T; rated_current = 2000A; }
"""


def run(body, sys_extra=""):
    r = analyze(BASE % sys_extra + body)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    return r


def chk(r, cid):
    return next(c for c in r.checks if c.id == cid)


def _hand_bus():
    zq = 1.1 * 22900 ** 2 / 500e6 * (380 / 22900) ** 2
    xq = zq / math.sqrt(1.01)
    zb = 380 ** 2 / 1e6
    xt = math.sqrt(0.06 ** 2 - 0.01 ** 2)
    kt = 0.95 * 1.05 / (1 + 0.6 * xt)
    return complex(0.1 * xq, xq) + complex(0.01 * zb, xt * zb) * kt


def test_short_circuit_matches_hand_calculation():
    r = run("load H { parent = MDB; kind = heater; rating = 10kW; pf = 1; phases = 3; }")
    z = _hand_bus()
    assert r.sc["MDB"].ik_max == pytest.approx(1.05 * 380 / (SQ3 * abs(z)))
    # 최소: cmin 0.95, KT 없음 → 최대보다 작다
    assert r.sc["MDB"].ik_min < r.sc["MDB"].ik_max
    # 전원 점: c 가 약분되어 S''k/(√3·Un)
    assert r.sc["S"].ik_max == pytest.approx(500e6 / (SQ3 * 22900))


def test_tc07_breaking_capacity_shortfall():
    r = run("breaker CB { parent = MDB; rated_current = 100A; standard = IEC60947-2; instantaneous = 10; breaking_capacity = 10kA; }\n"
            "load H { feed = CB; kind = heater; rating = 20kW; pf = 1; phases = 3; }")
    c = chk(r, "CB:breaking_capacity")
    assert c.status == "FAIL" and c.actual > 12000 and c.installed == 10000
    assert "212.5.5" in c.evidence.rule.citation


def test_breaking_capacity_backup_is_review():
    r = run("breaker UP { parent = MDB; rated_current = 400A; instantaneous = 10; breaking_capacity = 50kA; }\n"
            "breaker CB { feed = UP; rated_current = 100A; instantaneous = 10; breaking_capacity = 10kA; }\n"
            "load H { feed = CB; kind = heater; rating = 20kW; pf = 1; phases = 3; }")
    c = chk(r, "CB:breaking_capacity")
    assert c.status == "REVIEW" and any("후비보호" in a for a in c.evidence.assumptions)


def test_short_circuit_unknown_without_supply_data():
    r = analyze("source S { voltage = 380V; phases = 3; }\nswitchboard M { feed = S; }\n"
                "breaker CB { parent = M; rated_current = 50A; breaking_capacity = 10kA; }\n"
                "load H { feed = CB; kind = heater; rating = 5kW; pf = 1; phases = 3; }")
    c = chk(r, "CB:breaking_capacity")
    assert c.status == "UNKNOWN" and any("sc_mva" in x for x in c.missing)


def test_motor_contribution_decays_downstream():
    r = run("""
load M1 { parent = MDB; kind = motor; rating = 90kW; basis = input; pf = 0.85; phases = 3; start_multiplier = 7; }
panel P { feed = MDB; }
cable F { from = MDB; to = P; length = 150m; material = Cu; size = 16mm2; insulation = XLPE; }
load H { parent = P; kind = heater; rating = 5kW; pf = 1; phases = 3; }
""")
    assert r.sc["MDB"].motor_contrib > 900
    assert r.sc["P"].motor_contrib < 0.2 * r.sc["MDB"].motor_contrib


def test_thermal_withstand():
    body = """
breaker CB { parent = MDB; rated_current = 32A; standard = IEC60898; curve = C; breaking_capacity = 50kA; trip_time = %s; }
load H { kind = heater; rating = 10kW; pf = 1; phases = 3; }
cable C { from = CB; to = H; length = 5m; material = Cu; size = 2.5mm2; insulation = PVC; ampacity = 34A; }
"""
    bad = chk(run(body % "2s"), "C:thermal")
    r = run(body % "2s")
    ik = r.sc["H"].ik_min
    assert bad.actual == pytest.approx(ik * math.sqrt(2) / 115)       # 식 212.5-1, k(Cu PVC) = 115
    assert bad.status == "FAIL"
    fast = chk(run(body % "0.01s"), "C:thermal")                       # 0.1초 미만: 공식만으로 FAIL 하지 않음
    assert fast.status == "REVIEW" and any("통과 I²t" in a for a in fast.evidence.assumptions)
    lt = body.replace("trip_time = %s;", "trip_time = 0.01s; let_through_i2t = 30000;")
    assert chk(run(lt), "C:thermal").status in ("PASS", "REVIEW")       # k²S² 82656 ≥ 30000
    lt2 = body.replace("trip_time = %s;", "trip_time = 0.01s; let_through_i2t = 200000;")
    assert chk(run(lt2), "C:thermal").status == "FAIL"


def test_selectivity_review_when_fault_reaches_upstream_instantaneous():
    r = run("breaker UP { parent = MDB; rated_current = 250A; instantaneous = 10; breaking_capacity = 50kA; }\n"
            "breaker CB { feed = UP; rated_current = 63A; curve = C; breaking_capacity = 50kA; }\n"
            "load H { feed = CB; kind = heater; rating = 20kW; pf = 1; phases = 3; }")
    c = chk(r, "CB:selectivity")
    assert c.status == "REVIEW" and c.installed == pytest.approx(2500)


def _motor(beta=6.5, delta="", lim="motor_start_vd_limit = 15%;"):
    return run(f"""
load A {{ parent = MDB; kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; }}
breaker CB {{ parent = MDB; rated_current = 100A; standard = IEC60947-2; instantaneous = 12; breaking_capacity = 50kA; {delta} }}
load B {{ kind = motor; rating = 37kW; basis = output; efficiency = 93%; pf = 0.86; phases = 3;
          start_multiplier = {beta}; start_time = 4s; start_pf = 0.3; }}
cable C {{ from = CB; to = B; length = 80m; length_basis = measured; material = Cu; size = 25mm2; insulation = XLPE; ampacity = 119A; }}
""", lim)


def test_tc04_motor_start_not_judged_by_rating_alone():
    r = _motor(delta="start_trip_multiple = 7.5;")
    vd = chk(r, "B:motor_start_vd")
    pr = chk(r, "B:motor_start_protection")
    assert vd.actual > chk(r, "B:voltage_drop").actual          # 기동 강하 > 정상 강하
    assert vd.status == "PASS" and vd.required.value == pytest.approx(15.0)
    assert pr.actual > 100                                      # 기동전류 > 정격 100 A 인데도
    assert pr.status == "PASS"                                  # 순시(12 In)·δ(7.5) 아래 → 트립 아님


def test_motor_start_trips_and_unknowns():
    assert chk(_motor(beta=14, delta="start_trip_multiple = 7.5;"), "B:motor_start_protection").status == "FAIL"
    assert chk(_motor(), "B:motor_start_protection").status == "REVIEW"       # δ 미입력 → 제조사 곡선 확인
    assert chk(_motor(lim=""), "B:motor_start_vd").status == "REVIEW"         # 한도 없음 → 값과 질문


def test_rcd_socket_requirement():
    r = run("""
panel P { feed = MDB; }
rcd ELB { parent = P; rated_current = 30A; sensitivity = 30mA; }
load R1 { feed = ELB; kind = receptacle; rating = 2kW; pf = 1; phases = 1; phase = L1; socket_rating = 16A; }
load R2 { parent = P; kind = receptacle; rating = 2kW; pf = 1; phases = 1; phase = L2; socket_rating = 16A; }
load R3 { parent = P; kind = receptacle; rating = 2kW; pf = 1; phases = 1; phase = L3; socket_rating = 32A; }
""")
    assert chk(r, "R1:rcd_socket").status == "REVIEW"       # 감도 30 mA 충족, 감도 조항 미확인
    assert chk(r, "R2:rcd_socket").status == "FAIL"         # 누전차단기 없음 (KEC 211.2.3의 4)
    assert chk(r, "R3:rcd_socket").status == "N/A"          # 20 A 초과


def test_overload_condition_two_evidence():
    r = run("breaker CB { parent = MDB; rated_current = 63A; standard = IEC60947-2; instantaneous = 10; breaking_capacity = 50kA; }\n"
            "load H { kind = heater; rating = 20kW; pf = 1; phases = 3; }\n"
            "cable C { from = CB; to = H; length = 10m; material = Cu; size = 16mm2; ampacity = 70A; }")
    c = chk(r, "C:breaker_cable_coord")
    assert c.status == "PASS" and c.evidence.values["I2(A)"] == pytest.approx(1.3 * 63)


@pytest.mark.skipif(not os.path.exists(DB), reason="지식 DB 없음")
def test_ampacity_corrections_from_kb():
    def iz(extra):
        r = run("load H { parent = MDB; kind = heater; rating = 10kW; pf = 1; phases = 3; }\n"
                "cable C { from = MDB; to = H2; length = 10m; material = Cu; size = 35mm2; insulation = XLPE; "
                f"install_method = C; {extra} }}\nload H2 {{ kind = heater; rating = 10kW; pf = 1; phases = 3; }}")
        return chk(r, "C:cable_ampacity")
    assert iz("ambient = 40C; grouping = 3; arrangement = 1;").installed == pytest.approx(147 * 0.91 * 0.70)
    c = iz("ambient = 42C; grouping = 10;")                       # 표 사이 → 바로 위 값(45℃, 12회로), 항 1 가정
    assert c.installed == pytest.approx(147 * 0.87 * 0.45) and c.status == "REVIEW"


def test_spd_review_question():
    r = run("load H { parent = MDB; kind = heater; rating = 10kW; pf = 1; phases = 3; }")
    c = chk(r, "S:spd")
    assert c.status == "REVIEW" and c.questions
