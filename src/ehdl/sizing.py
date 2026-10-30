"""전선 규격 산정 (SPEC 5.3) — 여러 조건을 동시에 만족하는 최소 단면적과 후보.

배선마다 표준 공칭 단면적(KS C IEC 60228)을 작은 것부터 대입해 조건별 최소값을 구하고, 그 최댓값을 요구 단면적으로 한다.

| 조건 | 식 | 기준 |
|---|---|---|
| 허용전류·보호 협조 | IZ(S) ≥ max(IB, In, I2 ÷ 1.45) — IZ 는 표 B.52.2~5 × 보정계수(B.52.14~18) | KS C IEC 60364-5-52, KEC 212.4.1 |
| 전압강하 | 하류 부하마다 경로 Δu(이 배선 S, 나머지 배선 실제 규격) ≤ 허용치 | KEC 232.3.9 표 232.3-1, 부속서 G |
| 단락 열적 내량 | S ≥ Is,min·√tn / k | KEC 212.5.5의 2 식 212.5-1 |

실제 단면적이 없으면(기본설계 모드) 요구 단면적·후보만 내고 판정하지 않는다(N/A). 실제 단면적이 있으면 비교한다.
허용전류나 전압강하 조건을 계산할 입력이 없으면 UNKNOWN(필요 입력 목록) — 가정하지 않는다.
"""
from __future__ import annotations

import copy
import math
from typing import List, Optional, Tuple

from .engine import cable_vdrop, loads_under
from .model import Check, EResult, Evidence, Requirement
from .rules import RuleSet

# KS C IEC 60228 공칭 단면적 (㎟)
STANDARD_SIZES = (1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630)
N_CANDIDATES = 3


def sizing_checks(res: EResult, rules: RuleSet, kb, add) -> None:
    m = res.model
    for eid, e in m.edges.items():
        if e.type == "cable" and e.to_id in m.nodes and e.to_id in res.upstream:
            _size(res, rules, kb, eid, add)


def _first(pred) -> Optional[float]:
    return next((s for s in STANDARD_SIZES if pred(s)), None)


def _with_size(e, S):
    e2 = copy.copy(e)
    e2.installed = dict(e.installed, size=S)
    return e2


def _ampacity_condition(res, rules, kb, e, nr, IB) -> Tuple[Optional[float], List[str], List[str], dict]:
    """→ (S 최소, 누락, 추정, 값). IZ(S) ≥ max(IB, In, I2/1.45)."""
    from .judge import _table_ampacity
    m = res.model
    up = m.nodes.get(e.from_id)
    from .judge2 import setting_current
    In = setting_current(up) if up is not None and up.type in ("breaker", "rcd") else None
    need, vals = IB, {"IB(A)": round(IB, 1)}
    if In:
        std = up.installed.get("standard") or "IEC60898"
        i2 = rules.values("OVERLOAD_COORD")["I2_factor"].get(std, 1.45) * In
        need = max(need, In, i2 / 1.45)
        vals.update({"In(A)": In, "I2/1.45(A)": round(i2 / 1.45, 1)})
    vals["필요 IZ(A)"] = round(need, 1)
    reason = ""
    for S in STANDARD_SIZES:
        out = _table_ampacity(res, rules, _with_size(e, S), nr, kb)
        if out[0] is None:
            reason = out[1]
            if "표에 없는 조합" in reason:
                continue
            break
        if out[0] >= need:
            vals["IZ(S)(A)"] = round(out[0], 1)
            return S, [], list(out[2]), vals
    if e.installed.get("ampacity") and e.installed.get("size"):      # 입력 IZ 는 실제 단면적에만 유효
        if e.installed["ampacity"] >= need:
            return None, [], [f"입력 허용전류 {e.installed['ampacity']:g} A 로 실제 {e.installed['size']:g}㎟ 는 충족 — "
                              "더 작은 단면적은 공사방법·주변 온도·집합 조건이 있어야 산정"], vals
    if not reason:
        return None, ["표준 단면적 범위에서 허용전류 충족 불가 — 병렬(parallel) 검토"], [], vals
    return None, [f"허용전류 산정: {reason}"], [], vals


def _vd_path(res: EResult, load: str) -> List[str]:
    """부하에서 전원 쪽으로 — 전압강하가 누적되는 배선(변압기 2차에서 새로 시작)."""
    m, out, cur = res.model, [], load
    while cur is not None:
        eid = res.via_edge.get(cur)
        if eid:
            out.append(eid)
        cur = res.upstream.get(cur)
        if cur is not None and m.nodes[cur].type == "transformer":
            break
    return out


def _dv_at(res, rules, eid, nr, S) -> float:
    """이 배선 단면적을 S 로 바꿨을 때의 구간 전압강하 % (모델은 바꾸지 않는다)."""
    m = res.model
    e = m.edges[eid]
    saved = m.edges[eid]
    m.edges[eid] = _with_size(e, S)
    try:
        return cable_vdrop(m, eid, nr, res.levels, rules)[0]
    finally:
        m.edges[eid] = saved


def _vd_condition(res, rules, eid) -> Tuple[Optional[float], List[str], List[str], dict]:
    from .judge import vd_limit
    m = res.model
    e = m.edges[eid]
    if e.params.get("length") is None:
        return None, [f"{eid}: 길이"], [], {}
    s_need, missing, est, vals = 0.0, [], [], {}
    found = False
    for L in sorted(loads_under(m, res.children, e.to_id)):
        chk = next((c for c in res.checks if c.id == f"{L}:voltage_drop"), None)
        sid = chk.evidence.scenario if chk is not None and chk.evidence.scenario else res.design_scenario
        scn = res.scenarios.get(sid)
        if scn is None or L not in scn.on_loads:
            continue
        limit = vd_limit(res, rules, L, scn.nodes[L])
        if limit is None:
            missing.append(f"{L}: 용도(kind) — 전압강하 허용치")
            continue
        path = _vd_path(res, L)
        if eid not in path:
            continue
        other, ok = 0.0, True
        for e2 in path:
            if e2 == eid:
                continue
            dv, _, e_est, notes = cable_vdrop(m, e2, scn.nodes[m.edges[e2].to_id], res.levels, rules)
            if dv is None:
                missing += [f"{e2}: {x}" for x in notes]
                ok = False
                break
            other += dv
            if e_est:
                est.append(f"{e2}: 길이 추정")
        if not ok:
            continue
        nr = scn.nodes[e.to_id]
        if nr.current is None:
            missing.append(f"{L}: 부하 입력")
            continue
        found = True
        S = _first(lambda s: other + _dv_at(res, rules, eid, nr, s) <= limit)
        if (e.params.get("length_basis") or "estimate") == "estimate":
            est.append(f"{eid}: 길이 추정")
        if S is None:
            est.append(f"{L}: 경로의 다른 배선 강하 {other:.2f}% 만으로 허용 {limit:.2f}% 에 근접/초과 — "
                       "이 배선만으로는 충족 불가(다른 배선 규격·경로 검토)")
            continue
        if S > s_need:
            s_need = S
            vals = {f"전압강하 지배 부하 {L} 허용(%)": round(limit, 3), "경로의 다른 배선 강하(%)": round(other, 3)}
    if not found and not missing:
        return None, [], [], {}                        # 하류에 전압강하 대상 부하 없음
    return (s_need or None) if found else None, missing, sorted(set(est)), vals


def _thermal_condition(res, rules, e) -> Tuple[Optional[float], List[str], List[str], dict]:
    from .judge2 import _upstream_breaker
    m = res.model
    prot = e.from_id if m.nodes[e.from_id].type in ("breaker", "rcd") else _upstream_breaker(res, e.to_id)
    from .judge2 import trip_time
    tn = trip_time(m.nodes[prot]) if prot else None
    from .shortcircuit import ik_min_at_end
    mat, ins = e.installed.get("material"), e.installed.get("insulation")
    ok_sc = ik_min_at_end(res, rules, e.id, 1.5) is not None
    miss = [x for x, ok in (("보호 차단기 동작시간(trip_time)", tn), ("절연 종류", ins), ("재질", mat),
                            ("배선 시작점 단락 임피던스(전원 단락용량·상위 배선)", ok_sc)) if not ok]
    if miss or tn > rules.values("SC_THERMAL")["t_max"]:
        return None, miss or [f"동작시간 {tn:g}s > 5s — 식 212.5-1 범위 밖"], [], {}
    kv = rules.values("K_FACTOR")[mat]
    k = kv[ins] if ins in ("XLPE", "EPR") else kv["PVC"]
    # 배선 끝 최소 단락전류는 단면적에 따라 달라진다 — 후보마다 다시 구해 S ≥ Is,min(S)·√tn / k
    S = _first(lambda x: x >= ik_min_at_end(res, rules, e.id, x) * math.sqrt(tn) / k)
    note = []
    if tn < 0.1:
        note.append(f"동작시간 {tn:g}s < 0.1s — 한류형이면 제조사 통과 I²t 로 더 작아질 수 있음")
    if S is None:
        return None, ["표준 단면적 범위에서 열적 내량 충족 불가"], note, {}
    ik = ik_min_at_end(res, rules, e.id, S)
    return S, [], note, {"Is,min(A)": round(ik), "tn(s)": tn, "k": k, "S ≥ Is·√t/k(㎟)": round(ik * math.sqrt(tn) / k, 2)}


def _size(res: EResult, rules: RuleSet, kb, eid: str, add):
    from .judge import _worst
    m = res.model
    e = m.edges[eid]
    S_inst = e.installed.get("size")
    IB, nr, sid = _worst(res, lambda s: (res.scenarios[s].nodes[e.to_id].current, res.scenarios[s].nodes[e.to_id]))
    ev = Evidence(inputs=[eid, e.to_id], scenario=sid,
                  formula="요구 S = max(허용전류·보호협조, 전압강하, 단락 열적 내량 조건별 최소 표준 단면적)",
                  rule=rules.ref("AMPACITY_TABLE"), contributors=list(nr.contributors) if nr else [])
    c = Check(f"{eid}:cable_size", eid, "cable_size", "전선 규격 산정", "UNKNOWN", installed=S_inst, unit="mm²",
              evidence=ev)
    if IB is None:
        c.missing = ["하류 부하 입력"]
        add(c)
        return
    if e.installed.get("material") is None:
        c.missing = [f"{eid}: 재질(Cu/Al)"]
        add(c)
        return
    conds = {}
    for name, (S, miss, est, vals) in (("허용전류·보호협조", _ampacity_condition(res, rules, kb, e, nr, IB)),
                                       ("전압강하", _vd_condition(res, rules, eid)),
                                       ("단락 열적 내량", _thermal_condition(res, rules, e))):
        conds[name] = (S, miss)
        ev.values.update(vals)
        if S is not None:
            ev.values[f"{name} 최소(㎟)"] = S
        if name == "단락 열적 내량":
            ev.defaults += [f"열적 내량 미산정: {x}" for x in miss]
            ev.assumptions += [x for x in est if "한류형" not in x]
            ev.defaults += [x for x in est if "한류형" in x]
        else:
            c.missing += miss
            ev.assumptions += est
    known = {k: v[0] for k, v in conds.items() if v[0] is not None}
    if not known:
        add(c)
        return
    gov = max(known, key=known.get)
    s_req = known[gov]
    c.actual = s_req
    c.required = Requirement(f"단면적 (지배 조건: {gov})", "≥", s_req, "mm²")
    i = STANDARD_SIZES.index(s_req)
    for j, x in enumerate(STANDARD_SIZES[i:i + N_CANDIDATES]):
        ev.values[f"후보{j + 1}(㎟)"] = x
    if gov == "전압강하":
        ev.rule = rules.ref("VD_LIMIT")
    elif gov == "단락 열적 내량":
        ev.rule = rules.ref("SC_THERMAL")
    c.estimated = bool(ev.assumptions)
    amp_vd_unknown = any(conds[k][0] is None and conds[k][1] for k in ("허용전류·보호협조", "전압강하"))
    if S_inst is None:
        c.status = "UNKNOWN" if amp_vd_unknown else "N/A"
    else:
        c.utilization = s_req / S_inst
        if S_inst < s_req:
            c.status = "FAIL"
        elif amp_vd_unknown:
            c.status = "UNKNOWN"
        else:
            c.status = "REVIEW" if (c.estimated or conds["단락 열적 내량"][0] is None) else "PASS"
    add(c)
