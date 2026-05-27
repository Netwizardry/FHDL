"""T-SYN: 파서 단위 테스트."""
import sys
sys.path.insert(0, "src")

from fhdl.core.parser import FHDLParser


SIMPLE_FHD = """
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    friction_model = DW;
}

tank source {
    elevation = 5m;
}

terminal t1 {
    elevation = 0m;
    required_q = 100lpm;
    required_p = 0.1MPa;
}

pipe p1 {
    start = source;
    end = t1;
    length = 50m;
    diameter = auto;
    material = Steel;
}

connect source -> p1 -> t1;
"""


def test_parse_returns_ast():
    parser = FHDLParser()
    ast, diags = parser.parse(SIMPLE_FHD)
    assert len(ast) > 0
    assert not any(d.severity in ("ERROR", "FATAL") for d in diags)


def test_parse_system_node():
    from fhdl.core.models import SystemASTNode
    parser = FHDLParser()
    ast, _ = parser.parse(SIMPLE_FHD)
    systems = [n for n in ast if isinstance(n, SystemASTNode)]
    assert len(systems) == 1
    assert systems[0].name == "main"


def test_parse_components():
    from fhdl.core.models import ComponentASTNode
    parser = FHDLParser()
    ast, _ = parser.parse(SIMPLE_FHD)
    comps = [n for n in ast if isinstance(n, ComponentASTNode)]
    comp_types = {c.comp_type for c in comps}
    assert "tank" in comp_types
    assert "terminal" in comp_types
    assert "pipe" in comp_types


def test_parse_connect():
    from fhdl.core.models import ConnectASTNode
    parser = FHDLParser()
    ast, _ = parser.parse(SIMPLE_FHD)
    connects = [n for n in ast if isinstance(n, ConnectASTNode)]
    assert len(connects) >= 1
    assert "source" in connects[0].chain


def test_parse_comment_removal():
    code = """
    // 행 주석
    /* 블록
       주석 */
    system main { fluid = water; temp = 20; unit_system = METRIC; }
    """
    parser = FHDLParser()
    ast, diags = parser.parse(code)
    assert not any(d.severity == "ERROR" for d in diags)


def test_duplicate_connect_chain():
    code = """
    system s { fluid = water; temp = 20; unit_system = METRIC; }
    connect A;
    """
    parser = FHDLParser()
    ast, diags = parser.parse(code)
    # 단일 ID connect는 에러
    # (1개 체인은 에러지만 파서가 계속 파싱)
    error_codes = [d.code for d in diags]
    assert "SYN001" in error_codes
