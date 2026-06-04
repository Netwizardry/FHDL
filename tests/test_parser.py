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


# ---------------------------------------------------------------------------
# 좌표 (x, y, z) — 명세 정본 키 'z' 와 하위호환 별칭 'elevation'
# ---------------------------------------------------------------------------

from fhdl.core.semantic import SemanticAnalyzer
from fhdl.core.parser import serialize_entity_map_to_fhd

_HDR = "system m { unit_system = METRIC; fluid = water; temp = 20; }\n"


def _analyze(body: str):
    ast, _ = FHDLParser().parse(_HDR + body)
    return SemanticAnalyzer().analyze(ast)[0]


def test_coord_z_is_elevation():
    """명세 키 'z' 가 고도로 인식되어야 한다."""
    em = _analyze("junction n1 { z = 10m; x = 5; y = 7; }")
    j = em.junctions["n1"]
    assert j.elevation == 10.0
    assert j.x == 5.0 and j.y == 7.0


def test_coord_elevation_alias():
    """하위호환: 'elevation' 도 동일하게 고도로 인식되어야 한다."""
    ez = _analyze("junction n1 { elevation = 10m; }").junctions["n1"]
    zz = _analyze("junction n1 { z = 10m; }").junctions["n1"]
    assert ez.elevation == zz.elevation == 10.0


def test_coord_roundtrip_preserves_xyz():
    """직렬화 → 재파싱 시 x, y, z 가 보존되어야 한다."""
    em = _analyze("terminal t1 { z = 8m; x = 12; y = -3; required_q = 60lpm; }")
    fhd = serialize_entity_map_to_fhd(em)
    ast, _ = FHDLParser().parse(fhd)
    t = SemanticAnalyzer().analyze(ast)[0].terminals["t1"]
    assert t.elevation == 8.0
    assert t.x == 12.0 and t.y == -3.0
