"""T-DWG: 도면 생성(ISO·평면·정면·P&ID)과 내보내기(SVG·PDF·DXF·PNG·STEP 스크립트)."""
import math
import os
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0, "src")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fhdl.core.pipeline import AnalysisPipeline
from fhdl.drawing import VIEWS, build_drawing, export_drawing
from fhdl.drawing.export_step import MAX_HR, export_step, step_commands
from fhdl.drawing.export_svg import sheet_to_svg
from fhdl.drawing.projection import project_dir, symbol_frame
from fhdl.drawing.sheet import Circle, Polyline, Text

DEMO = os.path.join(os.path.dirname(__file__), "..", "projects", "demo_project", "main.fhd")


@pytest.fixture(scope="module")
def demo():
    with open(DEMO, encoding="utf-8") as f:
        r = AnalysisPipeline().run(f.read())
    assert r.status == "OK"
    return r


def _texts(sheet):
    return [i.text for i in sheet.items if isinstance(i, Text)]


# --- projection ----------------------------------------------------------------

def test_iso_axes_follow_piping_iso_convention():
    """북 = 오른쪽 위 30°, 동 = 오른쪽 아래 30°, 상 = 수직 (세 축 투영 길이 1)."""
    n, e, u = (project_dir("iso", d) for d in ((0, 1, 0), (1, 0, 0), (0, 0, 1)))
    assert math.isclose(math.degrees(math.atan2(n[1], n[0])), 30.0, abs_tol=1e-9)
    assert math.isclose(math.degrees(math.atan2(e[1], e[0])), -30.0, abs_tol=1e-9)
    assert u == (0.0, 1.0)
    assert all(math.isclose(math.hypot(*v), 1.0) for v in (n, e, u))


def test_symbol_plane_for_horizontal_pipe_is_vertical():
    a, b = symbol_frame("iso", (1.0, 0.0, 0.0))
    assert math.isclose(b[0], 0.0, abs_tol=1e-9) and math.isclose(abs(b[1]), 1.0)
    # 평면도의 수직관(시선 방향)은 화면 축으로 대체
    assert symbol_frame("plan", (0.0, 0.0, 1.0)) == ((1.0, 0.0), (0.0, 1.0))


# --- piping sheets ---------------------------------------------------------------

@pytest.mark.parametrize("view", ["iso", "plan", "elevation"])
def test_piping_sheet_references_every_entity(demo, view):
    sh = build_drawing(demo, view, "demo")
    em = demo.entity_map
    assert set(em.pipes) | set(em.all_node_ids()) <= sh.refs()
    x0, y0, x1, y1 = sh.bbox()
    assert x0 >= 0 and y0 >= 0 and x1 <= sh.width and y1 <= sh.height


def test_iso_sheet_content(demo):
    sh = build_drawing(demo, "iso", "demo")
    texts = _texts(sh)
    # 흐름 화살표 = 배관마다 1개 (채운 삼각형, FLOW 레이어)
    arrows = [i for i in sh.by_layer("FLOW") if isinstance(i, Polyline) and i.fill]
    assert len(arrows) == len(demo.entity_map.pipes)
    # 구간 치수(mm): main_pipe 경유점 경로 40000 / 3000 / 5000
    assert {"40000", "5000"} <= set(texts)
    # 밸브 기호(VALVE 레이어) — 데모: 게이트 2·체크·볼·글로브
    assert len(sh.by_layer("VALVE")) >= 5
    # 계기 태그
    assert "PI" in texts and "FE" in texts
    # 엘보·티 용접점
    assert sum(1 for i in sh.by_layer("FITTING") if isinstance(i, Circle) and i.fill) >= 14
    # 회사 양식(도면 양식 DXF 추출): BOM 행 + 절단 길이 행 + 표제란 칸
    assert {"BILL OF MATERIAL", "LINE NO.", "COMMODITY", "JOB NO.", "SHT.NO."} <= set(texts)
    assert any(t.startswith("PIPE CUT LENGTH (mm)") for t in texts)
    assert "main_pipe#2  3000 / 2905" in texts                 # 3000 − 2×47.6 (32A 롱 엘보)
    assert {"WATER", "demo", "1/1", "FHDL 자동 생성"} <= set(texts)
    assert "DS-생-017" not in texts and "J.con" not in texts     # 양식 샘플 값은 제외


def test_simple_form_option(demo):
    sh = build_drawing(demo, "iso", "demo", form="simple")
    texts = _texts(sh)
    assert "BILL OF MATERIAL" in texts and "PIPE CUT LENGTH (mm)" in texts
    assert "ISOMETRIC (ISO 6412-2)" in texts and "NTS" in texts


def test_bom_counts_elbows_tees_and_valves(demo):
    from fhdl.drawing.piping import _Ctx, bom_rows
    rows = {(r[1], r[2]): r[3] for r in bom_rows(_Ctx(demo, "iso"))}
    assert rows[("ELBOW 90° LR", "32A(1-1/4\")")] == "3 EA"   # suction 1 + main_pipe 2
    assert rows[("ELBOW 90° LR", "25A(1\")")] == "4 EA"       # branch_A 2 + branch_B 2
    assert rows[("TEE", "32A(1-1/4\")")] == "1 EA"
    assert rows[("게이트 밸브", "32A(1-1/4\")")] == "2 EA"
    assert rows[("PIPE Steel", "32A(1-1/4\")")] == "55.0 m"


def test_plan_shows_rise_drop_marks(demo):
    sh = build_drawing(demo, "plan")
    texts = _texts(sh)
    assert any(t.startswith("DN ") for t in texts)      # main_pipe 3 m 하강 등


def test_drawing_without_coordinates_uses_auto_layout():
    r = AnalysisPipeline().run("""
system main { unit_system = METRIC; fluid = water; temp = 20; }
tank t { z = 20m; }
junction j { z = 10m; }
terminal a { z = 0m; required_q = 50lpm; }
terminal b { z = 0m; required_q = 30lpm; }
pipe p1 { start = t; end = j; length = 30m; diameter = auto; fittings = [valve_gate]; }
pipe p2 { start = j; end = a; length = 20m; diameter = auto; }
pipe p3 { start = j; end = b; length = 20m; diameter = auto; }
""")
    for v in VIEWS:
        sh = build_drawing(r, v)
        assert {"p1", "p2", "p3", "t", "j", "a", "b"} <= sh.refs()
    iso = build_drawing(r, "iso")
    assert any("자동 배치" in n for n in iso.notes)
    assert any("균등 배치" in n for n in iso.notes)


def test_empty_result_gives_blank_sheet():
    sh = build_drawing(None, "iso")
    assert sh.items and not sh.refs()


# --- P&ID ------------------------------------------------------------------------

def test_pid_sheet(demo):
    sh = build_drawing(demo, "pid", "demo")
    texts = _texts(sh)
    assert "EQUIPMENT LIST" in texts and "LINE LIST" in texts
    assert any(t.startswith("main_pipe-32A") for t in texts)
    assert len(sh.by_layer("VALVE")) >= 5
    assert set(demo.entity_map.pipes) <= sh.refs()


# --- export ----------------------------------------------------------------------

def test_svg_is_well_formed_with_layers(demo):
    root = ET.fromstring(sheet_to_svg(build_drawing(demo, "iso")))
    ids = {g.get("id") for g in root.iter("{http://www.w3.org/2000/svg}g")}
    assert {"PIPE", "VALVE", "DIM", "TEXT", "BORDER", "FLOW"} <= ids


def test_export_all_formats(demo, tmp_path):
    import ezdxf
    pdf = export_drawing(demo, str(tmp_path / "d.pdf"), project="demo")
    with open(pdf, "rb") as f:
        data = f.read()
    assert data.startswith(b"%PDF")
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + data.count(b"/Type /Page/") >= 4 \
        or data.count(b"/Page") >= 4
    dxf = export_drawing(demo, str(tmp_path / "d.dxf"), views=["iso", "pid"])
    doc = ezdxf.readfile(dxf)
    layers = {l.dxf.name for l in doc.layers}
    assert {"PIPE", "VALVE", "FITTING", "DIM", "TEXT", "BORDER"} <= layers
    texts = {e.dxf.text for e in doc.modelspace().query("TEXT")}
    assert "main_pipe-32A(1-1/4\")-Steel" in texts
    assert len(doc.modelspace().query("HATCH")) > 0
    export_drawing(demo, str(tmp_path / "d.svg"), views=["iso", "plan"])
    assert (tmp_path / "d_iso.svg").exists() and (tmp_path / "d_plan.svg").exists()
    export_drawing(demo, str(tmp_path / "d.png"), views=["elevation"])
    assert (tmp_path / "d.png").stat().st_size > 1000
    with pytest.raises(ValueError):
        export_drawing(demo, str(tmp_path / "d.doc"))


def test_step_commands_segment_slender_pipes(demo):
    cmds = step_commands(demo)
    cyl = [c["params"] for c in cmds if c["command"] == "solid.cylinder"]
    assert all(p["height"] / p["radius"] <= MAX_HR + 1e-6 for p in cyl)
    # 구간 길이 합 = 경로 길이 (배관별)
    tot = {}
    for p in cyl:
        pid = p["body_name"].split("#")[0]
        tot[pid] = tot.get(pid, 0.0) + p["height"]
    for pid, L in tot.items():
        assert abs(L / 1000 - demo.entity_map.pipes[pid].length) < 0.01
    assert sum(1 for c in cmds if c["command"] == "solid.sphere") == len(demo.entity_map.all_node_ids())


def test_step_without_cli_writes_script_only(demo, tmp_path, monkeypatch):
    monkeypatch.delenv("SOLIDCRAFT_CLI", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    out = export_step(demo, str(tmp_path / "d.step"))
    assert out["step"] is None and os.path.exists(out["script"])


# --- GUI drawing panel -------------------------------------------------------------

def test_drawing_panel_select_and_drag(demo):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication
    from fhdl.gui.panels.drawing_panel import DrawingPanel
    QApplication.instance() or QApplication([])
    panel = DrawingPanel()
    panel.update_from_result(demo, "demo")
    events = []
    panel.entity_selected.connect(lambda r: events.append(("sel", r)))
    panel.node_double_clicked.connect(lambda r: events.append(("node", r)))
    panel.pipe_double_clicked.connect(lambda r: events.append(("pipe", r)))
    panel.node_moved.connect(lambda n, a: events.append(("move", n, a)))
    for v in VIEWS:
        panel.set_view(v)
        assert set(demo.entity_map.pipes) <= set(panel._items)
    panel.set_view("iso")
    assert not panel.can_drag("j1")                       # 아이소메트릭은 좌표 역변환 불가
    panel.select("main_pipe")
    panel.activate("main_pipe")
    panel.activate("j1")
    panel.set_view("plan")
    s = panel._sheet.fit[0]
    panel.finish_move("j1", QPointF(10 * s, -5 * s))      # 장면 y 아래쪽 → 북쪽 +5 m
    panel.set_view("elevation")
    panel.finish_move("j1", QPointF(0.0, -2 * s))         # 위로 2 m
    assert ("sel", "main_pipe") in events and ("pipe", "main_pipe") in events and ("node", "j1") in events
    moves = [e for e in events if e[0] == "move"]
    assert moves[0][2] == {"x": "60.0", "y": "5.0"}
    assert moves[1][2]["z"] == "7.00m"
