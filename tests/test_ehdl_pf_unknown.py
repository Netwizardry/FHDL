"""T-EPF: 역률 미입력 kVA 부하 — 국내 부하 일람표(VA 만 기재) 대응. 크기는 알므로 보수적 산술합으로 판정."""
import math
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.pipeline import analyze

HEAD = """system plant { frequency = 60Hz; }
source S { voltage = 380V; phases = 3; }
panel P { feed = S; rated_current = %sA; }
"""


def run(body, rated=100):
    r = analyze(HEAD % rated + body)
    assert r.status == "OK", [(d.code, d.message) for d in r.diagnostics]
    return r


def chk(r, cid):
    return next(c for c in r.checks if c.id == cid)


def test_kva_without_pf_is_aggregated_not_unknown():
    r = run("load A { parent = P; kind = general; rating = 40kVA; phases = 3; }")
    nr = r.scenarios["normal"].nodes["P"]
    assert nr.current == pytest.approx(40000 / (math.sqrt(3) * 380))
    c = chk(r, "A:load_input")
    assert c.status == "REVIEW" and c.questions and "역률" in c.questions[0]
    assert chk(r, "P:board_rating").status in ("PASS", "REVIEW")


def test_single_pf_unknown_load_over_rating_is_exact_fail():
    c = chk(run("load A { parent = P; kind = general; rating = 70kVA; phases = 3; }"), "P:board_rating")
    assert c.status == "FAIL"                                   # 부하 하나 → 크기 정확


def test_arithmetic_bound_over_rating_is_review():
    r = run("load A { parent = P; kind = general; rating = 35kVA; phases = 3; }\n"
            "load B { parent = P; kind = heater; rating = 35kW; pf = 1; phases = 3; }")
    c = chk(r, "P:board_rating")
    nr = r.scenarios["normal"].nodes["P"]
    assert nr.S == pytest.approx(70000) and c.status == "REVIEW"   # |35∠0| + 35(위상 모름) 상한
    assert any("상한" in a for a in c.evidence.assumptions)


def test_voltage_drop_uses_worst_angle():
    body = ("cable C { from = P; to = A; length = 100m; material = Cu; size = 10mm2; }\n"
            "load A { kind = general; rating = 10kVA; phases = 3; %s }")
    unknown = chk(run(body % ""), "A:voltage_drop")
    unity = chk(run(body % "pf = 1;"), "A:voltage_drop")
    assert unknown.actual >= unity.actual and unknown.status != "PASS"
    assert any("최악 역률각" in a for a in unknown.evidence.assumptions)


def test_kw_without_pf_still_unknown():
    r = run("load A { parent = P; kind = heater; rating = 10kW; phases = 3; basis = input; }")
    assert chk(r, "A:load_input").status == "UNKNOWN"


def test_sld_labels_fit_and_new_tag_only_when_mixed():
    from ehdl.drawing import _fit, _tw, build_sld
    assert all(_tw(x, 2.0) <= 20 for x in _fit("아주 긴 설비 이름 MCCB 4P 125/125 주차단기 (지하층)", 20, 2.0))
    many = "".join(f"load L{i} {{ parent = P; kind = general; rating = 1kVA; phases = 3; stage = new; "
                   f"name = \"매우 긴 부하 이름 {i} — 추후 기계 동력용\"; }}\n" for i in range(14))
    r = analyze(HEAD.replace("rated_current = %sA;", "rated_current = 400A; stage = new;") + many)
    texts = [t.text for t in build_sld(r).items if hasattr(t, "text")]
    assert not any("[신규]" in t for t in texts)                     # 전부 신규 → 주석 한 줄
    assert any("모든 설비 신규" in t for t in texts)
    r2 = run(many, rated=400)                                         # 반은 기존, 부하는 신규 → 혼합
    assert any("[신규]" in t for t in (t.text for t in build_sld(r2).items if hasattr(t, "text")))
