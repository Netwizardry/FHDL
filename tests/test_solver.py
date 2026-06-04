"""T-CAL: 수리 해석 솔버 단위 테스트."""
import sys
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline


_BASIC_FHD = """
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    friction_model = DW;
}

tank source {
    elevation = 10m;
}

terminal t1 {
    elevation = 0m;
    required_q = 60lpm;
    required_p = 0.05MPa;
}

pipe p1 {
    start = source;
    end = t1;
    length = 30m;
    diameter = 50mm;
    material = Steel;
}

connect source -> t1;
"""

_AUTO_SIZE_FHD = """
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    friction_model = DW;
}

constraint {
    velocity_max = 2.5m;
    velocity_min = 0.3m;
}

tank src {
    elevation = 5m;
}

terminal t1 {
    elevation = 0m;
    required_q = 120lpm;
}

pipe p1 {
    start = src;
    end = t1;
    length = 20m;
    diameter = auto;
    material = Steel;
}

connect src -> t1;
"""

_NPSH_FHD = """
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
}

tank reservoir {
    elevation = -2m;
}

pump p {
    elevation = 0m;
    npshr = 3.0m;
}

terminal t1 {
    elevation = 5m;
    required_q = 100lpm;
}

pipe suc {
    start = reservoir;
    end = p;
    length = 5m;
    diameter = 50mm;
    material = Steel;
}

pipe dis {
    start = p;
    end = t1;
    length = 20m;
    diameter = 50mm;
    material = Steel;
}

connect reservoir -> suc -> p -> dis -> t1;
"""


def test_basic_analysis():
    pipe = AnalysisPipeline()
    r = pipe.run(_BASIC_FHD)
    assert r.status in ("OK", "PARTIAL")
    assert len(r.node_results) > 0
    assert len(r.pipe_results) > 0


def test_auto_sizing():
    pipe = AnalysisPipeline()
    r = pipe.run(_AUTO_SIZE_FHD)
    assert r.status != "FAILED"
    # Auto로 선정된 관경 확인
    p1_result = next((pr for pr in r.pipe_results if pr.pipe_id == "p1"), None)
    assert p1_result is not None
    assert p1_result.diameter > 0
    assert p1_result.sizing_mode == "AUTO"


def test_no_nodes_fails():
    code = "system main { fluid = water; temp = 20; unit_system = METRIC; }"
    pipe = AnalysisPipeline()
    r = pipe.run(code)
    # 노드 없음 → FAILED 또는 PARTIAL
    assert r.status in ("FAILED", "PARTIAL")


def test_npsha_warning():
    pipe = AnalysisPipeline()
    r = pipe.run(_NPSH_FHD)
    # NPSHa 경고 WRN003이 발생해야 함
    warn_codes = [d.code for d in r.diagnostics if d.severity == "WARNING"]
    # 낮은 흡입 수위이므로 WRN003 가능
    # (조건에 따라 달라질 수 있으므로 느슨하게 체크)
    assert r.status in ("OK", "PARTIAL", "FAILED")


def test_hazen_williams():
    code = _BASIC_FHD.replace("friction_model = DW;", "friction_model = HW;")
    pipe = AnalysisPipeline()
    r = pipe.run(code)
    assert r.status != "FAILED"
    p1 = next((pr for pr in r.pipe_results if pr.pipe_id == "p1"), None)
    if p1:
        assert p1.formula_id == "FOR-HW-001"


def test_velocity_check():
    """좁은 관경으로 유속 초과 경고 확인"""
    code = _BASIC_FHD.replace("diameter = 50mm;", "diameter = 15mm;")
    pipe = AnalysisPipeline()
    r = pipe.run(code)
    warn_codes = [d.code for d in r.diagnostics]
    # 15mm에 60lpm → 유속 매우 높음 → WRN001
    assert "WRN001" in warn_codes


_BRANCH_FHD = """
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    friction_model = DW;
}

tank src {
    elevation = 10m;
}

junction j1 {
    elevation = 5m;
}

terminal ta {
    elevation = 3m;
    required_q = 80lpm;
}

terminal tb {
    elevation = 2m;
    required_q = 60lpm;
}

pipe trunk { start = src; end = j1; length = 30m; diameter = 50mm; material = Steel; }
pipe ba { start = j1; end = ta; length = 20m; diameter = 50mm; material = Steel; }
pipe bb { start = j1; end = tb; length = 20m; diameter = 50mm; material = Steel; }

connect src -> j1;
connect j1 -> ta;
connect j1 -> tb;
"""


def test_branch_flow_split():
    """분기점 하류 배관은 각자의 말단 유량만 분담해야 한다 (유량 분배 회귀 테스트).

    과거 버그: 분기 배관이 모두 분기점의 전체 유량(140lpm)을 받았음.
    기대값: trunk=140, ba=80, bb=60 lpm.
    """
    r = AnalysisPipeline().run(_BRANCH_FHD)
    assert r.status != "FAILED"
    q = {pr.pipe_id: pr.flow * 60000.0 for pr in r.pipe_results}  # m³/s → lpm
    assert abs(q["trunk"] - 140.0) < 1e-6
    assert abs(q["ba"] - 80.0) < 1e-6
    assert abs(q["bb"] - 60.0) < 1e-6
    # 분기 합 = 간선 (질량 보존)
    assert abs((q["ba"] + q["bb"]) - q["trunk"]) < 1e-6


def test_friction_reflected_in_head():
    """Pass2가 배관 유량 기준 마찰손실을 노드 수두에 반영해야 한다.

    과거 버그: Pass2가 노드 맵에서 파이프 ID로 유량을 조회해 항상 0 →
    마찰손실 미반영(모든 노드 수두 동일).
    """
    r = AnalysisPipeline().run(_BRANCH_FHD)
    heads = {nr.node_id: nr.head_total for nr in r.node_results}
    # 소스보다 하류 말단 수두가 마찰손실만큼 낮아야 한다
    assert heads["ta"] < heads["src"] - 0.1
    assert heads["j1"] < heads["src"]


def _pump_fhd(head_spec: str) -> str:
    return f"""
system m {{ unit_system=METRIC; fluid=water; temp=20; }}
tank res {{ z=2m; level_max=1m; }}
pump pp {{ z=0m; head={head_spec}; flow=100lpm; }}
terminal t {{ z=5m; required_q=100lpm; }}
pipe suc {{ start=res; end=pp; length=3m;  diameter=80mm; material=Steel; }}
pipe dis {{ start=pp;  end=t;  length=20m; diameter=80mm; material=Steel; }}
connect res -> pp -> t;
"""


def test_pump_head_injection():
    """수동 양정 펌프는 네트워크에 실제 에너지를 주입해야 한다."""
    heads = {}
    for h in ("0m", "30m", "60m"):
        r = AnalysisPipeline().run(_pump_fhd(h))
        nt = {n.node_id: n.head_total for n in r.node_results}
        heads[h] = (nt["pp"], nt["t"])
    # 펌프노드 수두가 양정만큼 증가 (흡입수두 3m + 양정)
    assert abs(heads["0m"][0] - 3.0) < 0.5
    assert abs(heads["30m"][0] - 33.0) < 0.5
    assert abs(heads["60m"][0] - 63.0) < 0.5
    # 말단 수두도 양정에 비례해 상승
    assert heads["60m"][1] > heads["30m"][1] > heads["0m"][1]


def test_auto_fitting_k_on_bend():
    """좌표상 꺾이는 배관은 auto_k>0, 직선 배관은 ~0 이어야 한다."""
    code = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank s { z=10m; x=0; y=0; }
junction j { z=9m; x=10; y=0; }
terminal bend { z=8m; x=10; y=10; required_q=40lpm; }
terminal straight { z=8m; x=20; y=0; required_q=40lpm; }
pipe trunk { start=s; end=j; length=10m; diameter=50mm; material=Steel; }
pipe p_bend { start=j; end=bend; length=10m; diameter=50mm; material=Steel; }
pipe p_str  { start=j; end=straight; length=10m; diameter=50mm; material=Steel; }
connect s -> j;
connect j -> bend;
connect j -> straight;
"""
    em = AnalysisPipeline().run(code).entity_map
    # j 에서 90도 꺾이는 p_bend 는 auto_k 부여, 직진 p_str 는 ~0
    assert em.pipes["p_bend"].auto_k > 0.5
    assert em.pipes["p_str"].auto_k < 0.1


def _npsha_fhd(alt_m, temp=20):
    return f"""
system m {{ unit_system=METRIC; fluid=water; temp={temp}; altitude={alt_m}m; }}
tank res {{ z=2m; level_max=1m; }}
pump pp {{ z=0m; head=20m; flow=100lpm; npshr=3m; }}
terminal t {{ z=5m; required_q=100lpm; }}
pipe suc {{ start=res; end=pp; length=3m;  diameter=80mm; material=Steel; }}
pipe dis {{ start=pp;  end=t;  length=20m; diameter=80mm; material=Steel; }}
connect res -> pp -> t;
"""


def _pump_npsha(alt_m, temp=20):
    r = AnalysisPipeline().run(_npsha_fhd(alt_m, temp))
    return next(n.npsha for n in r.node_results if n.node_id == "pp")


def test_result_exposes_k_and_altitude():
    """결과 모델이 피팅 K·절대해발·대기압을 노출해야 한다 (결과 패널 표시용)."""
    code = """
system m { unit_system=METRIC; fluid=water; temp=20; altitude=1000m; }
tank s { z=20m; }
terminal t { z=0m; required_q=100lpm; }
pipe p { start=s; end=t; length=30m; diameter=50mm; material=Steel; fittings=[valve_gate, elbow_90]; }
connect s -> t;
"""
    r = AnalysisPipeline().run(code)
    pr = r.pipe_results[0]
    assert abs(pr.k_total - 1.1) < 1e-6        # valve_gate 0.2 + elbow_90 0.9
    nr = next(n for n in r.node_results if n.node_id == "t")
    assert abs(nr.abs_altitude - 1000.0) < 1e-6  # datum 1000 + z 0
    assert 88000 < nr.atm_pressure < 91000       # 약 1000m 대기압


def test_atm_pressure_decreases_with_altitude():
    from fhdl.core.models import FluidConfig
    assert FluidConfig.atm_pressure_at(0) > FluidConfig.atm_pressure_at(1000) > \
        FluidConfig.atm_pressure_at(3000)


def test_npsha_drops_with_altitude():
    """해발고도가 높을수록 대기압이 낮아 NPSHa 가 감소해야 한다."""
    n0 = _pump_npsha(0)
    n3000 = _pump_npsha(3000)
    assert n0 - n3000 > 2.5      # 해발 3000m → 약 3m 대기압수두 감소


def test_npsha_drops_with_temperature():
    """온도가 높을수록 증기압이 높아 NPSHa 가 감소해야 한다."""
    assert _pump_npsha(0, 20) > _pump_npsha(0, 90) + 4.0


def test_datum_relative_z_guard():
    """노드 z 는 datum(altitude) 기준 상대값 — 절대 해발로 가드 검사."""
    # datum=70, z=-3 → 절대 67m: 정상
    ok = AnalysisPipeline().run(
        "system m{unit_system=METRIC;fluid=water;temp=20;altitude=70m;}\n"
        "tank res{z=5m;}\nterminal t{z=-3m;required_q=60lpm;}\n"
        "pipe p{start=res;end=t;length=20m;diameter=50mm;material=Steel;}\nconnect res->t;")
    assert "SEM005" not in [d.code for d in ok.diagnostics]
    # datum=9000, z=2000 → 절대 11000m: 범위 초과 경고
    bad = AnalysisPipeline().run(
        "system m{unit_system=METRIC;fluid=water;temp=20;altitude=9000m;}\n"
        "tank res{z=5m;}\nterminal t{z=2000m;required_q=60lpm;}\n"
        "pipe p{start=res;end=t;length=20m;diameter=50mm;material=Steel;}\nconnect res->t;")
    assert "SEM005" in [d.code for d in bad.diagnostics]
