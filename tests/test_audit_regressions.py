"""T-AUD: 전수 검사(2026-10-30)에서 찾아 고친 결함의 회귀 시험 — FHDL·EHDL."""
import math
import sys
sys.path.insert(0, "src")

import pytest

from fhdl.core.pipeline import AnalysisPipeline

FH = """system m { temp = 20; }
tank T { z = %s; }
terminal E { z = 0m; required_q = 60lpm; }
pipe p1 { start = T; end = E; length = 10m; diameter = %s; }
"""


# ---------------------------------------------------------------- FHDL 예외 → 진단
@pytest.mark.parametrize("z,d", [("1.2.3m", "50mm"), (".", "50mm"), ("10m", "0mm"), ("10m", "-50mm")])
def test_fhdl_bad_numbers_give_diagnostics_not_exceptions(z, d):
    r = AnalysisPipeline().run(FH % (z, d))
    assert r.status == "FAILED" and any(x.code in ("SEM012", "SEM014") for x in r.diagnostics)


def test_fhdl_self_loop_and_extremes_do_not_raise():
    r = AnalysisPipeline().run(FH % ("10m", "50mm") + "pipe p2 { start = T; end = T; length = 1m; diameter = 50mm; }")
    assert any(x.code == "SEM003" for x in r.diagnostics)
    for extra in ("system m { altitude = 50000m; temp = -233.426; }",):
        r = AnalysisPipeline().run(extra + "\n" + (FH % ("10m", "50mm")).split("\n", 1)[1])
        assert r.status in ("OK", "PARTIAL", "FAILED")


def test_fhdl_parser_last_attr_without_semicolon_and_braced_fittings():
    from fhdl.core.parser import FHDLParser
    ast, d = FHDLParser().parse("tank t { z = 5m; level_max = 3m }\npipe p { fittings = {elbow_90*2}; material = PVC; }")
    t = next(a for a in ast if getattr(a, "comp_id", "") == "t")
    p = next(a for a in ast if getattr(a, "comp_id", "") == "p")
    assert t.attributes["level_max"] == (3.0, "m") and p.attributes["material"] == "PVC"
    _, d = FHDLParser().parse("tank t { z = 1m;\nterminal e { z = 0m; }")
    assert any(x.code == "SYN003" for x in d)


# ---------------------------------------------------------------- FHDL 수리 로직
def test_flow_accumulates_over_unequal_branch_depths():
    src = """system m { temp=20; }
tank T { z=30m; }
junction J0 { z=0m; } junction J { z=0m; } junction B { z=0m; }
terminal A { z=0m; required_q=100lpm; } terminal C { z=0m; required_q=200lpm; }
pipe p0 { start=T; end=J0; length=10m; diameter=50mm; }
pipe p1 { start=J0; end=J; length=10m; diameter=50mm; }
pipe p2 { start=J; end=A; length=10m; diameter=50mm; }
pipe p3 { start=J; end=B; length=10m; diameter=50mm; }
pipe p4 { start=B; end=C; length=10m; diameter=50mm; }
"""
    q = {p.pipe_id: p.flow * 60000 for p in AnalysisPipeline().run(src).pipe_results}
    assert q["p0"] == pytest.approx(300) and q["p1"] == pytest.approx(300)


def test_parallel_pipes_equalize_head_loss():
    src = """system m { temp=20; }
tank a { z=50m; }
terminal e { z=0m; required_q=600lpm; }
pipe p1 { start=a; end=e; length=100m; diameter=100mm; }
pipe p2 { start=a; end=e; length=100m; diameter=25mm; }
"""
    pr = {p.pipe_id: p for p in AnalysisPipeline().run(src).pipe_results}
    assert pr["p1"].h_loss_total == pytest.approx(pr["p2"].h_loss_total, rel=1e-3)
    assert pr["p1"].flow + pr["p2"].flow == pytest.approx(600 / 60000)


def test_required_head_uses_path_source_and_pump_suction_through_junction():
    below = """system m { temp=20; }
tank T { z=-10m; level_max=0m; }
pump P { z=-10m; }
terminal E { z=0m; required_q=60lpm; required_p=0.1MPa; }
pipe p1 { start=T; end=P; length=1m; diameter=100mm; }
pipe p2 { start=P; end=E; length=1m; diameter=100mm; }
"""
    assert AnalysisPipeline().run(below).summary.required_head == pytest.approx(20.2, abs=0.1)
    via = """system m { temp=20; }
tank T { z=10m; level_max=0m; }
junction J { z=5m; }
pump P { z=0m; head=20m; }
terminal E { z=0m; required_q=60lpm; }
pipe p0 { start=T; end=J; length=1m; diameter=100mm; }
pipe p1 { start=J; end=P; length=1m; diameter=100mm; }
pipe p2 { start=P; end=E; length=1m; diameter=100mm; }
"""
    p = next(n for n in AnalysisPipeline().run(via).node_results if n.node_id == "P")
    assert p.head_total == pytest.approx(30.0, abs=0.05)


def test_water_properties_and_ks_sizes():
    from fhdl.core.models import FluidConfig
    from fhdl.core.pipe_sizes import KS_PIPE_SIZES
    assert FluidConfig(temp=100).density == pytest.approx(958.4, abs=0.5)
    assert FluidConfig(temp=20).dynamic_viscosity == pytest.approx(1.002e-3, rel=0.01)
    ids = {s.nominal_a: s.inner_d_m for s in KS_PIPE_SIZES}
    assert ids[150] == pytest.approx(0.1552) and ids[500] == pytest.approx(0.4922)


def test_serializer_flow_and_cal005_units():
    from fhdl.core.parser import serialize_entity_map_to_fhd
    em = AnalysisPipeline().run(FH % ("10m", "50mm")).entity_map
    assert "required_q = 1Ls;" in serialize_entity_map_to_fhd(em)            # 60 L/min = 1 L/s
    from fhdl.core.parser import serialize_entity_map_to_fhd as ser
    demo = open("projects/demo_project/main.fhd", encoding="utf-8").read()
    r1 = AnalysisPipeline().run(demo)
    r2 = AnalysisPipeline().run(ser(r1.entity_map))
    assert [(p.pipe_id, round(p.flow, 9), round(p.h_loss_total, 6)) for p in r1.pipe_results] == \
        [(p.pipe_id, round(p.flow, 9), round(p.h_loss_total, 6)) for p in r2.pipe_results]   # 왕복 보존


def test_dsl_editor_backslash_value_is_literal():
    from fhdl.core.dsl_editor import set_node_attributes
    out = set_node_attributes("terminal e {\n    z = 0m;\n}\n", "e", {"preset_id": r"C:\q\1"})
    assert r"preset_id = C:\q\1;" in out


def test_project_db_keeps_only_latest_diagnostics(tmp_path):
    from fhdl.core.project_io import load_project, save_project
    src = FH % ("10m", "50mm")
    r = AnalysisPipeline().run(src)
    save_project(str(tmp_path), src, r)
    save_project(str(tmp_path), src, r)
    loaded = load_project(str(tmp_path))
    assert loaded.cache_valid and len(loaded.result.diagnostics) == len(r.diagnostics)
    assert loaded.result.summary.converged
    # 해석 뒤 편집하고 저장 → 결과는 옛 소스 체크섬 → 캐시 무효
    save_project(str(tmp_path), src + "\n// edit", r, result_source=src)
    assert not load_project(str(tmp_path)).cache_valid


def test_corrupt_state_db_does_not_block_save(tmp_path):
    from fhdl.core.project_io import load_project, save_project
    (tmp_path / "state.db").write_bytes(b"not a database")
    src = FH % ("10m", "50mm")
    save_project(str(tmp_path), src, AnalysisPipeline().run(src))
    assert (tmp_path / "main.fhd").read_text(encoding="utf-8") == src
    assert load_project(str(tmp_path)).cache_valid


def test_library_upsert_keeps_od_and_fitting_priority(tmp_path):
    from fhdl.db.library_db import LibraryDB
    db = LibraryDB(str(tmp_path / "l.db"))
    db.upsert_pipe_size("KS", "50A", 0.0529)
    row = db._conn.execute("SELECT outer_diameter FROM pipe_sizes WHERE standard='KS' AND nominal_size='50A'").fetchone()
    assert row[0] == pytest.approx(0.0605)
    db.upsert_fitting("elbow_90", 0.3, "50A")
    assert db.get_fitting_k("elbow_90", "50A") == 0.3
    db.upsert_fitting("ELBOW90", 5.0)                                        # 별칭도 정본 키로
    assert db.get_fitting_k("elbow_90") == 5.0
    db.close()


def test_fhdl_command_rejects_duplicates_and_noops():
    from fhdl.core.command import execute_command
    src = FH % ("10m", "50mm")
    assert execute_command(src, "add junction p1").level == "ERROR"
    assert execute_command(src, "unlink T E").level in ("WARNING", "ERROR")
    assert execute_command(src, "unlink E T").level == "ERROR"
    assert execute_command(src, "set E z=5m;}").level == "ERROR"


# ---------------------------------------------------------------- EHDL
from ehdl.pipeline import analyze  # noqa: E402

EH = """system s { frequency = 60Hz; }
source S { voltage = 380V; phases = 3; %s }
breaker CB { feed = S; rated_current = 32A; curve = C; }
cable C { from = CB; to = L; length = 50m; material = Cu; size = 6mm2; ampacity = 40A; }
load L { kind = general; rating = %s; pf = 1; phases = %s; %s }
"""


def test_ehdl_default_units():
    r = analyze(EH % ("limit_kw = 10kW;", "37", 3, ""))
    assert r.model.nodes["L"].params["rating"] == 37000
    r = analyze(EH % ("sc_mva = 50;", "10kW", 3, ""))
    assert r.model.nodes["S"].params["sc_mva"] == 50e6


@pytest.mark.parametrize("bad", ["size = 0mm2", "size = -6mm2", "length = -5m"])
def test_ehdl_nonpositive_quantities_rejected(bad):
    r = analyze((EH % ("", "10kW", 3, "")).replace("size = 6mm2", "size = 6mm2").replace(
        "length = 50m; material = Cu; size = 6mm2", bad.join(["", ""]) if False else
        {"size = 0mm2": "length = 50m; material = Cu; size = 0mm2", "size = -6mm2": "length = 50m; material = Cu; size = -6mm2",
         "length = -5m": "length = -5m; material = Cu; size = 6mm2"}[bad]))
    assert r.status == "FAILED" and any(d.code == "ESEM003" for d in r.diagnostics)


def test_ehdl_analyze_never_raises_on_cable_to_earth():
    r = analyze(EH % ("", "10kW", 3, "") + "earth E1 { kind = electrode; }\ncable X { from = CB; to = E1; length = 1m; }")
    assert r.status == "FAILED" and any(d.code == "ESEM002" for d in r.diagnostics)


@pytest.mark.parametrize("phase,amps", [("", 10000 / 220), ("phase = L1;", 10000 / 220), ("phase = L1L2;", 10000 / 380)])
def test_ehdl_single_phase_currents(phase, amps):
    r = analyze(EH % ("", "10kVA", 1, phase))
    assert r.scenarios["normal"].nodes["CB"].current == pytest.approx(amps, rel=0.02)


def test_ehdl_hv_cable_referred_to_lv():
    src = """system s { frequency=60Hz; }
source S { voltage=22.9kV; phases=3; sc_mva=500MVA; rx=0.1; }
breaker VCB { feed=S; rated_current=200A; standard=IEC60947-2; instantaneous=10; }
cable HV { from=VCB; to=TR; length=%sm; material=Cu; size=60mm2; insulation=XLPE; }
transformer TR { primary=22.9kV; secondary=380V; rated=1000kVA; uk=6%%; ur=1%%; }
switchboard M { feed=TR; rated_current=2000A; }
load H { parent=M; kind=heater; rating=100kW; pf=1; phases=3; }
"""
    a, b = (analyze(src % L).sc["TR"].ik_max for L in (1, 200))
    assert b == pytest.approx(a, rel=0.01)


def test_ehdl_max_demand_covers_each_branch():
    src = """system s { frequency=60Hz; }
source S { voltage=380V; phases=3; }
switchboard M { feed=S; rated_current=400A; }
breaker BA { parent=M; rated_current=100A; }
panel A { feed=BA; }
load PA { parent=A; kind=motor; rating=40kW; basis=input; pf=0.85; phases=3; group=G; }
breaker BB { parent=M; rated_current=40A; }
panel B { feed=BB; }
load PB { parent=B; kind=motor; rating=30kW; basis=input; pf=0.85; phases=3; group=G; }
group G { max_on = 1; }
"""
    c = next(c for c in analyze(src).checks if c.id == "BB:breaker_load")
    assert c.status == "FAIL" and c.actual == pytest.approx(53.6, abs=0.2)


def test_ehdl_parser_strings_and_editor_comments():
    from ehdl.dsl_editor import remove_block, set_attrs
    from ehdl.parser import parse
    blocks, _ = parse('load M1 { name = "http://x/*y"; rating = 1kW; } load M2 { rating = 2kW; }')
    assert [b.id for b in blocks] == ["M1", "M2"] and blocks[0].attrs["name"] == "http://x/*y"
    blocks, _ = parse('load M1 { name = "펌프\\t1 \\"A\\" \\x"; }')
    assert blocks[0].attrs["name"] == '펌프\t1 "A" \\x'
    s = '// load M1 {rating=1kW;}\nload M1 { rating=2kW; // pf = 0.5;\n pf=0.9; }\n'
    out = set_attrs(s, "M1", {"rating": "5kW", "pf": "0.8"})
    assert out.startswith("// load M1 {rating=1kW;}") and "// pf = 0.5;" in out and "pf = 0.8;" in out
    s2 = "panel P { parent = MDB; }\nload L2 { parent = P; }\nscenario s1 { on = [P, L2]; }\n"
    out = remove_block(s2, "P")
    assert "parent = MDB" in out and "on = [L2]" in out


def test_ehdl_history_tolerates_corruption(tmp_path):
    from ehdl.history import for_target, load, table
    (tmp_path / "m.history.jsonl").write_text('[1]\n"x"\n{"edits":[{"id":"P"}]}\n{"time":"t","edits":[{"id":"P"},5]}\n',
                                              encoding="utf-8")
    h = load(str(tmp_path / "m.ehd"))
    assert len(h) == 1 and table(h)["rows"] and for_target(h, "P")


def test_ehdl_report_to_missing_folder_raises():
    pytest.importorskip("PySide6")
    from ehdl.report import export_report
    r = analyze(EH % ("", "10kW", 3, ""))
    with pytest.raises(OSError):
        export_report(r, "/nonexistent_dir_xyz/r.pdf")


def test_ehdl_command_quoted_values():
    from ehdl.command import execute_command
    res = execute_command("load M1 { rating = 1kW; }\n", 'set M1 name="펌프 1"')
    assert 'name = "펌프 1";' in res.new_source


# ---------------------------------------------------------------- 남은 항목 (2차)
def test_npsha_uses_minimum_level():
    src = """system m { temp=20; }
tank T { z=0m; level_max=3m; level_min=%s; }
pump P { z=0m; head=20m; }
terminal E { z=0m; required_q=60lpm; }
pipe p1 { start=T; end=P; length=1m; diameter=100mm; }
pipe p2 { start=P; end=E; length=1m; diameter=100mm; }
"""
    n = lambda lv: next(x for x in AnalysisPipeline().run(src % lv).node_results if x.node_id == "P").npsha  # noqa: E731
    assert n("2m") - n("0m") == pytest.approx(2.0, abs=0.01)
    r = AnalysisPipeline().run(src % "5m")
    assert any(d.code == "SEM014" for d in r.diagnostics)                    # 최저 > 최고


def test_short_spool_cut_is_clamped_and_flagged():
    from fhdl.core.geometry import spool_cut_lengths
    sp = spool_cut_lengths([(0, 0, 0), (0.05, 0, 0), (0.05, 1, 0), (1, 1, 0)], 0.155)
    assert all(s.cut_m >= 0 for s in sp) and any(s.short for s in sp)


def test_imperial_display_units():
    from fhdl.core.units import display_units
    u = display_units("IMPERIAL")
    assert u["volume"][1] == "gal" and u["atm"][1] == "psi"


def test_ehdl_unbalance_line_pairs():
    src = """system s { frequency=60Hz; }
source S { voltage=380V; phases=3; }
panel P { feed=S; rated_current=200A; }
load A { parent=P; kind=heater; rating=10kW; pf=1; phases=1; phase=L1L2; }
load B { parent=P; kind=heater; rating=20kW; pf=1; phases=3; }
"""
    c = next(c for c in analyze(src).checks if c.id == "P:unbalance")
    assert c.actual == pytest.approx(100.0)                                  # (10 − 0) ÷ (30/3)


def test_ehdl_single_phase_minimum_fault_current():
    r = analyze(open("projects/ehdl_demo/main.ehd", encoding="utf-8").read())
    s = r.sc["LT1"]
    assert s.ik1_min < s.ik_min                                              # 상-중성 루프 = 배선 왕복
    c = next(c for c in r.checks if c.id == "CB_L1:sc_min_trip")
    assert c.actual == pytest.approx(s.ik1_min)


def test_ehdl_hyphen_id_and_unit_case():
    from ehdl.parser import parse
    _, d = parse("panel LP-1 { }\nload M1 { rating = 1kW; }")
    assert any("'-'" in x.message for x in d)
    from ehdl.units import parse_quantity
    assert parse_quantity("1MA", "current")[0] is None and parse_quantity("30mA", "current_ma")[0] == pytest.approx(0.03)


def test_ehdl_deep_tree_drawing():
    from ehdl.drawing import build_sld
    lines = ["system s { frequency=60Hz; }", "source S { voltage=380V; phases=3; }"]
    prev = "S"
    for i in range(1200):
        lines.append(f"bus B{i} {{ feed={prev}; }}")
        prev = f"B{i}"
    lines.append(f"load L {{ feed={prev}; kind=heater; rating=1kW; pf=1; phases=3; }}")
    assert build_sld(analyze("\n".join(lines))).items
