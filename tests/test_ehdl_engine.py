"""T-EHDL: SPEC v0.1 검증 시나리오(TC-01~TC-09 중 Phase 1 범위) + 계산식 검산.

전류 = S/(√3·V), 전압강하 = KS C IEC 60364-5-52 부속서 G (ρ1 = 1.25ρ20, λ 기본 0.08 mΩ/m).
"""
import math
import os
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.judge import bottlenecks
from ehdl.pipeline import analyze

H = 'system plant { frequency = 60Hz; }\nsource SRC { voltage = 380V; phases = 3; %s }\n'
DB = os.path.join(os.path.dirname(__file__), "..", "data", "ehdl_kb.db")


def run(body, src_extra=""):
    r = analyze(H % src_extra + body)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    return r


def chk(r, cid):
    return next(c for c in r.checks if c.id == cid)


def node(r, nid, sc=None):
    return r.scenarios[sc or r.design_scenario].nodes[nid]


def test_tc01_load_sum_and_current():
    r = run("""
panel P { feed = SRC; rated_current = 300A; }
load E1 { parent = P; kind = general; rating = 50kW; basis = input; pf = 0.9; phases = 3; }
load E2 { parent = P; kind = general; rating = 50kW; basis = input; pf = 0.9; phases = 3; }
load E3 { parent = P; kind = general; rating = 25kW; basis = input; pf = 0.8; phases = 3; }
""")
    p = node(r, "P")
    assert p.P == pytest.approx(125000)
    q = 2 * 50000 * math.tan(math.acos(0.9)) + 25000 * math.tan(math.acos(0.8))
    assert p.Q == pytest.approx(q)                       # P·Q 를 따로 합산 (S 단순합 아님)
    assert p.current == pytest.approx(math.hypot(125000, q) / (math.sqrt(3) * 380))
    assert node(r, "SRC").P == pytest.approx(125000)     # 상위로 전달


def test_tc02_simultaneous_limit_exceeded():
    r = run("""
switchboard M { feed = SRC; }
load A { parent = M; kind = motor; rating = 60kW; basis = input; pf = 0.85; phases = 3; }
load B { parent = M; kind = motor; rating = 60kW; basis = input; pf = 0.85; phases = 3; }
load C { parent = M; kind = motor; rating = 60kW; basis = input; pf = 0.85; phases = 3; }
load D { parent = M; kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; }
scenario all_on { on = all; }
""", "limit_kw = 200kW;")
    c = chk(r, "SRC:source_limit")
    assert c.status == "FAIL" and c.actual == pytest.approx(210000)
    assert c.evidence.scenario in ("normal", "all_on")
    assert [b["target"] for b in bottlenecks(r)] == ["SRC"]


def test_group_constraint_max_demand():
    """동시운전 그룹: 3대 중 2대 운전 → 큰 것 2대로 최대 부하."""
    r = run("""
switchboard M { feed = SRC; }
group PUMPS { max_on = 2; }
load A { parent = M; kind = motor; rating = 60kW; basis = input; pf = 0.85; phases = 3; group = PUMPS; }
load B { parent = M; kind = motor; rating = 50kW; basis = input; pf = 0.85; phases = 3; group = PUMPS; }
load C { parent = M; kind = motor; rating = 40kW; basis = input; pf = 0.85; phases = 3; group = PUMPS; }
""", "limit_kw = 120kW;")
    assert r.design_scenario == "max_demand"
    assert node(r, "SRC").P == pytest.approx(110000)
    assert chk(r, "SRC:source_limit").status in ("PASS", "REVIEW")
    assert node(r, "SRC", "rated").P == pytest.approx(150000)   # 정격 합계는 따로 표시


def test_tc03_panel_feeder_bottleneck():
    r = run("""
switchboard MDB { feed = SRC; rated_current = 800A; }
panel PA { rated_current = 250A; }
cable FA { from = MDB; to = PA; length = 20m; length_basis = measured; material = Cu; size = 50mm2; ampacity = 150A; }
load L1 { parent = PA; kind = motor; rating = 55kW; basis = input; pf = 0.85; phases = 3; }
load L2 { parent = PA; kind = motor; rating = 55kW; basis = input; pf = 0.85; phases = 3; }
""", "limit_kw = 500kW;")
    assert chk(r, "SRC:source_limit").status in ("PASS", "REVIEW")
    assert chk(r, "MDB:board_rating").status == "PASS"
    assert chk(r, "FA:cable_ampacity").status == "FAIL"
    b = next(x for x in bottlenecks(r) if x["target"] == "FA")
    assert b["path"] == ["SRC", "MDB", "PA"] and set(b["causes"]) == {"L1", "L2"}


def test_tc05_oversize_asks_not_fails():
    # 350A 운전전류가 되도록 피상전력 역산: S = √3·380·350
    s_kva = math.sqrt(3) * 380 * 350 / 1000
    load = f"load L {{ parent = MDB; kind = general; rating = {s_kva:.4f}kVA; pf = 0.9; phases = 3; }}"
    r = run(f"switchboard MDB {{ feed = SRC; rated_current = 500A; }}\n{load}")
    c = chk(r, "MDB:board_rating")
    assert c.status == "PASS" and c.utilization == pytest.approx(0.70, abs=1e-3)
    rat = chk(r, "MDB:sizing_rationale")
    assert rat.status == "REVIEW" and "사용률은 70%" in rat.explanation
    assert any("향후 증설" in q for q in rat.questions)
    r2 = run(f'switchboard MDB {{ feed = SRC; rated_current = 500A; justification = "증설 100kW 예정"; }}\n{load}')
    assert chk(r2, "MDB:sizing_rationale").status == "PASS"


def _vd_model(length):
    return run(f"""
panel P {{ feed = SRC; }}
load M {{ parent = P; kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; }}
cable C {{ from = P; to = M; length = {length}m; length_basis = measured; material = Cu; size = 16mm2; x = 0.08mohm/m; }}
""")


def test_tc06_length_change_recomputes_vd():
    r30, r100 = _vd_model(30), _vd_model(100)
    I = 30000 / 0.85 / (math.sqrt(3) * 380)
    u = I * 30 * (0.0225 / 16 * 0.85 + 0.08e-3 * math.sqrt(1 - 0.85 ** 2))
    vd30 = chk(r30, "M:voltage_drop").actual
    assert vd30 == pytest.approx(u / (380 / math.sqrt(3)) * 100)
    assert chk(r100, "M:voltage_drop").actual == pytest.approx(vd30 * 100 / 30)
    assert chk(r30, "M:voltage_drop").status == "PASS"           # 실측 길이 + 원문 확인 규칙
    assert chk(r30, "M:voltage_drop").required.value == pytest.approx(5.0)


def test_vd_limit_over_100m_and_substation():
    r = run("""
transformer TR { feed = SRC; primary = 380V; secondary = 380V; rated = 300kVA; }
panel P { feed = TR; }
load LT { parent = P; kind = lighting; rating = 3kW; pf = 1.0; phases = 3; }
cable C { from = P; to = LT; length = 160m; length_basis = measured; material = Cu; size = 4mm2; }
""")
    c = chk(r, "LT:voltage_drop")
    assert c.required.value == pytest.approx(6.0 + 60 * 0.005)    # 고압 이상 수전(자가용 변전) 조명 6% + 가산
    assert any("기준 기본값" in d for d in c.evidence.defaults) and not c.evidence.assumptions


def test_tc08_missing_install_conditions_unknown():
    r = run("""
panel P { feed = SRC; }
load M { parent = P; kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; }
cable C { from = P; to = M; length = 30m; material = Cu; size = 16mm2; }
""")
    c = chk(r, "C:cable_ampacity")
    assert c.status == "UNKNOWN" and any("공사방법" in m for m in c.missing)
    assert "보류" in c.explanation and c.questions


def test_load_input_missing_is_unknown_not_assumed():
    r = run("""
panel P { feed = SRC; rated_current = 100A; }
load M { parent = P; kind = motor; rating = 37kW; pf = 0.85; phases = 3; }
""")
    c = chk(r, "M:load_input")
    assert c.status == "UNKNOWN" and any("basis" in m for m in c.missing)
    assert chk(r, "P:board_rating").status == "UNKNOWN"            # 빠진 부하가 있어 판정 보류


def test_tc09_collapsed_and_expanded_agree():
    """분전반 내부(parent)로 기술한 것과 배선(feed)으로 펼쳐 기술한 것의 집계가 같다."""
    inner = """
panel P { feed = SRC; rated_current = 200A; }
breaker CB { parent = P; rated_current = 100A; }
load A { feed = CB; kind = heater; rating = 20kW; pf = 1.0; phases = 3; }
load B { parent = P; kind = heater; rating = %skW; pf = 1.0; phases = 3; }
"""
    r1 = run(inner % "30")
    r2 = run(inner % "45")
    assert node(r1, "SRC").P == pytest.approx(50000) and node(r2, "SRC").P == pytest.approx(65000)
    assert node(r2, "P").P == node(r2, "SRC").P


def test_unbalance_and_single_phase_currents():
    r = run("""
panel P { feed = SRC; rated_current = 100A; }
load R1 { parent = P; kind = receptacle; rating = 4kW; pf = 1.0; phases = 1; phase = L1; }
load R2 { parent = P; kind = receptacle; rating = 1kW; pf = 1.0; phases = 1; phase = L2; }
load R3 { parent = P; kind = receptacle; rating = 1kW; pf = 1.0; phases = 1; phase = L3; }
""")
    p = node(r, "P")
    assert p.phase_current[0] == pytest.approx(4000 / (380 / math.sqrt(3)))
    u = chk(r, "P:unbalance")
    assert u.actual == pytest.approx((4000 - 1000) / (6000 / 3) * 100)
    assert u.status == "FAIL"                     # 150% > 30% (규칙 미확인이어도 위반은 표시)
    assert not u.evidence.rule.verified


def test_unassigned_phase_is_estimate():
    r = run("""
panel P { feed = SRC; rated_current = 100A; }
load R1 { parent = P; kind = receptacle; rating = 4kW; pf = 1.0; phases = 1; }
""")
    assert node(r, "P").balanced_estimate
    assert chk(r, "P:board_rating").status == "REVIEW"
    assert chk(r, "P:unbalance").status == "UNKNOWN"


def test_breaker_cable_coordination():
    r = run("""
panel P { feed = SRC; }
breaker CB { parent = P; rated_current = 63A; }
load M { kind = motor; rating = 20kW; basis = input; pf = 0.85; phases = 3; }
cable C { from = CB; to = M; length = 10m; length_basis = measured; material = Cu; size = 10mm2; ampacity = 57A; }
""")
    c = chk(r, "C:breaker_cable_coord")
    assert c.status == "FAIL" and "212.4.1" in c.evidence.rule.citation


@pytest.mark.skipif(not os.path.exists(DB), reason="지식 DB 없음")
def test_ampacity_from_kb_reference_conditions():
    r = run("""
panel P { feed = SRC; }
load M { parent = P; kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; }
cable C { from = P; to = M; length = 30m; material = Cu; size = 35mm2; insulation = XLPE; install_method = C; ambient = 30C; grouping = 1; }
cable C2 { from = P; to = M2; length = 30m; material = Cu; size = 35mm2; insulation = XLPE; install_method = C; ambient = 40C; grouping = 1; }
load M2 { kind = motor; rating = 30kW; basis = input; pf = 0.85; phases = 3; }
""")
    c = chk(r, "C:cable_ampacity")
    assert c.installed == 147.0 and c.status == "PASS" and "B.52.5" in c.evidence.defaults[0]
    c2 = chk(r, "C2:cable_ampacity")                       # Phase 2: 주위온도 보정 (표 B.52.14 XLPE 40℃ 0.91)
    assert c2.installed == pytest.approx(147.0 * 0.91) and c2.status == "PASS"


def test_topology_errors():
    r = analyze(H % "" + "panel P { rated_current = 100A; }\n")
    assert r.status == "FAILED" and any(d.code == "ENET002" for d in r.diagnostics)
    r = analyze("panel P { }\n")
    assert any(d.code == "ENET001" for d in r.diagnostics)
    r = analyze(H % "" + "load X { parent = NOPE; }\n")
    assert any(d.code == "ESEM002" for d in r.diagnostics)


def test_deterministic():
    a, b = _vd_model(42), _vd_model(42)
    assert [(c.id, c.status, c.actual) for c in a.checks] == [(c.id, c.status, c.actual) for c in b.checks]
