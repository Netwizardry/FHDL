"""규격·판정 엔진 (SPEC 6) — 요구조건(Required) 산출, 실제 규격(Installed) 비교, 병목 탐지.

판정 정책
- 판정 시나리오: 동시운전 그룹이 있으면 max_demand(+ 사용자 시나리오), 없으면 normal(+ 사용자).
  정격 합계(rated)는 참고값으로만 쓴다. 대상마다 가장 불리한 시나리오의 값으로 판정한다.
- 입력 부족: 이미 확인된 값만으로 정격을 넘으면 FAIL(빠진 부하는 더할 뿐이므로 확정), 아니면 UNKNOWN.
- 추정 입력(길이 추정·가정 리액턴스·상 미지정 평형 가정): 충족이어도 PASS 대신 REVIEW.
- 원문 미확인 규칙(verified=false): 충족이면 REVIEW, 위반이면 FAIL(규칙 미확인 표시).
- 정격 ≥ 요구는 PASS. 사용률이 review_below 보다 낮고 선정 근거가 없으면 별도 'sizing_rationale' REVIEW.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from .engine import cable_vdrop, loads_under
from .explain import explain
from .model import Check, EResult, Evidence, NodeResult, Requirement, worst
from .rules import RuleSet

DEFAULT_REVIEW_BELOW = 0.8      # 프로그램 기본 설정 (규정 아님) — system { review_below = ...; }


def judging_scenarios(res: EResult) -> List[str]:
    base = "max_demand" if "max_demand" in res.scenarios else "normal"
    return [base] + [k for k, s in res.scenarios.items() if not s.scenario.builtin]


def _worst(res: EResult, getter: Callable[[str], Tuple[Optional[float], Optional[NodeResult]]]):
    best = (None, None, "")
    for sid in judging_scenarios(res):
        v, nr = getter(sid)
        if v is not None and (best[0] is None or v > best[0]):
            best = (v, nr, sid)
    if best[1] is None:                              # 값이 전부 None — 기준 시나리오 결과만 돌려줌
        sid = judging_scenarios(res)[0]
        best = (None, getter(sid)[1], sid)
    return best


def bound_is_exact(nr: Optional[NodeResult]) -> bool:
    """역률 미입력 산술합이 정확한 값인가 — 역률을 모르는 부하가 하나뿐이고 나머지가 없으면 크기는 정확."""
    if nr is None or nr.S_extra <= 0:
        return True
    return len(set(nr.pf_unknown)) == 1 and abs(complex(nr.P, nr.Q)) < 1e-9


def judge(res: EResult, rules: RuleSet, kb=None) -> List[Check]:
    m = res.model
    review_below = float(m.settings.get("review_below") or DEFAULT_REVIEW_BELOW)
    checks: List[Check] = []

    def add(c: Check) -> Check:
        node = m.nodes.get(c.target)
        explain(c, node.name if node and node.name != node.id else c.target)
        checks.append(c)
        return c

    def capacity(target: str, kind: str, title: str, installed: Optional[float], unit: str,
                 value: Callable[[NodeResult], Optional[float]], formula: str, justification: str):
        actual, nr, sid = _worst(res, lambda s: (value(res.scenarios[s].nodes[target]),
                                                 res.scenarios[s].nodes[target]))
        ev = Evidence(inputs=[target] + [i for i, _ in nr.contributors], formula=formula, scenario=sid,
                      contributors=list(nr.contributors))
        if nr.balanced_estimate:
            ev.assumptions.append("단상 부하 접속 상(phase) 미지정 → 평형 가정 전류")
        if nr.S_extra > 0:
            ev.assumptions.append(f"역률 미입력 부하 {len(set(nr.pf_unknown))}개 — 피상전력 산술합(보수적 상한)")
        missing = [f"{i}: {', '.join(res.load_missing.get(i, []))}" for i in dict.fromkeys(nr.incomplete)]
        c = Check(f"{target}:{kind}", target, kind, title, "N/A", installed=installed, unit=unit,
                  actual=actual, evidence=ev, estimated=bool(ev.assumptions))
        if actual is not None:
            c.required = Requirement(title, "≥", actual, unit)
            ev.values = {f"최대 예상({unit})": round(actual, 3)}
        if installed is not None and actual is not None:
            c.utilization = actual / installed if installed > 0 else None
            ev.values[f"정격({unit})"] = installed
        if installed is None:
            c.status = "N/A" if not missing else "UNKNOWN"
        elif actual is not None and actual > installed * (1 + 1e-9):
            c.status = "FAIL" if bound_is_exact(nr) else "REVIEW"
            if c.status == "REVIEW":
                ev.assumptions.append("보수적 상한(산술합)이 정격을 넘음 — 역률을 입력하면 확정 판정")
            elif unit == "A" and nr.current_lb is not None and nr.current_lb <= installed:
                c.status = "REVIEW"
                ev.assumptions.append(f"상 미지정 단상 부하를 한 상에 모은 상한 {actual:.1f} A 가 정격을 넘음 "
                                      f"(하한 {nr.current_lb:.1f} A) — 접속 상(phase)을 입력하면 확정 판정")
        elif missing:
            c.status = "UNKNOWN"
        elif actual is None:
            c.status = "UNKNOWN"
        else:
            c.status = "REVIEW" if c.estimated else "PASS"
        c.missing = missing
        add(c)
        # 선정 근거 (과대 규격 — 단정 금지, 질문 생성)
        if c.status in ("PASS", "REVIEW") and c.utilization is not None and c.utilization < review_below:
            r = Check(f"{target}:sizing_rationale", target, "sizing_rationale", f"{title} 선정 근거",
                      "PASS" if justification else "REVIEW", installed=installed, unit=unit, actual=actual,
                      utilization=c.utilization, evidence=Evidence(
                          inputs=[target], formula=f"사용률 = 최대 예상 ÷ 정격 < 근거 확인 기준 {review_below * 100:.0f}%",
                          values={"justification_text": justification} if justification else {},
                          scenario=sid, contributors=list(nr.contributors)))
            add(r)
        return c

    vll = lambda nr: nr.voltage  # noqa: E731
    for nid in res.order:
        n = m.nodes[nid]
        if n.type == "load" and res.load_missing.get(nid):
            add(Check(f"{nid}:load_input", nid, "load_input", "부하 입력", "UNKNOWN",
                      missing=list(res.load_missing[nid]), evidence=Evidence(inputs=[nid])))
        elif n.type == "load" and res.load_assumed.get(nid):
            add(Check(f"{nid}:load_input", nid, "load_input", "부하 입력", "REVIEW", estimated=True,
                      evidence=Evidence(inputs=[nid], assumptions=list(res.load_assumed[nid]))))
        if n.type == "source":
            if n.installed.get("limit_kw") is not None:
                capacity(nid, "source_limit", "유효전력(사용 가능 한도)", n.installed["limit_kw"], "W",
                         lambda nr: nr.P_max, "P = Σ 운전 부하 유효전력 (상향 집계, 역률 미입력 부하는 P ≤ S)",
                         n.justification)
            if n.installed.get("limit_kva") is not None:
                capacity(nid, "source_limit", "피상전력(사용 가능 한도)", n.installed["limit_kva"], "VA",
                         lambda nr: nr.S, "S = |ΣP + jΣQ|", n.justification)
            _unbalance(res, rules, nid, add)
        elif n.type == "transformer":
            capacity(nid, "transformer_rating", "변압기 용량", n.installed.get("rated"), "VA",
                     lambda nr: nr.S, "S = |ΣP + jΣQ| (2차 측 부하 집계, 변압기 손실 제외)", n.justification)
        elif n.type in ("switchboard", "panel", "bus"):
            capacity(nid, "board_rating", "정격전류", n.installed.get("rated_current"), "A",
                     lambda nr: nr.current, "I = max 상전류 = max|S_k| ÷ V_LN (단상은 접속 상에, 삼상은 1/3씩)",
                     n.justification)
            _unbalance(res, rules, nid, add)
        elif n.type in ("breaker", "rcd"):
            from .judge2 import setting_current
            capacity(nid, "breaker_load", "정격전류 In·설정 Ir (설계전류 IB 이상)", setting_current(n), "A",
                     lambda nr: nr.current, "IB = 하류 부하 최대 상전류, 조건 IB ≤ In", n.justification)
        elif n.type == "load":
            _voltage_drop(res, rules, nid, add)
    for eid, e in m.edges.items():
        if e.type != "cable" or e.to_id not in m.nodes:
            continue
        _cable(res, rules, eid, add, kb)
    from .judge2 import phase2_checks
    from .judge3 import phase3_checks
    phase2_checks(res, rules, res.sc, add)
    phase3_checks(res, rules, add)
    res.checks = checks                    # 산정·혼합 모드는 앞선 판정(전압강하 시나리오 등)을 참조한다
    from .sizing import sizing_checks
    sizing_checks(res, rules, kb, add)
    from .mixed import annotate
    annotate(res)
    return checks


def _cable(res: EResult, rules: RuleSet, eid: str, add, kb=None):
    m = res.model
    e = m.edges[eid]
    iz = e.installed.get("ampacity")
    actual, nr, sid = _worst(res, lambda s: (res.scenarios[s].nodes[e.to_id].current,
                                             res.scenarios[s].nodes[e.to_id]))
    ev = Evidence(inputs=[eid, e.to_id], formula="IB(배선 전류) ≤ IZ(허용전류)", scenario=sid,
                  contributors=list(nr.contributors))
    c = Check(f"{eid}:cable_ampacity", eid, "cable_ampacity", "허용전류 IZ", "N/A", installed=iz, unit="A",
              actual=actual, evidence=ev)
    if actual is not None:
        c.required = Requirement("허용전류 IZ", "≥", actual, "A")
    if iz is None:
        out = _table_ampacity(res, rules, e, nr, kb)
        iz, note = out[0], out[1]
        if iz is not None:
            c.installed = iz
            ev.rule = rules.ref("AMPACITY_CORRECTION")
            ev.defaults.append(note)
            ev.assumptions += out[2]
    if iz is None:
        need = [lab for key, lab in (("install_method", "공사방법(A1~D2)"), ("ambient", "주변 온도"),
                                     ("grouping", "집합 포설 회로 수")) if e.params.get(key) is None]
        if e.installed.get("insulation") is None:
            need.append("절연 종류")
        c.status = "UNKNOWN"
        c.missing = (need or [note]) + ["(또는 보정 반영 허용전류 ampacity 직접 입력)"]
    elif actual is None:
        c.status = "UNKNOWN"
        c.missing = ["하류 부하 입력"]
    else:
        c.utilization = actual / iz
        if nr.balanced_estimate:
            ev.assumptions.append("단상 부하 접속 상 미지정 → 평형 가정 전류")
        if nr.S_extra > 0:
            ev.assumptions.append("역률 미입력 부하 포함 — 피상전력 산술합(보수적 상한)")
        c.estimated = bool(ev.assumptions)
        if actual > iz and nr.current_lb is not None and nr.current_lb <= iz:
            ev.assumptions.append(f"상 미지정 단상 부하 상한 {actual:.1f} A (하한 {nr.current_lb:.1f} A) — 접속 상 입력 후 확정")
            c.estimated = True
            c.status = "REVIEW"
        elif actual > iz and not bound_is_exact(nr):
            ev.assumptions.append("보수적 상한(산술합)이 허용전류를 넘음 — 역률을 입력하면 확정 판정")
            c.estimated = True
            c.status = "REVIEW"
        else:
            c.status = "FAIL" if actual > iz else ("REVIEW" if c.estimated else "PASS")
    add(c)
    # 보호 협조: 이 배선을 보호하는 상위 차단기 In ≤ Iz
    up = m.nodes.get(e.from_id)
    if up is not None and up.type in ("breaker", "rcd") and iz is not None and up.installed.get("rated_current"):
        from .judge2 import setting_current
        In = setting_current(up)
        ref = rules.ref("OVERLOAD_COORD")
        ok = In <= iz
        std = up.installed.get("standard")
        i2f = rules.values("OVERLOAD_COORD")["I2_factor"].get(std or "IEC60898")
        cc = Check(f"{eid}:breaker_cable_coord", up.id, "breaker_cable_coord", f"보호 협조 In ≤ Iz ({eid})",
                   ("REVIEW" if not ref.verified else "PASS") if ok else "FAIL", installed=In, unit="A",
                   actual=iz, required=Requirement("배선 허용전류 IZ", "≥", In, "A", ref.id),
                   evidence=Evidence(inputs=[up.id, eid], formula="IB ≤ In ≤ IZ (식 212.4-1), I2 ≤ 1.45·IZ (식 212.4-2)",
                                     rule=ref, scenario=sid,
                                     values={"In(A)": In, "IZ(A)": iz, "I2(A)": round(i2f * In, 1),
                                             "1.45·IZ(A)": round(1.45 * iz, 1)},
                                     defaults=([] if std else ["제품 규격 미입력 → I2 = 1.45 In(주택용, 보수적)"])))
        if i2f * In > 1.45 * iz:
            cc.status = "FAIL"
        add(cc)


def _next_up(kb, table: str, key: str, x: float):
    """표에 정확한 값이 없으면 바로 위(보수적) 값 — (행, 사용한 x)."""
    rows = kb._q("SELECT x, factor, printed_page FROM correction WHERE table_label=? AND key=? AND x>=? ORDER BY x",
                 (table, key, float(x)))
    return (rows[0], rows[0]["x"]) if rows else (None, None)


def _table_ampacity(res: EResult, rules: RuleSet, e, nr: NodeResult, kb):
    """허용전류 = 표 B.52.2~B.52.5 × 주위온도 계수(B.52.14/15) × 집합 계수(B.52.17/18) (× 토양 B.52.16).

    → (IZ 또는 None, 설명 — None 이면 UNKNOWN 사유). 표 사이 값은 바로 위 값(보수적)을 쓰고 추정으로 표시.
    """
    p, inst = e.params, e.installed
    method = str(p.get("install_method") or "").upper()
    need = [k for k, v in (("공사방법", method in ("A1", "A2", "B1", "B2", "C", "D1", "D2")),
                           ("절연 종류", inst.get("insulation")), ("재질", inst.get("material")),
                           ("단면적", inst.get("size")), ("주변 온도", p.get("ambient") is not None),
                           ("집합 포설 회로 수", p.get("grouping") is not None)) if not v]
    if kb is None or not getattr(kb, "available", False):
        return None, "허용전류 표(지식 DB) 없음 — python -m ehdl.kb.build 필요"
    if need:
        return None, "표 조회 입력 부족: " + ", ".join(need)
    to = res.model.nodes.get(e.to_id)
    loaded = 2 if (to is not None and to.type == "load" and to.params.get("phases") == 1) else 3
    row = kb.ampacity(inst["insulation"], loaded, inst["material"], method, inst["size"])
    if row is None:
        return None, f"표에 없는 조합: {inst['insulation']}·{loaded}도체·{inst['material']}·{method}·{inst['size']:g}㎟"
    ins_key = "PVC" if inst["insulation"] == "PVC" else "XLPE/EPR"
    ground = method.startswith("D")
    notes, est = [], []
    amb_t = "B.52.15" if ground else "B.52.14"
    f_amb, used = _next_up(kb, amb_t, ins_key, p["ambient"])
    if f_amb is None:
        return None, f"주변 온도 {p['ambient']:g}℃ — 표 {amb_t} 범위 밖"
    if used != p["ambient"]:
        est.append(f"주변 온도 {p['ambient']:g}℃ → 표 {amb_t} 의 {used:g}℃ 값(보수적)")
    n = int(p["grouping"])
    f_grp = 1.0
    if n > 1:
        if method == "D2":
            sp = p.get("spacing") or rules.values("AMPACITY_CORRECTION")["default_spacing"]
            if not p.get("spacing"):
                est.append("지중 간격 미입력 → 케이블 접촉(보수적)")
            g, gu = _next_up(kb, "B.52.18", sp, n)
            tbl = "B.52.18"
        elif method == "D1":
            return None, "지중 덕트 집합(표 B.52.19)은 아직 이식하지 않음 — ampacity 직접 입력"
        else:
            arr = p.get("arrangement") or rules.values("AMPACITY_CORRECTION")["default_arrangement"]
            if not p.get("arrangement"):
                est.append("집합 배치 항 미입력 → 항 1 묶음(보수적)")
            g, gu = _next_up(kb, "B.52.17", arr, n)
            tbl = "B.52.17"
            if g is None and arr != "1":            # 항 2~5 는 9회로 이상 추가 저감 없음
                g, gu = kb._q("SELECT x, factor, printed_page FROM correction WHERE table_label='B.52.17' AND key=? "
                              "ORDER BY x DESC LIMIT 1", (arr,))[0], n
        if g is None:
            return None, f"집합 {n}회로 — 표 범위 밖"
        if gu != n:
            est.append(f"집합 {n}회로 → 표 {tbl} 의 {gu:g}회로 값(보수적)")
        f_grp = g["factor"]
        notes.append(f"집합 {f_grp:g} (표 {tbl})")
    f_soil = 1.0
    if ground:
        rho = p.get("soil_resistivity")
        if rho is None:
            est.append("토양 열저항률 미입력 → 기준 2.5 K·m/W")
        else:
            srow, su = _next_up(kb, "B.52.16", "duct" if method == "D1" else "direct", rho)
            if srow is None:
                return None, f"토양 열저항률 {rho:g} — 표 B.52.16 범위 밖"
            f_soil = srow["factor"]
            notes.append(f"토양 {f_soil:g} (표 B.52.16)")
    par = int(inst.get("parallel") or 1)
    iz = row["ampacity_a"] * f_amb["factor"] * f_grp * f_soil * par
    desc = (f"표 {row['table_label']} {method} {inst['size']:g}㎟ {inst['material']} {loaded}개 부하도체 "
            f"{row['ampacity_a']:g} A × 주위온도 {f_amb['factor']:g} (표 {amb_t})"
            + "".join(f" × {x}" for x in notes) + (f" × 병렬 {par}" if par > 1 else "") + f" = {iz:.1f} A")
    return (iz, desc, est)


def _voltage_drop(res: EResult, rules: RuleSet, nid: str, add):
    m = res.model
    n = m.nodes[nid]
    actual, nr, sid = _worst(res, lambda s: (res.scenarios[s].nodes[nid].vdrop_pct
                                             if nid in res.scenarios[s].on_loads else None,
                                             res.scenarios[s].nodes[nid]))
    ref = rules.ref("VD_LIMIT")
    vals = rules.values("VD_LIMIT")
    path = _path_to_source(res, nid)
    supply = "own_substation" if any(m.nodes[p].type == "transformer" for p in path) else "lv_supply"
    kind = n.params.get("kind")
    cat = "lighting" if kind == "lighting" else ("other" if kind else None)
    cables = [res.via_edge[p] for p in path if res.via_edge.get(p)]
    ev = Evidence(inputs=[nid] + cables,
                  formula="u = b(ρ1·L/S·cosφ + λ·L·sinφ)·IB, Δu% = 100·u/U0 (KS C IEC 60364-5-52 부속서 G); 경로 누적",
                  rule=ref, scenario=sid, contributors=[(nid, nr.S)] if nr is not None else [])
    c = Check(f"{nid}:voltage_drop", nid, "voltage_drop", "전압강하", "UNKNOWN", unit="%", actual=actual, evidence=ev)
    missing = []
    for eid in cables:
        e = m.edges[eid]
        for key, lab in (("length", "길이"),):
            if e.params.get(key) is None:
                missing.append(f"{eid}: {lab}")
        for key, lab in (("size", "단면적"), ("material", "재질")):
            if e.installed.get(key) is None:
                missing.append(f"{eid}: {lab}")
        to = res.model.edges[eid].to_id
        for x in cable_vdrop(m, eid, res.scenarios[sid].nodes[to], res.levels, rules)[3]:
            (ev.defaults if x.startswith(("기준 기본값", "불평형률")) else ev.assumptions).append(f"{eid}: {x}")
    if cat is None:
        missing.append(f"{nid}: 용도(kind) — 조명/기타 허용치 구분")
    if res.load_missing.get(nid):
        missing.append(f"{nid}: 부하 입력")
    if not cables:
        c.status = "N/A"
        c.explanation = "배선 없이 연결된 부하 — 전압강하 계산 대상 없음"
        add(c)
        return
    if missing or actual is None:
        c.missing = missing or ["경로 계산 불가"]
        add(c)
        return
    limit = vd_limit(res, rules, nid, nr)
    c.required = Requirement("전압강하", "≤", limit, "%", ref.id)
    ev.values = {"전압강하(%)": round(actual, 3), "허용(%)": round(limit, 3), "경로 길이(m)": round(nr.path_length, 1),
                 "수전 구분": 1.0 if supply == "own_substation" else 0.0}
    c.estimated = bool(ev.assumptions)
    if actual > limit:
        c.status = "FAIL"
    else:
        c.status = "REVIEW" if (c.estimated or not ref.verified) else "PASS"
    add(c)


def vd_limit(res: EResult, rules: RuleSet, nid: str, nr: NodeResult) -> Optional[float]:
    """KEC 표 232.3-1 허용 전압강하(%) — 수전 형태·조명/기타·100 m 초과 가산. 용도(kind) 미입력이면 None."""
    m = res.model
    vals = rules.values("VD_LIMIT")
    kind = m.nodes[nid].params.get("kind")
    if not kind:
        return None
    cat = "lighting" if kind == "lighting" else "other"
    path = _path_to_source(res, nid)
    supply = "own_substation" if any(m.nodes[p].type == "transformer" for p in path) else "lv_supply"
    extra = min(max(nr.path_length - 100.0, 0.0) * vals["over_100m_per_m"], vals["over_100m_max_extra"])
    return vals[supply][cat] + extra


def _path_to_source(res: EResult, nid: str) -> List[str]:
    path, cur = [], nid
    while cur is not None and cur not in path:
        path.append(cur)
        cur = res.upstream.get(cur)
    return path


def _unbalance(res: EResult, rules: RuleSet, nid: str, add):
    """설비불평형률 — 정격(설비) 용량 기준, 하류에 단상 부하가 있을 때만."""
    m = res.model
    loads = sorted(loads_under(m, res.children, nid))
    singles = [i for i in loads if m.nodes[i].params.get("phases") == 1]
    if not singles or res.levels.get(nid, (None, None, 3))[2] == 1:
        return
    ref = rules.ref("UNBALANCE_1PH")
    rated = res.scenarios["rated"].nodes[nid]
    c = Check(f"{nid}:unbalance", nid, "unbalance", "단상 부하 설비불평형률", "UNKNOWN", unit="%",
              evidence=Evidence(inputs=[nid] + singles,
                                formula="(상별 단상 설비용량 최대 − 최소) ÷ (총 설비용량 ÷ 3) × 100", rule=ref,
                                scenario="rated"))
    unassigned = [i for i in singles if not m.nodes[i].params.get("phase")]
    incomplete = [i for i in loads if res.load_missing.get(i)]
    if unassigned or incomplete:
        c.missing = [f"{i}: 접속 상(phase)" for i in unassigned] + [f"{i}: 부하 입력" for i in incomplete]
        add(c)
        return
    from .engine import _PHASE_IDX, load_power
    ll = [i for i in singles if len(_PHASE_IDX[m.nodes[i].params["phase"]]) == 2]
    # 설비불평형률은 '각 선간(또는 상)에 접속되는 단상 설비용량'의 차 — 선간 부하만이면 선간쌍별로 모은다(3상 3선식).
    # 상-중성 부하가 섞이면 상별(선간 부하는 두 상에 절반씩)로 근사.
    pairs = {"L1L2": 0, "L2L3": 1, "L3L1": 2}
    per = [0.0, 0.0, 0.0]
    for i in singles:
        S, _, _ = load_power(m.nodes[i])
        ph = m.nodes[i].params["phase"]
        if ll and len(ll) == len(singles):
            per[pairs[ph]] += abs(S)
        else:
            idx = _PHASE_IDX[ph]
            for k in idx:
                per[k] += abs(S) / len(idx)
    # 분모 = 총 설비용량(kVA 산술합) ÷ 3 — 벡터합이 아니다
    total = sum(abs(load_power(m.nodes[i])[0] or 0) for i in loads)
    pct = (max(per) - min(per)) / (total / 3.0) * 100.0 if total > 0 else 0.0
    lim = rules.values("UNBALANCE_1PH")["limit_pct"]
    c.actual = pct
    c.required = Requirement("설비불평형률", "≤", lim, "%", ref.id)
    labels = ("L1-L2", "L2-L3", "L3-L1") if (ll and len(ll) == len(singles)) else ("L1", "L2", "L3")
    c.evidence.values = {f"{labels[0]}(VA)": round(per[0]), f"{labels[1]}(VA)": round(per[1]),
                         f"{labels[2]}(VA)": round(per[2]), "총 설비용량 산술합(VA)": round(total)}
    if ll and len(ll) != len(singles):
        c.evidence.assumptions.append("상-중성·선간 단상 부하 혼재 — 선간 부하는 두 상에 절반씩(근사)")
    c.status = "FAIL" if pct > lim else ("PASS" if ref.verified else "REVIEW")
    add(c)


# ---------------------------------------------------------------------------
# 병목
# ---------------------------------------------------------------------------

def bottlenecks(res: EResult) -> List[dict]:
    """FAIL 검사마다: 대상·초과 조건·원인 부하·전원까지 경로·검토 설비 (SPEC 6.4)."""
    out = []
    for c in res.checks:
        if c.status != "FAIL":
            continue
        target_node = c.target if c.target in res.model.nodes else res.model.edges[c.target].to_id
        path = _path_to_source(res, target_node)
        out.append({"target": c.target, "check": c.title, "kind": c.kind,
                    "exceed": (c.actual - c.installed) if (c.actual is not None and c.installed is not None
                                                           and c.kind != "breaker_cable_coord") else None,
                    "unit": c.unit, "scenario": c.evidence.scenario,
                    "causes": [i for i, _ in c.evidence.contributors[:5]],
                    "path": list(reversed(path)),
                    "upstream_status": {p: res.node_status(p) for p in path[1:]},
                    "new_load_caused": "신규 부하 전 사용률(%)" in c.evidence.values})
    return out


def node_status(res: EResult, nid: str) -> str:
    return worst(c.status for c in res.checks if c.target == nid)
