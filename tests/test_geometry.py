"""T-GEO: 배관 길이 ↔ 좌표 기하 정합성 및 말단 요구압 미달 진단.

대상 코드:
  - SEM008 length < 끝점 3D 직선거리
  - SEM009 length 생략 + 끝점 x/y 미지정
  - auto_k 는 x/y 가 명시된 노드끼리만 산정
  - WRN006 말단 요구압 미달 (사양 선정 대상 펌프 없음)
"""
import sys
sys.path.insert(0, "src")

from fhdl.core.pipeline import AnalysisPipeline


def _run(code: str):
    return AnalysisPipeline().run(code)


def _codes(r):
    return [d.code for d in r.diagnostics]


_HEADER = """
system main { unit_system = METRIC; fluid = water; temp = 20; friction_model = DW; }
"""


def test_length_shorter_than_chord_warns():
    r = _run(_HEADER + """
tank t { z = 30m; x = 0; y = 0; }
terminal e { z = 0m; required_q = 50lpm; x = 40; y = 30; }
pipe p { start = t; end = e; length = 20m; diameter = 50mm; }
""")
    assert "SEM008" in _codes(r)


def test_length_not_shorter_than_chord_ok():
    r = _run(_HEADER + """
tank t { z = 30m; x = 0; y = 0; }
terminal e { z = 0m; required_q = 50lpm; x = 40; y = 0; }
pipe p { start = t; end = e; length = 60m; diameter = 50mm; }
""")
    assert "SEM008" not in _codes(r)


def test_chord_check_skipped_without_coordinates():
    """좌표를 적지 않은 노드는 기하 비교 대상이 아니다."""
    r = _run(_HEADER + """
tank t { z = 30m; }
terminal e { z = 0m; required_q = 50lpm; x = 400; y = 300; }
pipe p { start = t; end = e; length = 20m; diameter = 50mm; }
""")
    assert "SEM008" not in _codes(r)


def test_omitted_length_without_coordinates_warns():
    r = _run(_HEADER + """
tank t { z = 30m; }
terminal e { z = 0m; required_q = 50lpm; x = 40; y = 0; }
pipe p { start = t; end = e; diameter = 50mm; }
""")
    assert "SEM009" in _codes(r)


def test_auto_k_ignores_nodes_without_coordinates():
    """x/y 미지정 노드의 가짜 (0,0) 으로 꺾임각을 만들지 않는다."""
    r = _run(_HEADER + """
tank t { z = 30m; }
junction j { z = 10m; x = 50; y = 0; }
terminal e { z = 0m; required_q = 50lpm; x = 50; y = 50; }
pipe p1 { start = t; end = j; length = 60m; diameter = 50mm; }
pipe p2 { start = j; end = e; length = 60m; diameter = 50mm; }
""")
    k = {p.pipe_id: p.k_auto for p in r.pipe_results}
    assert k["p2"] == 0.0


def test_auto_k_applies_with_coordinates():
    r = _run(_HEADER + """
tank t { z = 10m; x = 0; y = 0; }
junction j { z = 10m; x = 50; y = 0; }
terminal e { z = 10m; required_q = 50lpm; x = 50; y = 50; }
pipe p1 { start = t; end = j; length = 60m; diameter = 50mm; }
pipe p2 { start = j; end = e; length = 60m; diameter = 50mm; }
""")
    k = {p.pipe_id: p.k_auto for p in r.pipe_results}
    assert k["p2"] > 0.0


def test_terminal_pressure_shortfall_warns_without_pump():
    """자연유하(펌프 없음)로 요구압을 못 내면 WRN006."""
    r = _run(_HEADER + """
tank t { z = 5m; }
terminal e { z = 0m; required_q = 100lpm; required_p = 0.3MPa; }
pipe p { start = t; end = e; length = 50m; diameter = 50mm; }
""")
    assert "WRN006" in _codes(r)


def test_terminal_pressure_met_no_warning():
    r = _run(_HEADER + """
tank t { z = 50m; }
terminal e { z = 0m; required_q = 50lpm; required_p = 0.1MPa; }
pipe p { start = t; end = e; length = 50m; diameter = 50mm; }
""")
    assert "WRN006" not in _codes(r)


def test_terminal_pressure_shortfall_suppressed_with_auto_pump():
    """AUTO 펌프가 있으면 부족분은 펌프 사양 선정 대상 → 경고하지 않는다."""
    r = _run(_HEADER + """
tank t { z = 5m; }
pump pu { z = 0m; }
terminal e { z = 0m; required_q = 100lpm; required_p = 0.3MPa; }
pipe s { start = t; end = pu; length = 5m; diameter = 50mm; }
pipe p { start = pu; end = e; length = 50m; diameter = 50mm; }
""")
    assert "WRN006" not in _codes(r)
    assert "WRN005" not in _codes(r)
    assert r.summary.recommended_pump_head > 0


def test_vacuum_still_warns_without_pump():
    """펌프 없는 계통의 실제 부압은 여전히 WRN005."""
    r = _run(_HEADER + """
tank t { z = 5m; }
terminal e { z = 0m; required_q = 200lpm; }
pipe p { start = t; end = e; length = 300m; diameter = 25mm; }
""")
    assert "WRN005" in _codes(r)
