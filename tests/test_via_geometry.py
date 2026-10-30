"""T-VIA: 배관 경유점(via)·숨은 엘보·테이크오프·단관 절단 길이·부속 위치(@).

대상:
  - core.geometry (경로·꺾임각·테이크오프·절단 길이)
  - via → length 자동, auto_k 에 꺾임 엘보 가산, SEM008(via 경로)·SEM010·SEM011
  - fittings 위치 문법 name@2m / @1500mm / @50%
  - dsl_editor z ↔ elevation 별칭, 콘솔 dwg 명령
"""
import math
import sys
sys.path.insert(0, "src")

from fhdl.core.command import execute_command
from fhdl.core.dsl_editor import set_node_attributes
from fhdl.core.fittings import fitting_k, parse_fitting_placements, parse_fittings, sum_fittings_k
from fhdl.core.geometry import bend_angles, elbow_takeoff_m, polyline_length, spool_cut_lengths
from fhdl.core.pipeline import AnalysisPipeline
from fhdl.core.pipe_sizes import nominal_size


def _run(code: str):
    return AnalysisPipeline().run(code)


def _codes(r):
    return [d.code for d in r.diagnostics]


_HEADER = """
system main { unit_system = METRIC; fluid = water; temp = 20; friction_model = DW; }
"""

_VIA = _HEADER + """
tank t { z = 20m; x = 0; y = 0; }
terminal e { z = 0m; required_q = 50lpm; x = 40; y = 30; }
pipe p { start = t; end = e; via = [(0, 0, 0), (40, 0, 0)]; diameter = 50mm; %s }
"""


# --- core.geometry --------------------------------------------------------------

def test_elbow_takeoff_matches_ks_jis_long_elbow():
    """참고 자료: 100A 90° 롱 엘보 = 4 inch × 25.4 × 1.5 = 152.4 mm, 45° = 152.4·tan22.5° = 63.12 mm."""
    d100 = nominal_size(0.1023).inner_d_m
    assert abs(elbow_takeoff_m(d100, 90.0) * 1000 - 152.4) < 0.01
    assert abs(elbow_takeoff_m(d100, 45.0) * 1000 - 63.13) < 0.02
    assert elbow_takeoff_m(d100, 0.0) == 0.0


def test_spool_cut_lengths_reference_example():
    """참고 자료 SPOOL: 100A, 500 → UP 400 → 800 : A=500−152.4, B=400−2×152.4, C=800−152.4."""
    pts = [(0, 0, 0), (0.5, 0, 0), (0.5, 0, 0.4), (0.5, 0.8, 0.4)]
    cuts = [s.cut_m * 1000 for s in spool_cut_lengths(pts, 0.1023)]
    assert [round(c, 1) for c in cuts] == [347.6, 95.2, 647.6]
    assert bend_angles(pts) == [90.0, 90.0]
    assert abs(polyline_length(pts) - 1.7) < 1e-12


# --- via in the engine -------------------------------------------------------------

def test_via_sets_length_from_route():
    r = _run(_VIA % "")
    assert r.status == "OK"
    assert abs(r.entity_map.pipes["p"].length - 90.0) < 1e-9   # 20 (하강) + 40 + 30
    assert "SEM008" not in _codes(r)


def test_via_bends_add_elbow_k():
    r = _run(_VIA % "")
    k = {p.pipe_id: p.k_auto for p in r.pipe_results}
    assert abs(k["p"] - 2 * fitting_k("elbow_90")) < 1e-9       # 꺾임 2곳 모두 90°


def test_length_shorter_than_via_route_warns():
    r = _run(_VIA % "length = 80m;")
    msgs = [d.message for d in r.diagnostics if d.code == "SEM008"]
    assert msgs and "경유점" in msgs[0]


def test_via_without_endpoint_coordinates_warns_and_is_ignored():
    r = _run(_HEADER + """
tank t { z = 20m; }
terminal e { z = 0m; required_q = 50lpm; x = 40; y = 30; }
pipe p { start = t; end = e; length = 80m; via = [(0, 0, 0)]; diameter = 50mm; }
""")
    assert "SEM010" in _codes(r)
    assert r.entity_map.pipes["p"].via == []


def test_malformed_via_point_warns():
    r = _run(_VIA.replace("(0, 0, 0), (40, 0, 0)", "(0, 0), (40, 0, 0)") % "")
    assert "SEM010" in _codes(r)
    assert r.entity_map.pipes["p"].via == [(40.0, 0.0, 0.0)]


def test_junction_turn_uses_route_end_directions():
    """노드 꺾임각은 배관 끝 구간 방향으로 잰다: 직진으로 이어지면 노드 엘보 K 없음."""
    r = _run(_HEADER + """
tank t { z = 10m; x = 0; y = 0; }
junction j { z = 10m; x = 50; y = 50; }
terminal e { z = 10m; required_q = 50lpm; x = 100; y = 50; }
pipe p1 { start = t; end = j; via = [(0, 50, 10)]; diameter = 50mm; }
pipe p2 { start = j; end = e; diameter = 50mm; }
""")
    k = {p.pipe_id: p.k_auto for p in r.pipe_results}
    assert abs(k["p1"] - fitting_k("elbow_90")) < 1e-9     # via 꺾임 1곳
    assert k["p2"] == 0.0                                   # p1 끝 방향(동) = p2 방향(동)


# --- fitting positions -------------------------------------------------------------

def test_fitting_position_syntax():
    fps = parse_fitting_placements("[valve_gate@2m, elbow_90*2@50%, valve_ball@1500mm, flow_meter]")
    assert [(f.canon, f.count, f.at_m, f.at_frac) for f in fps] == [
        ("valve_gate", 1, 2.0, None), ("elbow_90", 2, None, 0.5),
        ("valve_ball", 1, 1.5, None), ("flow_meter", 1, None, None)]
    # 위치 표기는 K 합산·기존 파서에 영향 없음
    assert parse_fittings("[valve_gate@2m, elbow_90*2]") == [("valve_gate", 1), ("elbow_90", 2)]
    assert abs(sum_fittings_k("[valve_gate@2m, elbow_90*2]") - 2.0) < 1e-9


def test_fitting_position_beyond_length_warns():
    r = _run(_VIA % "fittings = [valve_gate@95m];")
    assert "SEM011" in _codes(r)
    r = _run(_VIA % "fittings = [valve_gate@5m];")
    assert "SEM011" not in _codes(r)


# --- editing / commands ------------------------------------------------------------

def test_set_z_updates_elevation_alias():
    src = "junction j1 {\n    elevation = 5m;\n    x = 1;\n}\n"
    out = set_node_attributes(src, "j1", {"z": "7m"})
    assert "elevation = 7m;" in out and "\n    z =" not in out
    src2 = "junction j1 {\n    z = 5m;\n}\n"
    assert "z = 7m;" in set_node_attributes(src2, "j1", {"z": "7m"})


def test_dwg_command():
    r = execute_command("", "dwg plan")
    assert r.action == "drawing" and r.args == {"view": "plan"}
    r = execute_command("", "dwg export out.dxf views=iso,pid")
    assert r.action == "drawing" and r.args == {"path": "out.dxf", "views": ["iso", "pid"]}
    assert execute_command("", "dwg export out.doc").level == "ERROR"
    assert execute_command("", "dwg export out.pdf views=top").level == "ERROR"
