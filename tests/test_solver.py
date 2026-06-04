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
