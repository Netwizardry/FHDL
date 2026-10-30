"""T-VAL: 입력 검증(SYN002·SEM012~015) · 중단 결과 폐기 · 수렴 기록 · 리포트 형식 · 진공 압력 한계 · 편집 되돌리기."""
import csv
import json
import sys
sys.path.insert(0, "src")

import pytest

from fhdl.core.pipeline import AnalysisPipeline

BASE = """system main { fluid = water; temp = 20; friction_model = DW; }
tank T { z = 10m; }
terminal E { z = 0m; required_q = 60lpm; required_p = 0.05MPa; }
pipe p1 { start = T; end = E; length = 30m; diameter = 50mm; material = Steel; %s }
connect T -> p1 -> E;
"""


def codes(src):
    r = AnalysisPipeline().run(src)
    return r, {d.code: d for d in r.diagnostics}


def test_valid_source_has_no_validation_diagnostics():
    r, c = codes(BASE % "")
    assert r.status == "OK" and not {k for k in c if k.startswith(("SEM01", "SYN"))}


def test_unknown_unit_is_error_not_silent_factor_1():
    r, c = codes(BASE.replace("60lpm", "60lpmm"))
    assert c["SEM012"].severity == "ERROR" and "lpmm" in c["SEM012"].message
    assert r.status != "OK"


def test_wrong_dimension_unit():
    _, c = codes(BASE.replace("0.05MPa", "0.05m3"))
    assert "체적 단위" in c["SEM012"].message


def test_legacy_velocity_in_m_is_read_as_m_per_s_with_warning():
    r, c = codes(BASE % "" + "constraint { velocity_max = 2.5m; }")
    assert c["SEM012"].severity == "WARNING" and r.entity_map.constraints.velocity_max == 2.5


def test_unknown_block_and_attribute():
    _, c = codes(BASE % "" + "nozzle N { z = 0m; }")
    assert c["SYN002"].severity == "ERROR" and "nozzle" in c["SYN002"].message
    _, c = codes(BASE % "colour = red;")
    assert c["SEM013"].severity == "WARNING"


def test_enum_and_range_checks():
    _, c = codes(BASE.replace("friction_model = DW", "friction_model = XX"))
    assert c["SEM014"].severity == "ERROR"
    _, c = codes(BASE.replace("fluid = water", "fluid = brine"))
    assert c["SEM014"].severity == "WARNING" and "물(water)" in c["SEM014"].message
    _, c = codes(BASE % "c_factor = 9999;")
    assert c["SEM014"].severity == "WARNING"


def test_percent_efficiency_is_ratio():
    src = BASE + "pump P { z = 0m; efficiency = 75%; }"
    r, c = codes(src)
    assert r.entity_map.pumps["P"].efficiency == pytest.approx(0.75) and "SEM014" not in c


def test_unknown_fitting_warns():
    _, c = codes(BASE % "fittings = [foo_valve, elbow_90];")
    assert "foo_valve" in c["SEM015"].message


def test_cancelled_run_is_discarded(tmp_path):
    r = AnalysisPipeline().run(BASE % "", output_dir=str(tmp_path), cancel_fn=lambda: True)
    assert r.status == "CANCELLED" and any(d.code == "CAL004" for d in r.diagnostics)
    assert not any(tmp_path.iterdir())                       # 리포트도 쓰지 않음


def test_convergence_is_recorded():
    r = AnalysisPipeline().run(BASE % "")
    assert r.summary.converged and r.summary.solve_iterations >= 1 and r.summary.residual < 1e-3


def test_reports_have_bom_length_and_sizing(tmp_path):
    r = AnalysisPipeline().run(BASE % "", output_dir=str(tmp_path))
    paths = r.summary.provenance_map["_output_paths"]
    raw = open(paths["pipes_csv"], "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf")                   # Excel 한글
    rows = list(csv.DictReader(open(paths["pipes_csv"], encoding="utf-8-sig")))
    assert rows[0]["Length(m)"] == "30.00" and rows[0]["Sizing_Mode"] == "MANUAL"
    js = json.load(open(paths["summary_json"], encoding="utf-8"))
    assert js["converged"] is True and js["solve_iterations"] >= 1


def test_vacuum_pressure_is_clamped():
    # 저수조보다 30 m 높은 말단 — 계산 압력이 진공 아래로 떨어진다
    src = BASE.replace("terminal E { z = 0m;", "terminal E { z = 60m;").replace("required_p = 0.05MPa;", "")
    r, c = codes(src)
    p = next(n for n in r.node_results if n.node_id == "E").p_gauge
    assert p >= -101325 and "WRN005" in c


def test_graph_edit_is_undoable():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fhdl.gui.panels.editor_panel import EditorPanel
    e = EditorPanel()
    e.set_source("tank A { z = 1m; }", reset_undo=True)
    e.set_source("tank A { z = 2m; }")
    e._editor.undo()
    assert e.get_source() == "tank A { z = 1m; }"


def test_unsaved_changes_tracked():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fhdl.gui.main_window import MainWindow
    w = MainWindow()
    assert not w.has_unsaved_changes()
    w._editor_panel.set_source(w._editor_panel.get_source() + "\n// edit")
    assert w.has_unsaved_changes()
    w._saved_source = w._editor_panel.get_source()
    assert w.confirm_discard()


def test_live_lint_marks_errors_without_running():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fhdl.gui.main_window import MainWindow
    w = MainWindow()
    w._lint(BASE.replace("60lpm", "60lpmm"))
    assert any(d.code == "SEM012" for d in w._lint_diags)
    assert w._editor_panel._editor._error_lines                 # 에디터 오류 줄 표시
    w._lint(BASE % "")
    assert not any(d.is_blocking for d in w._lint_diags)


def test_auto_indent():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fhdl.gui.panels.editor_panel import FHDLEditor
    ed = FHDLEditor()
    ed.setPlainText("tank T {")
    c = ed.textCursor()
    c.movePosition(c.MoveOperation.End)
    ed.setTextCursor(c)
    ed.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r"))
    assert ed.toPlainText() == "tank T {\n    "
    ed.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_BraceRight, Qt.KeyboardModifier.NoModifier, "}"))
    assert ed.toPlainText() == "tank T {\n}"


def test_defaults_applied_are_recorded(tmp_path):
    r = AnalysisPipeline().run(BASE.replace(" material = Steel;", "") % "", output_dir=str(tmp_path))
    d = r.entity_map.defaults_applied
    assert d[("배관 재질", "Steel")] == ["p1"] and ("최대 유속", "3.0 m/s") in d
    assert any(x.code == "DEF001" and x.severity == "INFO" and "Steel" in x.message for x in r.diagnostics)
    assert "배관 재질: Steel" in r.summary.provenance_map["p1"]["assumptions"]
    js = json.load(open(r.summary.provenance_map["_output_paths"]["summary_json"], encoding="utf-8"))
    assert any(x["item"] == "배관 재질" for x in js["defaults_applied"])


def test_calc_report_html_and_pdf(tmp_path):
    from fhdl.core.calc_report import export_calc_report
    src = BASE % ""
    r = AnalysisPipeline().run(src, output_dir=str(tmp_path))
    h = export_calc_report(r, str(tmp_path / "r.html"), src, "demo")
    text = open(h, encoding="utf-8").read()
    import hashlib
    assert hashlib.sha256(src.encode()).hexdigest() in text and "p1" in text and "DW" in text
    pytest.importorskip("PySide6")
    pdf = export_calc_report(r, str(tmp_path / "r.pdf"), src, "demo")
    assert open(pdf, "rb").read(4) == b"%PDF"
    js = json.load(open(r.summary.provenance_map["_output_paths"]["summary_json"], encoding="utf-8"))
    assert js["header"]["source_sha256"] == hashlib.sha256(src.encode()).hexdigest()
    from fhdl.core.command import execute_command
    assert execute_command(src, "report out.pdf").action == "report"
