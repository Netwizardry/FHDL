"""T-NET: 네트워크 토폴로지 진단 및 다중 구조 수리 검증.

대상 코드:
  - NET001 고립 노드 / NET003 도달 불가 / NET004 복합 루프 / NET005 Dead Loop
  - 다중 분기 · 다중 급수 · 다중 출력 · 고도 변경 시나리오
"""
import sys
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline


def _run(code: str):
    return AnalysisPipeline().run(code)


def _codes(r):
    return [d.code for d in r.diagnostics]


def _q_lpm(r):
    """파이프 ID → 유량(lpm) 딕셔너리."""
    return {p.pipe_id: p.flow * 60000.0 for p in r.pipe_results}


def _pressure(r):
    """노드 ID → 게이지 압력(Pa)."""
    return {n.node_id: n.p_gauge for n in r.node_results}


_HEADER = """
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    friction_model = DW;
}
"""


# ===========================================================================
# 네트워크 진단
# ===========================================================================

def test_net001_isolated_node():
    """배관에 연결되지 않은 고립 노드 → NET001."""
    code = _HEADER + """
    tank src { elevation = 10m; }
    terminal t1 { elevation = 0m; required_q = 60lpm; }
    junction orphan { elevation = 5m; }
    pipe p1 { start = src; end = t1; length = 20m; diameter = 50mm; material = Steel; }
    connect src -> t1;
    """
    r = _run(code)
    assert "NET001" in _codes(r)
    # 고립 노드 진단 메시지에 노드명 포함
    net001 = [d for d in r.diagnostics if d.code == "NET001"]
    assert any("orphan" in d.message for d in net001)


def test_net003_unreachable_node():
    """공급원에서 도달 불가한 분리 서브그래프 → NET003."""
    code = _HEADER + """
    tank src { elevation = 10m; }
    terminal t1 { elevation = 0m; required_q = 60lpm; }
    junction j2 { elevation = 5m; }
    terminal t2 { elevation = 0m; required_q = 40lpm; }
    pipe p1 { start = src; end = t1; length = 20m; diameter = 50mm; material = Steel; }
    pipe p2 { start = j2;  end = t2; length = 20m; diameter = 50mm; material = Steel; }
    connect src -> t1;
    connect j2 -> t2;
    """
    r = _run(code)
    assert "NET003" in _codes(r)


def test_net005_dead_loop():
    """공급원과 무관한 순환 루프 → NET005 (Dead Loop)."""
    code = _HEADER + """
    tank src { elevation = 10m; }
    terminal t1 { elevation = 0m; required_q = 60lpm; }
    junction a { elevation = 5m; }
    junction b { elevation = 5m; }
    pipe p1  { start = src; end = t1; length = 20m; diameter = 50mm; material = Steel; }
    pipe pab { start = a;   end = b;  length = 10m; diameter = 50mm; material = Steel; }
    pipe pba { start = b;   end = a;  length = 10m; diameter = 50mm; material = Steel; }
    connect src -> t1;
    connect a -> b;
    connect b -> a;
    """
    r = _run(code)
    assert "NET005" in _codes(r)
    # NET005는 ERROR 등급
    net005 = [d for d in r.diagnostics if d.code == "NET005"]
    assert all(d.severity == "ERROR" for d in net005)


def test_net004_complex_loop_warning():
    """공급원과 연결된 복합 루프 → NET004 (WARNING, 비차단)."""
    code = _HEADER + """
    tank src { elevation = 10m; }
    junction a { elevation = 6m; }
    junction b { elevation = 5m; }
    terminal t1 { elevation = 0m; required_q = 60lpm; }
    pipe p0 { start = src; end = a;  length = 10m; diameter = 50mm; material = Steel; }
    pipe p1 { start = a;   end = b;  length = 10m; diameter = 50mm; material = Steel; }
    pipe p2 { start = b;   end = a;  length = 10m; diameter = 50mm; material = Steel; }
    pipe p3 { start = a;   end = t1; length = 10m; diameter = 50mm; material = Steel; }
    connect src -> a;
    connect a -> b;
    connect b -> a;
    connect a -> t1;
    """
    r = _run(code)
    assert "NET004" in _codes(r)
    assert r.status != "FAILED"  # 경고이므로 해석은 계속


def test_clean_tree_no_net_diag():
    """정상 트리 구조에는 NET 진단이 없어야 한다."""
    code = _HEADER + """
    tank src { elevation = 10m; }
    junction j { elevation = 5m; }
    terminal ta { elevation = 2m; required_q = 50lpm; }
    terminal tb { elevation = 2m; required_q = 50lpm; }
    pipe trunk { start = src; end = j;  length = 20m; diameter = 50mm; material = Steel; }
    pipe ba    { start = j;   end = ta; length = 10m; diameter = 50mm; material = Steel; }
    pipe bb    { start = j;   end = tb; length = 10m; diameter = 50mm; material = Steel; }
    connect src -> j;
    connect j -> ta;
    connect j -> tb;
    """
    r = _run(code)
    net = [c for c in _codes(r) if c.startswith("NET")]
    assert net == []


# ===========================================================================
# 다중 분기 (2단계 트리)
# ===========================================================================

def test_multi_branch_mass_conservation():
    """2단계 분기 트리: 각 분기점에서 질량 보존이 성립해야 한다."""
    code = _HEADER + """
    tank src { elevation = 15m; }
    junction j1 { elevation = 10m; }
    junction j2 { elevation = 8m; }
    terminal ta { elevation = 5m; required_q = 30lpm; }
    terminal tb { elevation = 4m; required_q = 40lpm; }
    terminal tc { elevation = 3m; required_q = 50lpm; }
    pipe trunk { start = src; end = j1; length = 20m; diameter = 80mm; material = Steel; }
    pipe a     { start = j1;  end = ta; length = 10m; diameter = 50mm; material = Steel; }
    pipe mid   { start = j1;  end = j2; length = 10m; diameter = 65mm; material = Steel; }
    pipe b     { start = j2;  end = tb; length = 10m; diameter = 50mm; material = Steel; }
    pipe c     { start = j2;  end = tc; length = 10m; diameter = 50mm; material = Steel; }
    connect src -> j1;
    connect j1 -> ta;
    connect j1 -> j2;
    connect j2 -> tb;
    connect j2 -> tc;
    """
    r = _run(code)
    assert r.status != "FAILED"
    q = _q_lpm(r)
    # 말단 유량
    assert abs(q["a"] - 30.0) < 1e-6
    assert abs(q["b"] - 40.0) < 1e-6
    assert abs(q["c"] - 50.0) < 1e-6
    # j2 분기점 보존: mid = b + c
    assert abs(q["mid"] - (q["b"] + q["c"])) < 1e-6
    # j1 분기점 보존: trunk = a + mid
    assert abs(q["trunk"] - (q["a"] + q["mid"])) < 1e-6
    # 간선 = 전체 수요
    assert abs(q["trunk"] - 120.0) < 1e-6


# ===========================================================================
# 다중 급수 (병렬 공급원)
# ===========================================================================

def test_multi_source_supply_split():
    """2개 탱크가 공통 분기점에 급수: 공급 유량 합 = 수요."""
    code = _HEADER + """
    tank src1 { elevation = 12m; }
    tank src2 { elevation = 12m; }
    junction j { elevation = 6m; }
    terminal t1 { elevation = 0m; required_q = 100lpm; }
    pipe a { start = src1; end = j;  length = 15m; diameter = 50mm; material = Steel; }
    pipe b { start = src2; end = j;  length = 15m; diameter = 50mm; material = Steel; }
    pipe c { start = j;    end = t1; length = 20m; diameter = 65mm; material = Steel; }
    connect src1 -> j;
    connect src2 -> j;
    connect j -> t1;
    """
    r = _run(code)
    assert r.status != "FAILED"
    assert "NET003" not in _codes(r)  # 양쪽 공급원 모두 정상 연결
    q = _q_lpm(r)
    # 하류 배관 = 전체 수요
    assert abs(q["c"] - 100.0) < 1e-6
    # 공급 보존: 두 공급원 합 = 하류
    assert abs((q["a"] + q["b"]) - q["c"]) < 1e-6
    # 동일 조건이므로 균등 분담
    assert abs(q["a"] - q["b"]) < 1e-6


# ===========================================================================
# 다중 출력
# ===========================================================================

def test_multi_terminal_total_flow():
    """4개 말단의 요구 유량 합이 총 유량으로 집계되어야 한다."""
    code = _HEADER + """
    tank src { elevation = 20m; }
    junction j { elevation = 10m; }
    terminal t1 { elevation = 5m; required_q = 10lpm; }
    terminal t2 { elevation = 5m; required_q = 20lpm; }
    terminal t3 { elevation = 5m; required_q = 30lpm; }
    terminal t4 { elevation = 5m; required_q = 40lpm; }
    pipe trunk { start = src; end = j; length = 20m; diameter = 80mm; material = Steel; }
    pipe p1 { start = j; end = t1; length = 5m; diameter = 40mm; material = Steel; }
    pipe p2 { start = j; end = t2; length = 5m; diameter = 40mm; material = Steel; }
    pipe p3 { start = j; end = t3; length = 5m; diameter = 50mm; material = Steel; }
    pipe p4 { start = j; end = t4; length = 5m; diameter = 50mm; material = Steel; }
    connect src -> j;
    connect j -> t1; connect j -> t2; connect j -> t3; connect j -> t4;
    """
    r = _run(code)
    assert r.status != "FAILED"
    # 총 유량 = 100lpm = 0.0016667 m³/s
    assert abs(r.summary.total_flow * 60000.0 - 100.0) < 1e-6
    q = _q_lpm(r)
    assert abs(q["trunk"] - 100.0) < 1e-6


# ===========================================================================
# 고도 변경
# ===========================================================================

def test_elevation_affects_pressure():
    """동일 조건에서 말단 고도가 높을수록 게이지 압력이 낮아야 한다."""
    code = _HEADER + """
    tank src { elevation = 30m; }
    junction j { elevation = 10m; }
    terminal t_low  { elevation = 0m;  required_q = 50lpm; }
    terminal t_high { elevation = 15m; required_q = 50lpm; }
    pipe trunk { start = src; end = j; length = 10m; diameter = 80mm; material = Steel; }
    pipe lo { start = j; end = t_low;  length = 10m; diameter = 50mm; material = Steel; }
    pipe hi { start = j; end = t_high; length = 10m; diameter = 50mm; material = Steel; }
    connect src -> j;
    connect j -> t_low;
    connect j -> t_high;
    """
    r = _run(code)
    assert r.status != "FAILED"
    p = _pressure(r)
    # 같은 유량/관경/길이이지만 고도가 높은 말단의 압력이 더 낮다
    assert p["t_high"] < p["t_low"]


def test_elevation_increases_required_head():
    """말단 고도를 높이면 권장 펌프 양정(required_head)이 증가해야 한다."""
    base = _HEADER + """
    tank src { elevation = 5m; }
    terminal t1 { elevation = __Z__m; required_q = 80lpm; }
    pipe p1 { start = src; end = t1; length = 30m; diameter = 50mm; material = Steel; }
    connect src -> t1;
    """
    r_low = _run(base.replace("__Z__", "0"))
    r_high = _run(base.replace("__Z__", "20"))
    assert r_high.summary.required_head > r_low.summary.required_head
