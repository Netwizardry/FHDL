"""T-CMD: 하단 콘솔 명령 인터프리터 (TUI)."""
import sys
sys.path.insert(0, "src")

from fhdl.core.command import execute_command
from fhdl.core.pipeline import AnalysisPipeline

_SRC = """system m { unit_system=METRIC; fluid=water; temp=20; }
tank src { z=10m; }
terminal t { z=0m; required_q=60lpm; }
pipe p1 { start=src; end=t; length=30m; diameter=50mm; material=Steel; }
connect src -> t;
"""


def _em(src):
    return AnalysisPipeline().run(src).entity_map


def test_help_and_unknown():
    assert execute_command(_SRC, "help").messages
    r = execute_command(_SRC, "bogus")
    assert r.level == "ERROR" and r.new_source is None


def test_actions():
    assert execute_command(_SRC, "run").action == "run"
    assert execute_command(_SRC, "save").action == "save"
    assert execute_command(_SRC, "clear").action == "clear"


def test_add_node():
    r = execute_command(_SRC, "add junction j1 z=5m x=10 y=2")
    assert "junction j1 {" in r.new_source
    em = _em(r.new_source)
    assert "j1" in em.junctions and em.junctions["j1"].elevation == 5.0


def test_set_node():
    r = execute_command(_SRC, "set t required_q=120lpm", _em(_SRC))
    em = _em(r.new_source)
    assert abs(em.terminals["t"].required_q * 60000 - 120) < 1e-6


def test_set_pipe_routes_to_pipe():
    em = _em(_SRC)
    r = execute_command(_SRC, "set p1 length=45m material=PVC", em)
    em2 = _em(r.new_source)
    assert em2.pipes["p1"].length == 45.0
    assert em2.pipes["p1"].material == "PVC"


def test_del_node_cascades():
    src = _SRC.replace("tank src { z=10m; }",
                       "tank src { z=10m; }\njunction j { z=5m; }")
    src = src.replace("connect src -> t;",
                      "pipe pj { start=src; end=j; length=5m; diameter=50mm; material=Steel; }\nconnect src -> j;\nconnect src -> t;")
    em = _em(src)
    r = execute_command(src, "del j", em)
    em2 = _em(r.new_source)
    assert "j" not in em2.junctions
    assert "pj" not in em2.pipes


def test_link_unlink():
    src = _SRC + "\njunction j { z=5m; }\n"
    r = execute_command(src, "link j t length=8m")
    assert "connect j -> t;" in r.new_source
    from fhdl.core.dsl_editor import default_pipe_id
    assert default_pipe_id("j", "t") in r.new_source
    r2 = execute_command(r.new_source, "unlink j t")
    assert default_pipe_id("j", "t") not in r2.new_source


def test_constraint():
    r = execute_command(_SRC, "constraint velocity_max=1.8m")
    assert _em(r.new_source).constraints.velocity_max == 1.8


def test_ls():
    r = execute_command(_SRC, "ls", _em(_SRC))
    text = " ".join(r.messages)
    assert "src" in text and "p1" in text
