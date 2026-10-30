"""EHDL 지식 DB 빌더 — archive/EHDL-Docs 의 PDF(KEC·KS C IEC 60364-5-52·검사기준·가이드) → SQLite.

    python -m ehdl.kb.build archive/EHDL-Docs [-o data/ehdl_kb.db]

만드는 것 (스키마는 ehdl/kb/__init__.py SCHEMA):
  documents  문서 메타(종류·발행·판·쪽수·sha256·이용 제한 문구)
  pages      쪽별 원문 (PDF 쪽 + 인쇄 쪽번호)              + pages_fts (trigram 전문검색)
  clauses    KEC 조항(번호·제목·본문·쪽) — 규정 문서만        + clauses_fts
  tables     표 번호·제목·쪽 (표 232.3-1, 표 B.52.4 …)
  ampacity   KS C IEC 60364-5-52 표 B.52.2~B.52.5 허용전류 (절연·부하도체 수·재질·공사방법·단면적)
  rule_sources  EHDL 규칙(rules/*.json) ↔ 원문 조항·쪽 연결

원문은 '무단전재 및 재배포 금지' 문서를 포함하므로 DB 는 로컬 전용(.gitignore)이다.
PDF 읽기에 PyMuPDF(pymupdf)가 필요하다 — 빌드 때만 쓰고, DB 조회(ehdl.kb)는 표준 sqlite3 만 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import sys
from typing import Dict, List, Optional, Tuple

from . import SCHEMA, DEFAULT_DB

# 파일명 일부 → (doc 키, 종류, 발행처, 판/시행, 제목)
DOC_CATALOG = [
    ("한국전기설비규정(KEC)_규정집", "KEC", "regulation", "산업통상자원부 공고 제2021-509호",
     "2021.07.01 개정 (2022.01.01 시행)", "한국전기설비규정(KEC) 규정집"),
    ("2021 한국전기설비규정(KEC) 개정 전문", "KEC_FULL", "regulation", "산업통상자원부",
     "2021 개정", "2021 한국전기설비규정(KEC) 개정 전문"),
    ("KS C IEC 60364-5-52", "IEC60364-5-52", "standard_ref", "KEC 검사판정기준 부록",
     "KS C IEC 60364-5-52(2012)", "전기기기의 선정 및 설치 — 배선설비 (참고자료)"),
    ("전기설비 검사, 점검 기준", "KESC_INSPECT", "inspection", "전기설비 검사·점검 기준",
     "2022.1.1 시행", "전기설비 검사, 점검 기준"),
    ("자가용전기설비 검사업무 적용 가이드", "KESC_GUIDE", "guide", "-", "-",
     "KEC 및 KESC 자가용전기설비 검사업무 적용 가이드"),
    ("검사기준_변화", "KESCO_CHANGE", "guide", "한국전기안전공사", "-", "KEC 적용에 따른 검사기준 변화"),
    ("KEC_시공_가이드북", "KEC_CONSTR", "guide", "-", "-", "KEC 시공 가이드북"),
    ("주택단지_설계사례", "LH_CASE", "case", "LH", "-", "KEC 부합 주택단지 설계사례"),
    ("KFS-462", "KFS462", "standard_ref", "-", "-", "KFS-462 전기설비 유지관리기준"),
]

_TOC = re.compile(r"[·∙…]{3,}|\.{6,}")
_KEC_CLAUSE = re.compile(r"^(\d{3}(?:\.\d{1,2}){0,3})\s+([^\d\s·][^·]{0,70})$")
_TABLE = re.compile(r"^(표\s*(?:[A-Z]\.)?\d{2,3}(?:[.\-]\d+)*)\s*(.{0,80})$")
_PRINTED = re.compile(r"^(?:-\s*)?([ivxlc]+|\d{1,4})(?:\s*-)?$", re.I)
_NOTICE = ("무단전재 및 재배포 금지", "무단전재", "재배포 금지")


def _catalog(fname: str):
    for key, doc_id, kind, issuer, edition, title in DOC_CATALOG:
        if key in fname:
            return doc_id, kind, issuer, edition, title
    base = os.path.splitext(fname)[0]
    return re.sub(r"\W+", "_", base)[:40], "other", "-", "-", base


def _printed_page(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:8] + lines[-3:]:
        m = _PRINTED.match(ln)
        if m:
            return m.group(1)
        m = re.search(r"[▸‣]\s*(\d{2,4})|(\d{2,4})\s*[▸‣]", ln)
        if m:
            return m.group(1) or m.group(2)
    return ""


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _clauses(pages: List[Tuple[int, str, str]]) -> List[dict]:
    """KEC 조항 분리: 줄 머리 '232.3.9 제목' (목차 줄 제외), 다음 머리까지 본문."""
    out: List[dict] = []
    cur: Optional[dict] = None
    last_top = None
    for pno, printed, text in pages:
        if _TOC.search(text) and text.count("··") > 5:
            continue                                  # 목차 쪽
        for ln in text.splitlines():
            s = ln.strip()
            m = _KEC_CLAUSE.match(s)
            if m and not _TOC.search(s):
                num = m.group(1)
                top = int(num.split(".")[0])
                if last_top is not None and abs(top - last_top) > 200:
                    m = None                          # 본문 속 숫자 오인 방지
                elif num.count(".") == 0 and len(m.group(2)) > 40:
                    m = None
            if m and not _TOC.search(s):
                if cur:
                    out.append(cur)
                num = m.group(1)
                last_top = int(num.split(".")[0])
                cur = {"clause": num, "title": m.group(2).strip(), "pdf_page": pno, "printed_page": printed,
                       "depth": num.count("."), "parent": num.rsplit(".", 1)[0] if "." in num else "",
                       "lines": []}
            elif cur is not None:
                cur["lines"].append(s)
    if cur:
        out.append(cur)
    # 같은 번호가 여러 번이면(본문 인용 등) 본문이 가장 긴 것
    best: Dict[str, dict] = {}
    for c in out:
        c["text"] = "\n".join(c.pop("lines")).strip()
        if c["clause"] not in best or len(c["text"]) > len(best[c["clause"]]["text"]):
            best[c["clause"]] = c
    return sorted(best.values(), key=lambda c: (c["pdf_page"], c["clause"]))


# ---------------------------------------------------------------------------
# 허용전류 표 (KS C IEC 60364-5-52 표 B.52.2 ~ B.52.5)
# ---------------------------------------------------------------------------

_AMP_TABLES = {"B.52.2": ("PVC", 2, 70.0), "B.52.3": ("XLPE/EPR", 2, 90.0),
               "B.52.4": ("PVC", 3, 70.0), "B.52.5": ("XLPE/EPR", 3, 90.0)}
_METHODS = ["A1", "A2", "B1", "B2", "C", "D1", "D2"]


def _num(s: str) -> Optional[float]:
    try:
        return float(s)
    except ValueError:
        return None


def _runs(nums: List[float]) -> List[List[float]]:
    """증가하는 연속 구간으로 나눈다 (표의 세로줄 = 단면적 증가에 따라 증가)."""
    runs, cur = [], []
    for v in nums:
        if cur and v <= cur[-1]:
            runs.append(cur)
            cur = []
        cur.append(v)
    if cur:
        runs.append(cur)
    return runs


def parse_ampacity_page(text: str):
    """→ (표 번호, [(재질, 공사방법, 단면적, 허용전류)]) 또는 None (검증 실패)."""
    m = re.search(r"표\s*(B\.52\.[2-5])\b", text)
    if not m or m.group(1) not in _AMP_TABLES:
        return None
    label = m.group(1)
    body = text[text.find("구  리") if "구  리" in text else text.find("구리"):]
    parts = re.split(r"알루미늄", body, maxsplit=1)
    if len(parts) != 2:
        return None
    rows = []
    for material, chunk in (("Cu", parts[0]), ("Al", parts[1])):
        chunk = chunk.split("【비고】")[0]
        nums = [v for v in (_num(t) for t in chunk.split()) if v is not None]
        runs = _runs(nums)
        if len(runs) < 1 + len(_METHODS):
            return None
        sizes, cols = runs[0], runs[1:1 + len(_METHODS)]
        for method, col in zip(_METHODS, cols):
            if len(col) > len(sizes):
                return None
            for size, amp in zip(sizes[len(sizes) - len(col):], col):   # 짧은 세로줄은 큰 단면적 쪽 정렬
                rows.append((material, method, size, amp))
    return label, rows


# ---------------------------------------------------------------------------
# 보정계수 표 (표 B.52.14 ~ B.52.18)
# ---------------------------------------------------------------------------

def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[\s|]+", text) if t]


def _vals(tokens: List[str]) -> List[Optional[float]]:
    return [None if t in ("-", "−") else _num(t) for t in tokens]


def parse_corrections(pno: int, printed: str, text: str) -> List[tuple]:
    """→ [(표, 종류, 키, x, 계수, 쪽, 인쇄쪽)]. 표 구조를 검증하고 맞지 않으면 그 표는 건너뛴다."""
    rows: List[tuple] = []
    if "표 B.52.14" in text:
        body = text.split("노출로 접촉할")[-1].split("무단전재")[0]
        toks = [t for t in _tokens(body) if re.fullmatch(r"\d+(\.\d+)?|-", t)]
        temps = [float(t) for t in toks[:18]]
        if temps == [float(x) for x in range(10, 100, 5)] and len(toks) >= 18 * 5:
            for key, col in zip(("PVC", "XLPE/EPR", "MI70", "MI105"), range(4)):
                for T, f in zip(temps, _vals(toks[18 * (col + 1): 18 * (col + 2)])):
                    if f is not None:
                        rows.append(("B.52.14", "ambient_air", key, T, f, pno, printed))
    if "표 B.52.15" in text:
        body = text.split("XLPE, EPR")[-1].split("표 B.52.16")[0]
        toks = [t for t in _tokens(body) if re.fullmatch(r"\d+(\.\d+)?|-", t)]
        temps = [float(t) for t in toks[:14]]
        if temps == [10, 15, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80] and len(toks) >= 14 * 3:
            for key, col in (("PVC", 1), ("XLPE/EPR", 2)):
                for T, f in zip(temps, _vals(toks[14 * col: 14 * (col + 1)])):
                    if f is not None:
                        rows.append(("B.52.15", "ambient_ground", key, T, f, pno, printed))
    if "표 B.52.16" in text:
        m = re.search(r"K·m/W\s*\|?\s*((?:[\d.]+\s*\|?\s*){7}).*?보정계수\s*\|?\s*((?:[\d.]+\s*\|?\s*){7})"
                      r".*?보정계수\s*\|?\s*((?:[\d.]+\s*\|?\s*){7})", text.replace("ㆍ", "·"), re.S)
        if m:
            xs = [float(t) for t in _tokens(m.group(1))]
            for key, grp in (("duct", 2), ("direct", 3)):
                for x, f in zip(xs, [float(t) for t in _tokens(m.group(grp))]):
                    rows.append(("B.52.16", "soil", key, x, f, pno, printed))
    if "표 B.52.17" in text:
        counts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 20]
        for item, line in enumerate(re.findall(r"((?:\d\.\d{2}\s){8,11}\d\.\d{2})", text), start=1):
            vals = [float(v) for v in line.split()]
            if item <= 5:
                for n, f in zip(counts, vals):
                    rows.append(("B.52.17", "grouping", str(item), float(n), f, pno, printed))
    if "표 B.52.18" in text:
        body = text.split("0.5m")[-1].split("【주】")[0]
        toks = [t for t in _tokens(body) if re.fullmatch(r"\d+(\.\d+)?", t)]
        counts = [2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 20]
        if [float(t) for t in toks[:11]] == [float(c) for c in counts] and len(toks) >= 11 * 6:
            for key, col in zip(("touch", "1d", "0.125", "0.25", "0.5"), range(5)):
                for n, f in zip(counts, toks[11 * (col + 1): 11 * (col + 2)]):
                    rows.append(("B.52.18", "grouping_buried", key, float(n), float(f), pno, printed))
    return rows


# ---------------------------------------------------------------------------
# 규칙 ↔ 원문
# ---------------------------------------------------------------------------

RULE_SOURCES = [
    # (규칙 ID, 문서, 조항/표, 찾을 문구)
    ("VD_LIMIT", "KEC", "232.3.9", "표 232.3-1"),
    ("VD_LIMIT", "IEC60364-5-52", "부속서 G 표 G.52.1", "G.52.1"),
    ("OVERLOAD_COORD", "KEC", "212.4.1", "212.4.1 도체와 과부하 보호장치 사이의 협조"),
    ("CONDUCTOR_TEMP", "KEC", "232.5.1 표 232.5-1", "표 232.5-1 절연물의 종류에 대한 최고허용온도"),
    ("RESISTIVITY_SERVICE", "IEC60364-5-52", "부속서 G (ρ1)", "0.0225"),
    ("REACTANCE_DEFAULT", "IEC60364-5-52", "부속서 G (λ)", "리액턴스"),
    ("VD_UNBALANCED_AS_1PH", "KEC_CONSTR", "전압강하 계산식 (b 계수)", "불평형률"),
    ("VD_UNBALANCED_AS_1PH", "LH_CASE", "전압강하식 (b 계수)", "불평형률"),
    ("OVERLOAD_COORD", "KEC", "표 212.3-2·212.3-4", "표 212.3-2 과전류트립 동작시간"),
    ("TRIP_INSTANTANEOUS", "KEC", "표 212.3-3", "표 212.3-3 순시트립에 따른 구분"),
    ("BREAKING_CAPACITY", "KEC", "212.5.5의 1", "정격차단용량은 단락전류보호장치 설치 점에서"),
    ("SC_METHOD", "KESC_INSPECT", "220.1.2", "220.1.2 단락전류 산출"),
    ("SC_VOLTAGE_FACTOR", "KESC_INSPECT", "표 220-3", "전압계수(c)"),
    ("SC_TEMP_LIMIT", "KESC_INSPECT", "표 220-4", "절연재료 종류에 따른 단락회로 온도 한계"),
    ("K_FACTOR", "KEC", "표 212.5-1", "표 212.5-1 도체에 대한 k 값"),
    ("SC_THERMAL", "KEC", "212.5.5의 2", "케이블 등의 단락전류"),
    ("MOTOR_START_VD", "KESC_INSPECT", "240절 기동 전압강하", "따른 허용전압강하를 고려한"),
    ("MOTOR_START_PROTECTION", "KEC_CONSTR", "MCCB 오동작 방지", "최소동작시간"),
    ("START_METHOD", "KESC_INSPECT", "240.3.1 기동방식 계수", "Inverter 기동"),
    ("RCD_TYPES", "KESCO_CHANGE", "누전차단기 동작시간 형별", "시연형"),
    ("RCD_SOCKET", "KEC", "211.2.3의 4", "정격전류 20 A 이하 콘센트"),
    ("RCD_SENSITIVITY", "KEC", "p.43", "정격감도전류가 30 mA 이하, 동작시간이 0.03초"),
    ("SPD_SELECTION", "KEC", "153.1.4", "153.1.4 서지보호장치 시설"),
    ("AMPACITY_CORRECTION", "IEC60364-5-52", "표 B.52.14", "표 B.52.14 기중 케이블의 허용전류에 적용되는"),
    ("ADS_TN", "KEC", "211.2.5의 6", "6. 보호장치의 특성과 회로의 임피던스는"),
    ("TNC_NO_RCD", "KEC", "211.2.5의 8", "TN-C 계통에는 누전차단기를 사용해서는"),
    ("ADS_TT", "KEC", "211.2.6", "TT 계통은 누전차단기를 사용하여 고장보호를"),
    ("ADS_IT", "KEC", "211.2.7", "노출도전부 또는 대지로 단일고장이 발생한"),
    ("DISCONNECT_TIME", "KEC", "표 211.2-1", "표 211.2-1 32 A 이하 분기회로의 최대 차단시간"),
    ("PE_MIN_SIZE", "KEC", "표 142.3-1", "표 142.3-1 보호도체의 최소 단면적"),
    ("BONDING_MAIN", "KEC", "143.3.1", "주접지단자에 접속하기 위한 등전위본딩 도체는"),
    ("TX_CAPACITY", "KESC_INSPECT", "230.4.3", "230.4.3 변압기 용량산정"),
]


def build(src_dir: str, db_path: str = DEFAULT_DB, verbose: bool = True) -> dict:
    import pymupdf
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    stats = {"documents": 0, "pages": 0, "clauses": 0, "tables": 0, "ampacity": 0, "rule_sources": 0,
             "skipped_tables": []}
    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".pdf"))
    doc_pages: Dict[str, List[Tuple[int, str, str]]] = {}
    for fname in files:
        path = os.path.join(src_dir, fname)
        doc_id, kind, issuer, edition, title = _catalog(fname)
        d = pymupdf.open(path)
        pages = []
        notice = ""
        for i, p in enumerate(d):
            t = p.get_text()
            if not notice and any(n in t for n in _NOTICE):
                notice = "무단전재 및 재배포 금지"
            pages.append((i + 1, _printed_page(t), t))
        con.execute("INSERT INTO documents(doc_id,file,title,kind,issuer,edition,pages,sha256,notice) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (doc_id, fname, title, kind, issuer, edition, d.page_count, _sha256(path), notice))
        con.executemany("INSERT INTO pages(doc_id,pdf_page,printed_page,text) VALUES (?,?,?,?)",
                        [(doc_id, n, pr, t) for n, pr, t in pages])
        doc_pages[doc_id] = pages
        stats["documents"] += 1
        stats["pages"] += len(pages)
        if kind == "regulation" and doc_id == "KEC":
            for c in _clauses(pages):
                con.execute("INSERT INTO clauses(doc_id,clause,title,pdf_page,printed_page,depth,parent,text) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (doc_id, c["clause"], c["title"], c["pdf_page"], c["printed_page"], c["depth"],
                             c["parent"], c["text"]))
                stats["clauses"] += 1
        for n, pr, t in pages:
            for ln in t.splitlines():
                mt = _TABLE.match(ln.strip())
                if mt and not _TOC.search(ln):
                    con.execute("INSERT OR IGNORE INTO tables(doc_id,label,caption,pdf_page,printed_page) "
                                "VALUES (?,?,?,?,?)",
                                (doc_id, re.sub(r"\s+", " ", mt.group(1)), mt.group(2).strip(), n, pr))
        if doc_id == "IEC60364-5-52":
            for n, pr, t in pages:
                parsed = parse_ampacity_page(t)
                if parsed is None:
                    if re.search(r"^표\s*B\.52\.[2-5]\s*$", t, re.M):
                        stats["skipped_tables"].append(n)
                    continue
                label, rows = parsed
                ins, cond, temp = _AMP_TABLES[label]
                con.executemany(
                    "INSERT OR REPLACE INTO ampacity(doc_id,table_label,insulation,loaded_conductors,material,"
                    "method,size_mm2,ampacity_a,conductor_temp_c,ambient_ref,pdf_page,printed_page) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(doc_id, label, ins, cond, mat, meth, size, amp, temp, "기중 30℃ / 지중 20℃", n, pr)
                     for mat, meth, size, amp in rows])
                stats["ampacity"] += len(rows)
            for n, pr, t in pages:
                corr = parse_corrections(n, pr, t)
                con.executemany("INSERT OR REPLACE INTO correction VALUES (?,?,?,?,?,?,?)", corr)
                stats["correction"] = stats.get("correction", 0) + len(corr)
        if verbose:
            print(f"  {doc_id:15s} {d.page_count:5d}쪽  {title}", file=sys.stderr)
    for rule_id, doc_id, ref, needle in RULE_SOURCES:
        for n, pr, t in doc_pages.get(doc_id, []):
            j = t.find(needle)
            if j >= 0:
                quote = re.sub(r"\s+", " ", t[max(0, j - 40): j + 260]).strip()
                con.execute("INSERT INTO rule_sources(rule_id,doc_id,ref,pdf_page,printed_page,quote) "
                            "VALUES (?,?,?,?,?,?)", (rule_id, doc_id, ref, n, pr, quote))
                stats["rule_sources"] += 1
                break
    stats["tables"] = con.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
    con.execute("INSERT INTO pages_fts(pages_fts) VALUES ('rebuild')")
    con.execute("INSERT INTO clauses_fts(clauses_fts) VALUES ('rebuild')")
    con.execute("INSERT INTO meta(key,value) VALUES ('source_dir',?),('builder','ehdl.kb.build')",
                (os.path.abspath(src_dir),))
    con.commit()
    con.close()
    return stats


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="EHDL 지식 DB 빌드 (PDF → SQLite)")
    ap.add_argument("src", help="PDF 폴더 (예: archive/EHDL-Docs)")
    ap.add_argument("-o", "--out", default=DEFAULT_DB)
    a = ap.parse_args(argv)
    st = build(a.src, a.out)
    print(f"문서 {st['documents']} · 쪽 {st['pages']} · KEC 조항 {st['clauses']} · 표 {st['tables']} · "
          f"허용전류 {st['ampacity']}행 · 보정계수 {st.get('correction', 0)}행 · 규칙 근거 {st['rule_sources']}"
          + (f" · 해석 실패 표 쪽 {st['skipped_tables']}" if st["skipped_tables"] else ""))
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
