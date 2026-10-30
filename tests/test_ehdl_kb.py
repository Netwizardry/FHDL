"""T-EKB: EHDL 지식 DB (archive/EHDL-Docs PDF → SQLite) 와 원문 대조 규칙.

DB 는 로컬 전용(원문 재배포 금지 문서 포함)이라 없으면 DB 의존 테스트는 skip 한다.
허용전류 기대값은 원문 표를 렌더링해 눈으로 대조한 값이다.
"""
import json
import os
import sys
sys.path.insert(0, "src")

import pytest

from ehdl.kb import KB
from ehdl.rules import RULES_DIR, load_ruleset

DB = os.path.join(os.path.dirname(__file__), "..", "data", "ehdl_kb.db")
kb_required = pytest.mark.skipif(not os.path.exists(DB), reason="지식 DB 없음 (python -m ehdl.kb.build)")


@pytest.fixture(scope="module")
def kb():
    return KB(DB)


def test_missing_db_is_harmless(tmp_path):
    k = KB(str(tmp_path / "none.db"))
    assert not k.available and k.search("전압강하") == [] and k.ampacity("PVC", 3, "Cu", "C", 16) is None


@kb_required
def test_documents_and_kec_edition(kb):
    docs = {d["doc_id"]: d for d in kb.documents()}
    assert {"KEC", "KEC_FULL", "IEC60364-5-52", "KESC_INSPECT", "KEC_CONSTR", "LH_CASE"} <= set(docs)
    assert "2022.01.01 시행" in docs["KEC"]["edition"]
    assert docs["IEC60364-5-52"]["notice"] == "무단전재 및 재배포 금지"


@kb_required
def test_kec_clauses(kb):
    c = kb.clause("232.3.9")
    assert c["title"] == "수용가 설비에서의 전압강하" and c["printed_page"] == "137"
    assert "표 232.3-1" in c["text"]
    assert [r["clause"] for r in kb.subclauses("212.4")] == ["212.4.1", "212.4.2", "212.4.3", "212.4.4"]


@kb_required
@pytest.mark.parametrize("ins, n, mat, method, size, amp", [
    ("PVC", 2, "Cu", "A1", 1.5, 14.5),      # 표 B.52.2
    ("PVC", 2, "Cu", "C", 2.5, 27.0),
    ("PVC", 3, "Cu", "C", 16, 76.0),        # 표 B.52.4
    ("XLPE", 3, "Cu", "C", 35, 147.0),      # 표 B.52.5 (렌더링 대조)
    ("XLPE", 3, "Cu", "C", 95, 278.0),
    ("XLPE", 3, "Cu", "B1", 300, 514.0),
])
def test_ampacity_values(kb, ins, n, mat, method, size, amp):
    assert kb.ampacity(ins, n, mat, method, size)["ampacity_a"] == amp


@kb_required
def test_ampacity_table_shape(kb):
    rows = kb._q("SELECT table_label, material, method, COUNT(*) n FROM ampacity GROUP BY 1,2,3")
    assert len(rows) == 4 * 2 * 7
    for r in rows:
        expect = 16 if r["material"] == "Cu" else (11 if r["method"] == "D2" else 15)
        assert r["n"] == expect, dict(r)


@kb_required
def test_search(kb):
    hits = kb.search("수용가 설비에서의 전압강하", doc_id="KEC")
    assert hits and any(h["printed_page"] == "137" for h in hits)


@kb_required
def test_verified_rules_cite_pages_found_in_kb(kb):
    data = json.load(open(os.path.join(RULES_DIR, "kec_lv.json"), encoding="utf-8"))
    for rid, r in data["rules"].items():
        if not r["verified"] or rid == "AMPACITY_TABLE":
            continue
        found = {(s["doc_id"], s["printed_page"]) for s in kb.rule_sources(rid)}
        cited = {(c["doc"], c["page"]) for c in r["citations"]}
        assert found & cited, (rid, found, cited)


def test_ruleset_flags():
    rs = load_ruleset("kec_lv")
    assert rs.ref("VD_LIMIT").verified and "232.3.9" in rs.ref("VD_LIMIT").citation
    assert rs.values("RESISTIVITY_SERVICE") == {"Cu": 0.0225, "Al": 0.036}
    assert rs.values("OVERLOAD_COORD")["I2_over_Iz_max"] == 1.45
    assert not rs.ref("UNBALANCE_1PH").verified          # 제공 자료에 근거 없음
