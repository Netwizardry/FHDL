"""T-SYN-001 계열: DSL 인플레이스 편집 (Inverse Sync) 단위 테스트."""
import sys
sys.path.insert(0, "src")

from fhdl.core.dsl_editor import (
    add_connection, add_link, add_pipe, has_link, remove_connection,
    remove_link, remove_pipe, set_constraint_attributes, set_node_attributes,
    set_pipe_attributes, default_pipe_id,
)
from fhdl.core.parser import FHDLParser
from fhdl.core.semantic import SemanticAnalyzer

_SRC = """system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
}

tank src {
    z = 10m;
    x = 0; y = 0;
}

terminal t1 {
    z = 0m;
    required_q = 60lpm;
}

pipe p1 {
    start = src;
    end = t1;
    length = 30m;
    diameter = auto;
    material = Steel;
}

connect src -> t1;
"""


def _analyze(src: str):
    ast, _ = FHDLParser().parse(src)
    return SemanticAnalyzer().analyze(ast)[0]


# --- 속성 편집 / 좌표 역반영 ------------------------------------------------

def test_set_existing_attribute():
    out = set_node_attributes(_SRC, "t1", {"required_q": "120lpm"})
    assert "required_q = 120lpm;" in out
    assert "required_q = 60lpm;" not in out
    # 재파싱으로 의미 확인
    t = _analyze(out).terminals["t1"]
    assert abs(t.required_q * 60000 - 120) < 1e-6


def test_set_adds_missing_attribute():
    out = set_node_attributes(_SRC, "t1", {"required_p": "0.05MPa"})
    assert "required_p = 0.05MPa;" in out
    t = _analyze(out).terminals["t1"]
    assert t.required_p > 0


def test_set_coordinates_inverse_sync():
    """그래프에서 바꾼 좌표(x,y,z)가 DSL 텍스트에 반영되어야 한다."""
    out = set_node_attributes(_SRC, "src", {"x": "25", "y": "-8", "z": "12m"})
    s = _analyze(out).tanks["src"]
    assert s.x == 25.0 and s.y == -8.0 and s.elevation == 12.0


def test_set_preserves_comments_and_other_nodes():
    src = _SRC.replace("tank src {", "// 공급 탱크\ntank src {")
    out = set_node_attributes(src, "src", {"z": "15m"})
    assert "// 공급 탱크" in out          # 주석 보존
    assert "terminal t1 {" in out          # 다른 노드 보존
    assert "z = 15m;" in out


def test_set_unknown_node_noop():
    out = set_node_attributes(_SRC, "ghost", {"z": "1m"})
    assert out == _SRC


def test_empty_value_skipped():
    out = set_node_attributes(_SRC, "t1", {"required_q": ""})
    assert "required_q = 60lpm;" in out    # 빈 값은 무시


# --- connect 편집 ----------------------------------------------------------

def test_add_connection():
    out = add_connection(_SRC, "src", "j2")
    assert "connect src -> j2;" in out


def test_add_connection_idempotent():
    out = add_connection(_SRC, "src", "t1")
    assert out.count("connect src -> t1;") == 1


def test_remove_connection():
    out = remove_connection(_SRC, "src", "t1")
    assert "connect src -> t1;" not in out


# --- pipe 편집 -------------------------------------------------------------

def test_set_pipe_attributes():
    out = set_pipe_attributes(_SRC, "p1", {"length": "45m", "material": "PVC"})
    assert "length = 45m;" in out
    assert "material = PVC;" in out
    em = _analyze(out)
    assert em.pipes["p1"].length == 45.0
    # 다른 블록·연결 보존
    assert "tank src {" in out and "connect src -> t1;" in out


def test_set_pipe_diameter_and_fittings():
    out = set_pipe_attributes(_SRC, "p1", {"diameter": "80mm", "fittings": "[elbow_90, valve_gate]"})
    em = _analyze(out)
    assert abs(em.pipes["p1"].diameter.value - 0.08) < 1e-9
    assert em.pipes["p1"].manual_k > 0    # 피팅 K 반영


def test_add_and_remove_pipe():
    out = add_pipe(_SRC, "p2", "src", "t1", length="5m")
    assert "pipe p2 {" in out
    back = remove_pipe(out, "p2")
    assert "pipe p2 {" not in back


# --- 드래그 연결 (pipe + connect) ------------------------------------------

def test_add_link_creates_pipe_and_connect():
    out = add_link(_SRC, "src", "t2", length="12m")
    pid = default_pipe_id("src", "t2")
    assert f"pipe {pid} {{" in out
    assert "connect src -> t2;" in out


def test_add_link_then_parse_ok():
    """추가된 연결이 파서/시맨틱을 통과해야 한다."""
    src = _SRC + "\njunction j2 { z = 5m; }\n"
    out = add_link(src, "j2", "t1", length="8m")
    em = _analyze(out)
    assert default_pipe_id("j2", "t1") in em.pipes


def test_remove_link():
    out = add_link(_SRC, "src", "t2")
    back = remove_link(out, "src", "t2")
    assert default_pipe_id("src", "t2") not in back
    assert "connect src -> t2;" not in back


def test_set_constraint_existing_block():
    src = _SRC + "\nconstraint {\n    velocity_max = 2.5m;\n}\n"
    out = set_constraint_attributes(src, {"velocity_max": "3.0m", "safety_factor_head": "1.2"})
    em = _analyze(out)
    assert em.constraints.velocity_max == 3.0
    assert em.constraints.safety_factor_head == 1.2


def test_set_constraint_creates_block():
    out = set_constraint_attributes(_SRC, {"velocity_max": "1.8m"})
    assert "constraint {" in out
    assert _analyze(out).constraints.velocity_max == 1.8


def test_has_link_toggle():
    assert has_link(_SRC, "src", "t1") is True       # 기존 connect
    assert has_link(_SRC, "src", "ghost") is False
    out = add_link(_SRC, "src", "t2")
    assert has_link(out, "src", "t2") is True
