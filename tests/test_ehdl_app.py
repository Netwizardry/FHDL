"""T-EAPP: EHDL 편집(Inverse Sync)·명령·계통 구성도·보고서·GUI."""
import json
import os
import sys
sys.path.insert(0, "src")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ehdl.command import execute_command
from ehdl.drawing import build_sld
from ehdl.dsl_editor import add_block, add_cable, block_type, remove_block, set_attrs
from ehdl.pipeline import analyze
from ehdl.report import export_report, tables

DEMO = os.path.join(os.path.dirname(__file__), "..", "projects", "ehdl_demo", "main.ehd")


@pytest.fixture(scope="module")
def demo():
    with open(DEMO, encoding="utf-8") as f:
        src = f.read()
    r = analyze(src)
    assert r.status == "OK"
    return src, r


SRC = """source S { voltage = 380V; phases = 3; }
panel P {
    feed = S;
    rated_current = 100A;   // 정격
}
load L { parent = P; kind = heater; rating = 3kW; pf = 1.0; phases = 3; }
cable C1 { from = P; to = L; length = 10m; }
"""


def test_set_attrs_preserves_comments_and_spacing():
    a = set_attrs(SRC, "P", {"rated_current": "150A", "justification": "증설 예정 20kW"})
    assert "    rated_current = 150A;   // 정격\n" in a
    assert '    justification = "증설 예정 20kW";\n' in a
    b = set_attrs(a, "L", {"pf": "0.9"})
    assert "load L { parent = P; kind = heater; rating = 3kW; pf = 0.9; phases = 3; }" in b
    assert set_attrs(a, "P", {"justification": None}) == set_attrs(SRC, "P", {"rated_current": "150A"})


def test_remove_block_cascades():
    out = remove_block(SRC, "P")
    assert block_type(out, "P") is None and block_type(out, "C1") is None
    assert "parent = P" not in out and block_type(out, "L") == "load"


def test_add_block_and_cable_round_trip():
    s = add_cable(add_block(SRC, "load", "L2", {"parent": "P", "kind": "motor", "rating": "5kW", "basis": "input",
                                                   "pf": "0.8", "phases": "3"}), "C2", "P", "L2", {"length": "5m"})
    r = analyze(s)
    assert r.status == "OK" and "L2" in r.model.nodes and r.model.edges["C2"].to_id == "L2"


def test_commands():
    r = analyze(SRC)
    c = execute_command(SRC, "add load L9 parent=P kind=heater rating=1kW pf=1 phases=3", r)
    assert block_type(c.new_source, "L9") == "load"
    c = execute_command(SRC, "set P rated_current=125A", r)
    assert "rated_current = 125A;" in c.new_source
    c = execute_command(SRC, "link P L length=20m", r)
    assert "from = P;" in c.new_source.split("cable C_L_")[1]
    c = execute_command(SRC, "scenario peak on=L", r)
    assert block_type(c.new_source, "peak") == "scenario"
    w = execute_command(SRC, "why P", r)
    assert any("정격전류" in m for m in w.messages)
    assert execute_command(SRC, "report out.pdf", r).action == "report"
    assert execute_command(SRC, "dwg export x.svg", r).args == {"path": "x.svg"}
    assert execute_command(SRC, "bogus", r).level == "ERROR"


def test_sld_references_every_entity_and_collapse(demo):
    _, r = demo
    sh = build_sld(r, "demo")
    assert set(r.model.nodes) | set(r.model.edges) <= sh.refs()
    assert sh.by_layer("ST_FAIL")                       # LT1 전압강하 FAIL 표식
    folded = build_sld(r, "demo", collapsed={"PNL_A"})
    refs = folded.refs()
    assert "PNL_A" in refs and "P1" not in refs and "C_P1" not in refs
    assert any(getattr(i, "text", "").startswith("[접힘: 하위") for i in folded.items)


def test_report_tables_and_exports(demo, tmp_path):
    _, r = demo
    t = tables(r)
    assert {r[0] for r in t["BOTTLENECK"]["rows"]} == {"LT1", "RC2", "B_W", "C_LT1"}
    assert any("향후 증설" in row[2] for row in t["F"]["rows"])
    assert any(row[0] == "MDB" and "2공장" in row[5] for row in t["E"]["rows"])
    j = export_report(r, str(tmp_path / "r.json"))
    data = json.load(open(j, encoding="utf-8"))
    assert data["summary"]["counts"]["FAIL"] == 5 and data["checks"][0]["evidence"]["formula"]
    export_report(r, str(tmp_path / "r.csv"))
    assert (tmp_path / "r_C.csv").exists() and (tmp_path / "r_F.csv").exists()
    assert (tmp_path / "r_EARTH.csv").exists() and (tmp_path / "r_SUPPLY.csv").exists()
    pdf = export_report(r, str(tmp_path / "r.pdf"), "demo")
    assert open(pdf, "rb").read(4) == b"%PDF"
    with pytest.raises(ValueError):
        export_report(r, str(tmp_path / "r.doc"))


def test_demo_findings(demo):
    _, r = demo
    st = {c.id: c.status for c in r.checks}
    assert st["LT1:voltage_drop"] == "FAIL"
    assert st["C_P1:cable_ampacity"] in ("PASS", "UNKNOWN")       # 지식 DB 있으면 표 B.52.5 로 PASS
    assert st["MDB:sizing_rationale"] == "PASS"                    # 선정 근거 입력됨
    assert st["PNL_B:unbalance"] == "UNKNOWN"                      # RC2 접속 상 미지정
    assert any(d.code == "ESCN001" for d in r.diagnostics)         # 교대 운전 3대 > 제약 2대
    assert st["RC2:rcd_socket"] == "FAIL"                          # Phase 2: 콘센트 누전차단기 없음
    assert st["P1:motor_start_protection"] == "PASS"               # δ 입력된 펌프
    assert st["CB_FA:breaking_capacity"] in ("PASS", "REVIEW")     # 17 kA < 35 kA (KT 미확인 → REVIEW)
    assert st["LT1:fault_protection"] == "FAIL"                    # Phase 3: Zs 가 0.4 s 차단 허용치 초과
    assert st["B_W:bonding"] == "FAIL"                             # 주 보호등전위본딩 10 < 25 ㎟
    assert st["RC1:fault_protection"] == "REVIEW"                  # 30 mA 누전차단기


def test_ehdl_main_window_flow(demo, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ehdl.gui.main_window import EHDLMainWindow
    w = EHDLMainWindow()
    assert w.result.status == "OK"                                 # 새 계통 예제
    w.open_file(DEMO)
    assert w.result.status == "OK" and w.editor._file_label.text() == "main.ehd"
    w._select("LT1")
    html = w.detail.toHtml()
    for sec in ("1. 이 설비는", "3. 계산된 요구조건", "5. 적합성 판정", "7. 설계자에게 확인할 질문"):
        assert sec in html
    w._command("set PNL_B rated_current=125A")
    assert "rated_current = 125A" in w.editor.get_source() and w._dirty
    w.graph.toggle_collapse("PNL_A")
    assert "P1" not in w.graph._items
    assert w.export_report(str(tmp_path / "g.pdf")).endswith("g.pdf")
    assert w.graph.export(str(tmp_path / "g.svg")).endswith("g.svg")
    w.results.mode.setCurrentIndex(1)                              # 기본설계 모드
    assert w.results.t_checks.columnCount() == 5
    w._dirty = False
    w.close()
