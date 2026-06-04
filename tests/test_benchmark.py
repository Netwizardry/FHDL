"""T-BENCH: 수리 계산 정확도 검증 — 독립 손계산 값과 대조.

솔버가 공식을 올바르게(단위·결선 포함) 적용하는지 해석적 기준값으로 확인한다.
"""
import math
import sys
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline

G = 9.80665


def _run(code):
    return AnalysisPipeline().run(code)


def test_velocity_exact():
    """유속 = Q / (πD²/4) 와 정확히 일치해야 한다."""
    code = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank s { z=50m; }
terminal t { z=0m; required_q=600lpm; }
pipe p { start=s; end=t; length=100m; diameter=100mm; material=Steel; }
connect s -> t;
"""
    pr = _run(code).pipe_results[0]
    Q = 600 / 60000.0          # m³/s
    A = math.pi * (0.1 / 2) ** 2
    v_expected = Q / A
    assert abs(pr.velocity - v_expected) < 1e-6
    assert abs(pr.flow - Q) < 1e-9


def test_hazen_williams_headloss_exact():
    """HW 마찰손실이 표준식 값과 일치해야 한다.

    h_f = 10.67 · L · Q^1.852 / (C^1.852 · D^4.87)
    """
    L, Q, D, C = 100.0, 0.01, 0.1, 120.0   # Steel C=120
    code = f"""
system m {{ unit_system=METRIC; fluid=water; temp=20; friction_model=HW; }}
tank s {{ z=80m; }}
terminal t {{ z=0m; required_q=600lpm; }}
pipe p {{ start=s; end=t; length=100m; diameter=100mm; material=Steel; }}
connect s -> t;
"""
    pr = _run(code).pipe_results[0]
    h_expected = 10.67 * L * (Q ** 1.852) / (C ** 1.852 * D ** 4.87)
    assert abs(pr.h_loss_f - h_expected) / h_expected < 0.01   # 1% 이내


def test_static_pressure_no_demand():
    """무유량 정수압: 게이지압 = ρg·(수두 − 고도)."""
    code = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank s { z=20m; level_max=0m; }
terminal t { z=5m; required_q=0lpm; }
pipe p { start=s; end=t; length=10m; diameter=100mm; material=Steel; }
connect s -> t;
"""
    r = _run(code)
    nt = {n.node_id: n for n in r.node_results}
    # 유량 0 → 손실 0 → 말단 수두 = 탱크 수두(20m), 압력 = ρg(20-5)
    rho = r.entity_map.fluid.density
    p_expected = (20.0 - 5.0) * rho * G
    assert abs(nt["t"].p_gauge - p_expected) / p_expected < 0.01


def test_series_loss_is_additive():
    """직렬 두 배관의 손실 합 = 단일 등가 배관 손실 (동일 유량)."""
    two = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank s { z=50m; }
junction j { z=25m; }
terminal t { z=0m; required_q=400lpm; }
pipe a { start=s; end=j; length=50m; diameter=80mm; material=Steel; }
pipe b { start=j; end=t; length=50m; diameter=80mm; material=Steel; }
connect s -> j -> t;
"""
    one = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank s { z=50m; }
terminal t { z=0m; required_q=400lpm; }
pipe a { start=s; end=t; length=100m; diameter=80mm; material=Steel; }
connect s -> t;
"""
    r2 = _run(two)
    loss2 = sum(p.h_loss_f for p in r2.pipe_results)
    r1 = _run(one)
    loss1 = r1.pipe_results[0].h_loss_f
    assert abs(loss2 - loss1) / loss1 < 0.02   # 2% 이내


def test_continuity_at_junction():
    """분기점 유입 = 유출 합 (질량 보존)."""
    code = """
system m { unit_system=METRIC; fluid=water; temp=20; }
tank s { z=30m; }
junction j { z=15m; }
terminal a { z=0m; required_q=120lpm; }
terminal b { z=0m; required_q=180lpm; }
pipe trunk { start=s; end=j; length=20m; diameter=100mm; material=Steel; }
pipe pa { start=j; end=a; length=10m; diameter=65mm; material=Steel; }
pipe pb { start=j; end=b; length=10m; diameter=65mm; material=Steel; }
connect s -> j; connect j -> a; connect j -> b;
"""
    q = {p.pipe_id: p.flow for p in _run(code).pipe_results}
    assert abs(q["trunk"] - (q["pa"] + q["pb"])) < 1e-9
    assert abs(q["trunk"] - 300 / 60000.0) < 1e-9
