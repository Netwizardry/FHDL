"""EHDL 지식 DB 조회 — KEC 조항·원문 쪽·허용전류 표·규칙 근거 (SQLite, 표준 라이브러리만 사용).

DB 는 `python -m ehdl.kb.build archive/EHDL-Docs` 로 만든다(로컬 전용, 원문 재배포 금지 문서 포함).
DB 가 없으면 조회 함수는 빈 결과를 돌려준다 — 엔진은 DB 없이도 동작한다.
"""
from __future__ import annotations

import os
import sqlite3
from typing import List, Optional

DEFAULT_DB = os.path.join(os.getcwd(), "data", "ehdl_kb.db")

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE documents(doc_id TEXT PRIMARY KEY, file TEXT, title TEXT, kind TEXT, issuer TEXT,
                       edition TEXT, pages INTEGER, sha256 TEXT, notice TEXT);
CREATE TABLE pages(id INTEGER PRIMARY KEY, doc_id TEXT, pdf_page INTEGER, printed_page TEXT, text TEXT,
                   UNIQUE(doc_id, pdf_page));
CREATE TABLE clauses(id INTEGER PRIMARY KEY, doc_id TEXT, clause TEXT, title TEXT, pdf_page INTEGER,
                     printed_page TEXT, depth INTEGER, parent TEXT, text TEXT, UNIQUE(doc_id, clause));
CREATE TABLE tables(id INTEGER PRIMARY KEY, doc_id TEXT, label TEXT, caption TEXT, pdf_page INTEGER,
                    printed_page TEXT, UNIQUE(doc_id, label, pdf_page));
CREATE TABLE ampacity(doc_id TEXT, table_label TEXT, insulation TEXT, loaded_conductors INTEGER,
                      material TEXT, method TEXT, size_mm2 REAL, ampacity_a REAL, conductor_temp_c REAL,
                      ambient_ref TEXT, pdf_page INTEGER, printed_page TEXT,
                      PRIMARY KEY(table_label, material, method, size_mm2));
CREATE TABLE correction(table_label TEXT, kind TEXT, key TEXT, x REAL, factor REAL, pdf_page INTEGER,
                        printed_page TEXT, PRIMARY KEY(table_label, key, x));
CREATE TABLE rule_sources(rule_id TEXT, doc_id TEXT, ref TEXT, pdf_page INTEGER, printed_page TEXT,
                          quote TEXT);
CREATE VIRTUAL TABLE pages_fts USING fts5(text, content='pages', content_rowid='id', tokenize='trigram');
CREATE VIRTUAL TABLE clauses_fts USING fts5(clause, title, text, content='clauses', content_rowid='id',
                                            tokenize='trigram');
"""


class KB:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        self.con = sqlite3.connect(path) if os.path.exists(path) else None
        if self.con:
            self.con.row_factory = sqlite3.Row

    @property
    def available(self) -> bool:
        return self.con is not None

    def _q(self, sql: str, args=()) -> List[sqlite3.Row]:
        return self.con.execute(sql, args).fetchall() if self.con else []

    def documents(self):
        return self._q("SELECT * FROM documents ORDER BY doc_id")

    def clause(self, number: str, doc_id: str = "KEC") -> Optional[sqlite3.Row]:
        r = self._q("SELECT * FROM clauses WHERE doc_id=? AND clause=?", (doc_id, number))
        return r[0] if r else None

    def subclauses(self, number: str, doc_id: str = "KEC"):
        return self._q("SELECT clause,title,printed_page FROM clauses WHERE doc_id=? AND parent=? ORDER BY id",
                       (doc_id, number))

    def search(self, query: str, limit: int = 20, doc_id: Optional[str] = None):
        """전문 검색(3글자 이상: trigram) → (doc_id, pdf_page, printed_page, 발췌)."""
        if len(query) < 3:
            sql = ("SELECT doc_id,pdf_page,printed_page,text FROM pages WHERE text LIKE ? "
                   + ("AND doc_id=? " if doc_id else "") + "LIMIT ?")
            args = [f"%{query}%"] + ([doc_id] if doc_id else []) + [limit]
        else:
            sql = ("SELECT p.doc_id,p.pdf_page,p.printed_page,snippet(pages_fts,0,'[',']','…',24) AS text "
                   "FROM pages_fts JOIN pages p ON p.id=pages_fts.rowid WHERE pages_fts MATCH ? "
                   + ("AND p.doc_id=? " if doc_id else "") + "ORDER BY rank LIMIT ?")
            args = ['"' + query.replace('"', '""') + '"'] + ([doc_id] if doc_id else []) + [limit]
        return self._q(sql, args)

    def rule_sources(self, rule_id: str):
        return self._q("SELECT * FROM rule_sources WHERE rule_id=?", (rule_id,))

    def correction(self, table_label: str, key: str, x: float) -> Optional[sqlite3.Row]:
        """보정계수 (표 B.52.14 주위온도 · B.52.15 지중온도 · B.52.16 토양 열저항률 · B.52.17 집합 · B.52.18 지중 집합).

        key: 절연(PVC / XLPE/EPR) · 배치 항(1~5) · 간격(touch, 1d, 0.125, 0.25, 0.5) · 덕트/직매(duct, direct).
        x: 온도(℃) · 회로 수 · 열저항률. 표에 있는 값만(보간 없음) — 없으면 None.
        """
        r = self._q("SELECT * FROM correction WHERE table_label=? AND key=? AND x=?", (table_label, key, float(x)))
        return r[0] if r else None

    def ampacity(self, insulation: str, loaded_conductors: int, material: str, method: str,
                 size_mm2: float) -> Optional[sqlite3.Row]:
        """KS C IEC 60364-5-52 표 B.52.2~B.52.5 기준 허용전류 (보정 전, 기준 주위온도)."""
        ins = "PVC" if insulation.upper() == "PVC" else "XLPE/EPR"
        r = self._q("SELECT * FROM ampacity WHERE insulation=? AND loaded_conductors=? AND material=? "
                    "AND method=? AND size_mm2=?", (ins, loaded_conductors, material, method, size_mm2))
        return r[0] if r else None
