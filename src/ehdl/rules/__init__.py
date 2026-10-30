"""규칙(규정) 데이터 로더 — 코드와 분리된 JSON (SPEC 9.3, 결정 D2).

규칙마다 출처·조항·버전·verified 를 가진다. verified=false 규칙을 쓰는 판정은 PASS 가 아니라
REVIEW 로 낸다(원문 확인 전이므로 확정 판정 금지).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict

from ..model import RuleRef

RULES_DIR = os.path.dirname(__file__)


class RuleSet:
    def __init__(self, data: dict):
        self.id = data["ruleset"]
        self.title = data.get("title", self.id)
        self.version = data.get("version", "")
        self._rules: Dict[str, dict] = data["rules"]

    def values(self, rule_id: str) -> dict:
        return self._rules[rule_id]["values"]

    def ref(self, rule_id: str) -> RuleRef:
        r = self._rules[rule_id]
        cites = "; ".join(f"{c['doc']} {c['ref']} (p.{c['page']})" for c in r.get("citations", []))
        return RuleRef(rule_id, r["title"], r["source"], r["clause"], self.version, bool(r.get("verified")),
                       cites)

    def explain(self, rule_id: str) -> str:
        return self._rules[rule_id].get("explain", "")

    def ids(self):
        return list(self._rules)


@lru_cache(maxsize=8)
def load_ruleset(name: str = "kec_lv") -> RuleSet:
    path = name if name.endswith(".json") else os.path.join(RULES_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return RuleSet(json.load(f))
