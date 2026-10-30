"""Phase 2 판정 (SPEC 5.6~5.11) — 단락 차단용량·열적 내량·보호협조·전동기 기동·누전·SPD.

판정 정책은 judge.py 와 같다: 입력 부족 → UNKNOWN(필요 입력), 추정 → 충족이어도 REVIEW,
미확인 규칙(verified=false) → 충족이어도 REVIEW·위반은 FAIL. 보호협조가 확인되지 않은 구간은 REVIEW(SPEC 5.8).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .model import Check, EResult, Evidence, Requirement
from .motorstart import start_vdrop
from .rules import RuleSet
from .shortcircuit import SCResult


def _upstream_breaker(res: EResult, nid: str) -> Optional[str]:
    """nid 에서 전원 쪽으로 가장 가까운 차단기·누전차단기 (자신 제외)."""
    cur = res.upstream.get(nid)
    while cur is not None:
        if res.model.nodes[cur].type in ("breaker", "rcd"):
            return cur
        cur = res.upstream.get(cur)
    return None


def trip_time(b) -> Optional[float]:
    """단락 시 동작시간 tn — trip_time, 없으면 단시간 지연 tsd(전자식)."""
    return b.installed.get("trip_time") or b.installed.get("short_time_delay")


def setting_current(b) -> Optional[float]:
    """과부하 보호 전류 — 전자식 장시간 설정이 있으면 Ir = ir_setting × In, 없으면 In."""
    In = b.installed.get("rated_current")
    r = b.installed.get("ir_setting")
    return In * r if (In and r) else In


def inst_band(rules: RuleSet, b) -> Optional[Tuple[float, float]]:
    """순시 트립 범위 (× In): 주택용 B/C/D 표 212.3-3, 산업용 instantaneous 설정."""
    if b.installed.get("instantaneous"):
        x = float(b.installed["instantaneous"])
        return x, x
    c = b.installed.get("curve")
    if c:
        lo, hi = rules.values("TRIP_INSTANTANEOUS")[c]
        return float(lo), float(hi)
    return None


def _sc_status(base: str, sc: SCResult, verified: bool = True) -> str:
    if base == "PASS" and (sc.assumptions or sc.unverified or not verified):
        return "REVIEW"
    return base


def phase2_checks(res: EResult, rules: RuleSet, scmap: Dict[str, SCResult], add) -> None:
    m = res.model
    sc_ref = rules.ref("SC_METHOD")
    for nid in res.order:
        n = m.nodes[nid]
        s = scmap.get(nid)
        # ---- 차단용량 (TC-07) -------------------------------------------------
        if n.type in ("breaker", "rcd"):
            icu = n.installed.get("breaking_capacity")
            ref = rules.ref("BREAKING_CAPACITY")
            ev = Evidence(inputs=[nid], formula="정격차단용량 ≥ 설치 점 최대 단락전류 Ik''max = cmax·Un/(√3·|Zk|) + 전동기 기여",
                          rule=ref, assumptions=list(s.assumptions) if s else [],
                          defaults=list(s.unverified) if s else [])
            c = Check(f"{nid}:breaking_capacity", nid, "breaking_capacity", "차단용량", "UNKNOWN", installed=icu,
                      unit="A", actual=s.ik_max if s else None, evidence=ev)
            if s is None or s.ik_max is None:
                c.missing = (s.missing if s else []) or ["단락전류 계산 입력"]
            else:
                c.required = Requirement("정격차단용량", "≥", s.ik_max, "A", ref.id)
                ev.values = {"Ik''max(A)": round(s.ik_max), "전동기 기여(A)": round(s.motor_contrib),
                             "Ik''min(A)": round(s.ik_min or 0)}
                if icu is None:
                    c.status = "N/A"
                else:
                    c.utilization = s.ik_max / icu
                    if s.ik_max > icu:
                        backup = _upstream_breaker(res, nid)
                        bk = m.nodes[backup].installed.get("breaking_capacity") if backup else None
                        if bk and bk >= s.ik_max:
                            c.status = "REVIEW"
                            ev.assumptions.append(f"전원 측 {backup} 차단용량 {bk / 1000:g} kA 로 후비보호 가능 — "
                                                  "양 장치 협조(제조사 캐스케이드 표) 확인 필요 (KEC 212.5.5 단서)")
                        else:
                            c.status = "FAIL"
                    else:
                        c.status = _sc_status("PASS", s)
                        ics = n.installed.get("ics")
                        if ics is not None and s.ik_max > ics:
                            c.status = "REVIEW"
                            ev.values["Ics(A)"] = ics
                            ev.assumptions.append(f"Ik''max {s.ik_max / 1000:.1f} kA > Ics {ics / 1000:g} kA — 차단은 가능(Icu)하나 "
                                                  "차단 후 계속 사용 성능(Ics)은 보장되지 않음")
            c.estimated = bool(ev.assumptions)
            add(c)
            _rated_voltage(res, nid, add)
            _selectivity(res, rules, scmap, nid, add)
            if n.type == "rcd" or n.installed.get("sensitivity"):
                _rcd_series(res, rules, nid, add)
            if n.type == "breaker":
                _sc_min_trip(res, rules, scmap, nid, add)
        # ---- 전동기 기동 (TC-04) ------------------------------------------------
        if n.type == "load" and n.params.get("kind") == "motor":
            _motor_start(res, rules, nid, add)
        # ---- 누전 추가 보호 ---------------------------------------------------------
        if n.type == "load" and n.params.get("kind") == "receptacle" and n.params.get("general_use") != "no":
            _rcd_socket(res, rules, nid, add)
    for eid, e in m.edges.items():
        if e.type == "cable" and e.to_id in m.nodes:
            _thermal(res, rules, scmap, eid, add)
    _spd(res, rules, add)


def protected_zone(res: EResult, bid: str) -> List[str]:
    """차단기 bid 가 보호하는 하류 설비 — 다음 차단기에서 멈춘다(그 차단기 설치 점까지는 포함)."""
    m, out, stack = res.model, [], list(res.children.get(bid, []))
    while stack:
        cur = stack.pop()
        if cur not in m.nodes or m.nodes[cur].type == "earth":
            continue
        out.append(cur)
        if m.nodes[cur].type != "breaker":
            stack.extend(res.children.get(cur, []))
    return out


def _sc_min_trip(res: EResult, rules: RuleSet, scmap, bid: str, add):
    """보호 구간 끝의 최소 단락전류에서 순시 동작하는가 (SPEC 5.7 '고장전류에 대한 보호장치 동작', 5.8 '차단 범위').

    Ik''min(구간 최소) ≥ 순시 상한 × In 이면 순시 영역 확정. 아니면 장한시 영역에서 동작하므로 열적 내량에 쓴
    동작시간(trip_time) 가정이 성립하지 않는다 → REVIEW(제조사 시간-전류 곡선으로 동작시간 확인).
    """
    m = res.model
    b = m.nodes[bid]
    In = b.installed.get("rated_current")
    band = inst_band(rules, b)
    zone = protected_zone(res, bid)
    ref = rules.ref("TRIP_INSTANTANEOUS")
    ev = Evidence(inputs=[bid] + zone, rule=ref,
                  formula="보호 구간 최소 단락전류 Ik''min ≥ 순시 트립 상한 × In (표 212.3-3) — 순시 영역 동작 확정")
    c = Check(f"{bid}:sc_min_trip", bid, "sc_min_trip", "최소 단락전류 순시 동작", "UNKNOWN", unit="A", evidence=ev)
    if not zone:
        return
    lacking = [z for z in zone if scmap.get(z) is None or scmap[z].ik_min is None]
    miss = [x for x, ok in ((f"{bid} 정격전류", In), (f"{bid} 순시 특성(curve 또는 instantaneous)", band)) if not ok]
    if lacking:
        miss.append("보호 구간 최소 단락전류: " + ", ".join(lacking[:4]) + " (전원 단락용량·배선 규격)")
    if miss:
        c.missing = miss
        add(c)
        return
    far = min(zone, key=lambda z: scmap[z].ik_min)
    ik = scmap[far].ik_min
    ia = band[1] * In
    c.actual, c.installed = ik, ia
    c.required = Requirement("보호 구간 최소 단락전류", "≥", ia, "A", ref.id)
    c.utilization = ia / ik if ik else None
    ev.values = {"Ik''min(A)": round(ik), "순시 상한(A)": round(ia), "In(A)": In}
    ev.inputs = [bid, far]
    ev.assumptions += scmap[far].assumptions
    ev.defaults += scmap[far].unverified
    cut = sorted(loads_under_zone(res, bid))
    ev.values["차단 범위 부하 수"] = len(cut)
    isd = b.installed.get("short_time")
    tsd = b.installed.get("short_time_delay")
    ir = setting_current(b)
    if ik >= ia:
        c.status = _sc_status("PASS", scmap[far])
    elif isd and tsd and ir and ik >= isd * ir:
        c.status = _sc_status("PASS", scmap[far])
        ev.values.update({"Isd(A)": round(isd * ir), "tsd(s)": tsd})
        c.required = Requirement("보호 구간 최소 단락전류 (단시간 영역)", "≥", isd * ir, "A", ref.id)
        c.installed = isd * ir
        ev.defaults.append(f"순시 영역 밖이지만 단시간 픽업 Isd {isd * ir:.0f} A 이상 — tsd {tsd:g}s 에 동작"
                           "(열적 내량은 이 시간으로 검토)")
    else:
        c.status = "REVIEW"
        ev.assumptions.append(f"{far} 의 최소 단락전류 {ik:.0f} A 가 순시 상한 {ia:.0f} A 아래 — 장한시 영역에서 동작하므로 "
                              "열적 내량의 동작시간(trip_time) 가정 대신 제조사 곡선의 실제 동작시간으로 재검토")
    c.estimated = bool(ev.assumptions)
    add(c)


def _rated_voltage(res: EResult, nid: str, add):
    """차단기·누전차단기 정격전압 Ue ≥ 설치 점 계통 선간전압 (정의)."""
    b = res.model.nodes[nid]
    ue = b.installed.get("rated_voltage")
    v = res.levels.get(nid, (None,))[0]
    if ue is None or not v:
        return
    add(Check(f"{nid}:rated_voltage", nid, "rated_voltage", "정격전압", "PASS" if ue >= v * (1 - 1e-6) else "FAIL",
              required=Requirement("정격전압 Ue", "≥", v, "V"), installed=ue, actual=v, unit="V",
              evidence=Evidence(inputs=[nid], formula="정격전압 Ue ≥ 설치 점 계통전압", values={"계통(V)": v, "Ue(V)": ue})))


def _rcd_series(res: EResult, rules: RuleSet, nid: str, add):
    """누전차단기 직렬 — 상위·하위 동작 형(시간)으로 선택성 근거를 보인다. 선택차단 요건 조항은 미확인 → REVIEW."""
    m = res.model
    cur = res.upstream.get(nid)
    up = None
    while cur is not None:
        n = m.nodes[cur]
        if n.type == "rcd" or (n.type == "breaker" and n.installed.get("sensitivity")):
            up = cur
            break
        cur = res.upstream.get(cur)
    if up is None:
        return
    ref = rules.ref("RCD_TYPES")
    t = rules.values("RCD_TYPES")
    d_type = m.nodes[nid].installed.get("rcd_type")
    u_type = m.nodes[up].installed.get("rcd_type")
    d_s, u_s = m.nodes[nid].installed.get("sensitivity"), m.nodes[up].installed.get("sensitivity")
    ev = Evidence(inputs=[up, nid], rule=ref, formula="상위 최소 동작시간 > 하위 최대 동작시간, IΔn 상위 > 하위")
    c = Check(f"{nid}:rcd_selectivity", nid, "rcd_selectivity", f"누전 선택성 (상위 {up})", "REVIEW", evidence=ev)
    if not (d_type and u_type):
        c.status = "UNKNOWN"
        c.missing = [f"{x} 동작 형(rcd_type)" for x, ok in ((up, u_type), (nid, d_type)) if not ok]
        add(c)
        return
    ev.values = {f"{up} 최소(s)": t["min_time"][u_type], f"{nid} 최대(s)": t["max_time"][d_type]}
    time_ok = t["min_time"][u_type] >= t["max_time"][d_type]
    sens_ok = (d_s is None or u_s is None) or u_s > d_s
    if not time_ok:
        ev.assumptions.append(f"상위 {up}({u_type}) 와 하위 {nid}({d_type}) 의 동작시간이 겹침 — 하위 누전에 상위도 동작할 수 있음")
    if not sens_ok:
        ev.assumptions.append(f"상위 감도 {u_s * 1000:g} mA ≤ 하위 {d_s * 1000:g} mA")
    if time_ok and sens_ok:
        ev.defaults.append("동작시간·감도가 나뉨 — 선택차단 요건 조항은 제공 자료에서 미확인이라 REVIEW")
    add(c)


def loads_under_zone(res: EResult, bid: str):
    """bid 가 끊으면 정전되는 부하 (차단 범위)."""
    from .engine import loads_under
    return loads_under(res.model, res.children, bid)


def _selectivity(res: EResult, rules: RuleSet, scmap, nid: str, add):
    """상위 차단기와의 선택차단 (SPEC 5.8): 정격 관계 + 하위 설치 점 최대 단락전류 < 상위 순시 하한."""
    m = res.model
    up = _upstream_breaker(res, nid)
    if up is None:
        return
    d, u = m.nodes[nid], m.nodes[up]
    in_d, in_u = d.installed.get("rated_current"), u.installed.get("rated_current")
    ref = rules.ref("TRIP_INSTANTANEOUS")
    s = scmap.get(nid)
    ev = Evidence(inputs=[up, nid], formula="In(상위) > In(하위), 하위 설치 점 Ik''max < 상위 순시 트립 하한 × In(상위)",
                  rule=ref)
    c = Check(f"{nid}:selectivity", nid, "selectivity", f"보호협조 (상위 {up})", "UNKNOWN", unit="A", evidence=ev)
    band = inst_band(rules, u)
    miss = [x for x, ok in ((f"{up}·{nid} 정격전류", in_d and in_u),
                            (f"{up} 순시 특성(curve 또는 instantaneous)", band),
                            ("단락전류", s is not None and s.ik_max is not None)) if not ok]
    if miss:
        c.missing = miss
        add(c)
        return
    lo = band[0] * in_u
    c.actual, c.installed = s.ik_max, lo
    c.required = Requirement(f"{up} 순시 트립 하한", ">", s.ik_max, "A", ref.id)
    ev.values = {"In 상위(A)": in_u, "In 하위(A)": in_d, f"{up} 순시 하한(A)": round(lo), "Ik''max 하위(A)": round(s.ik_max)}
    if in_u <= in_d:
        c.status = "REVIEW"
        ev.assumptions.append(f"상위 {up} 정격 {in_u:g} A ≤ 하위 {in_d:g} A — 과부하 영역 선택차단 불가 가능성")
    elif s.ik_max >= lo:
        c.status = "REVIEW"
        ev.assumptions.append("단락 영역에서 상위도 순시 트립 범위 — 선택차단은 제조사 선택차단표로 확인")
    else:
        c.status = _sc_status("PASS", s)
    add(c)


def _thermal(res: EResult, rules: RuleSet, scmap, eid: str, add):
    """도체 열적 내량 (KEC 212.5.5의 2, 식 212.5-1): S ≥ Is,min·√tn / k (권장 × α 1.25)."""
    m = res.model
    e = m.edges[eid]
    prot = e.from_id if m.nodes[e.from_id].type in ("breaker", "rcd") else _upstream_breaker(res, e.to_id)
    s = scmap.get(e.to_id)
    ref = rules.ref("SC_THERMAL")
    kv = rules.values("K_FACTOR")
    S, mat, ins = e.installed.get("size"), e.installed.get("material"), e.installed.get("insulation")
    tn = trip_time(m.nodes[prot]) if prot else None
    ev = Evidence(inputs=[eid] + ([prot] if prot else []), formula="t = (k·S / I)² (식 212.5-1) → S ≥ Is,min·√tn / k",
                  rule=ref)
    if prot and tn is not None and m.nodes[prot].installed.get("trip_time") is None:
        ev.assumptions.append(f"{prot}: 단락 동작시간 미입력 → 단시간 지연 tsd {tn:g}s 를 동작시간으로")
    c = Check(f"{eid}:thermal", eid, "thermal", "단락 열적 내량", "UNKNOWN", installed=S, unit="mm²", evidence=ev)
    miss = [x for x, ok in (("보호 차단기(전원 측 차단기 없음)", prot), (f"{prot or '보호 차단기'} 단락 시 동작시간(trip_time)", tn),
                            ("재질·절연·단면적", S and mat and ins), ("최소 단락전류", s is not None and s.ik_min))
            if not ok]
    if miss:
        c.missing = miss
        add(c)
        return
    key = ins if ins in ("XLPE", "EPR") else ("PVC_gt300" if S > 300 else "PVC")
    k = kv[mat][key]
    if tn > rules.values("SC_THERMAL")["t_max"]:
        c.missing = [f"동작시간 {tn:g}s > 5s — 식 212.5-1 적용 범위 밖"]
        add(c)
        return
    s_req = s.ik_min * math.sqrt(tn) / k
    alpha = rules.values("SC_THERMAL")["alpha"]
    c.actual = s_req
    c.required = Requirement("도체 단면적", "≥", s_req, "mm²", ref.id)
    c.utilization = s_req / S
    ev.values = {"Is,min(A)": round(s.ik_min), "tn(s)": tn, "k": k, "S 요구(㎟)": round(s_req, 2),
                 "S 권장 ×1.25(㎟)": round(s_req * alpha, 2)}
    ev.defaults += s.unverified
    ev.assumptions += s.assumptions
    i2t = m.nodes[prot].installed.get("let_through_i2t")
    if i2t is not None:
        ev.values["k²S²(A²s)"] = round(k * k * S * S)
        ev.values["통과 I²t(A²s)"] = i2t
        c.status = "PASS" if k * k * S * S >= i2t else "FAIL"
        ev.assumptions += []
    elif S < s_req and tn < 0.1:
        c.status = "REVIEW"
        ev.assumptions.append(f"동작시간 {tn:g}s < 0.1s — 한류형 차단기는 실제 통과 에너지가 I²·t 보다 작으므로 "
                              f"제조사 통과 I²t 로 확인 (k²S² = {k * k * S * S:.0f} A²s, let_through_i2t)")
    elif S < s_req:
        c.status = "FAIL"
    elif S < s_req * alpha:
        c.status = "REVIEW"
        ev.assumptions.append(f"설계여유 α {alpha:g} 권장값({s_req * alpha:.1f}㎟) 미달")
    else:
        c.status = _sc_status("PASS", s)
    c.estimated = bool(ev.assumptions)
    if i2t is not None and c.status == "PASS":
        c.status = _sc_status("PASS", s)
    add(c)


def _motor_start(res: EResult, rules: RuleSet, mid: str, add):
    m = res.model
    n = m.nodes[mid]
    vd, i_st, notes, missing = start_vdrop(res, rules, mid)
    ref = rules.ref("MOTOR_START_VD")
    lim = m.settings.get("motor_start_vd_limit")
    ev = Evidence(inputs=[mid], formula="ε(%) = K·Ims·L(R cosθs + X sinθs)/V × 100 (다른 부하 운전 + 대상 기동)",
                  rule=ref, scenario=res.design_scenario, defaults=notes)
    c = Check(f"{mid}:motor_start_vd", mid, "motor_start_vd", "기동 시 전압강하", "UNKNOWN", unit="%", actual=vd,
              evidence=ev)
    if missing:
        c.missing = missing
    elif lim is None:
        c.status = "REVIEW"
        c.missing = []
        ev.assumptions.append("기동 중 허용 전압강하 수치 기준 없음(KEC 232.3.9의 2) — system motor_start_vd_limit 로 지정")
    else:
        c.required = Requirement("기동 시 전압강하", "≤", lim * 100, "%")
        c.status = "FAIL" if vd > lim * 100 else "PASS"
    add(c)
    # 보호장치: 순시 트립 범위 · 기동 시간 동안의 동작배율
    b = _upstream_breaker(res, mid)
    pr = rules.ref("MOTOR_START_PROTECTION")
    ev2 = Evidence(inputs=[mid] + ([b] if b else []),
                   formula="Ims < 순시 하한 × In, Ims/In < δ(tb = 1.5·tm 에서의 제조사 동작배율)", rule=pr)
    c2 = Check(f"{mid}:motor_start_protection", mid, "motor_start_protection", "기동 시 차단기 동작", "UNKNOWN",
               unit="A", actual=i_st, evidence=ev2)
    tm = n.params.get("start_time")
    if b is None or i_st is None or not m.nodes[b].installed.get("rated_current") or tm is None:
        c2.missing = [x for x, ok in (("보호 차단기", b), ("기동전류(β·정격)", i_st),
                                      ("차단기 정격전류", b and m.nodes[b].installed.get("rated_current")),
                                      ("기동시간 tm", tm)) if not ok]
        add(c2)
        return
    bn = m.nodes[b]
    In = bn.installed["rated_current"]
    mult = i_st / In
    band = inst_band(rules, bn)
    tb = rules.values("MOTOR_START_PROTECTION")["tb_over_tm"] * tm
    ev2.values = {"Ims(A)": round(i_st), "In(A)": In, "Ims/In": round(mult, 2), "tb(s)": round(tb, 2)}
    status = "PASS"
    reasons = []
    if band is None:
        status = "UNKNOWN"
        c2.missing = [f"{b} 순시 특성(curve 또는 instantaneous)"]
    elif mult >= band[1]:
        status = "FAIL"
        reasons.append(f"기동전류 {mult:.1f} In ≥ 순시 상한 {band[1]:g} In — 기동 순간 트립")
    elif mult > band[0]:
        status = "REVIEW"
        reasons.append(f"기동전류 {mult:.1f} In 이 순시 범위 {band[0]:g}~{band[1]:g} In 안 — 트립할 수 있음")
    delta = bn.installed.get("start_trip_multiple")
    if delta is None:
        if status == "PASS":
            status = "REVIEW"
        reasons.append(f"tb {tb:g}s 에서의 동작배율 δ(제조사 곡선) 미입력 — 장시간 영역 트립 여부 확인")
    elif mult >= delta:
        status = "FAIL"
        reasons.append(f"기동전류 {mult:.1f} In ≥ δ {delta:g} — 기동 중 장시간 영역 트립")
    c2.status = status
    c2.required = Requirement("기동전류 배수 Ims/In", "<", min([x for x in (band[0] if band else None, delta) if x]
                                                              or [mult]), "", pr.id)
    ev2.assumptions += reasons
    add(c2)


def _rcd_socket(res: EResult, rules: RuleSet, nid: str, add):
    m = res.model
    n = m.nodes[nid]
    ref = rules.ref("RCD_SOCKET")
    lim = rules.values("RCD_SOCKET")["socket_max_a"]
    rating = n.params.get("socket_rating")
    b = _upstream_breaker(res, nid)
    if rating is None and b:
        rating = m.nodes[b].installed.get("rated_current")
    ev = Evidence(inputs=[nid] + ([b] if b else []), formula="일반인 사용 20 A 이하 콘센트 → 누전차단기 추가적 보호",
                  rule=ref)
    c = Check(f"{nid}:rcd_socket", nid, "rcd_socket", "누전차단기 추가적 보호", "UNKNOWN", unit="mA", evidence=ev)
    if rating is None:
        c.missing = ["콘센트 정격(socket_rating) 또는 보호 차단기 정격"]
        add(c)
        return
    if rating > lim:
        c.status = "N/A"
        c.explanation = f"{rating:g} A 콘센트 — 20 A 이하 일반 콘센트 대상 아님"
        add(c)
        return
    rcd, sens, cur = None, None, nid
    while cur is not None:
        cn = m.nodes[cur]
        if cn.type == "rcd" or (cn.type == "breaker" and cn.installed.get("sensitivity")):
            rcd, sens = cur, cn.installed.get("sensitivity")
            break
        cur = res.upstream.get(cur)
    sref = rules.ref("RCD_SENSITIVITY")
    smax = rules.values("RCD_SENSITIVITY")["max_ma"] / 1000.0
    c.required = Requirement("누전 감도 IΔn", "≤", smax * 1000, "mA", sref.id)
    if rcd is None:
        c.status = "FAIL"
        ev.assumptions.append("전원 측 경로에 누전차단기(rcd 또는 sensitivity 가 있는 차단기) 없음")
    elif sens is None:
        c.status = "UNKNOWN"
        c.missing = [f"{rcd} 정격감도전류(sensitivity)"]
    else:
        c.installed = c.actual = sens * 1000
        ev.inputs.append(rcd)
        c.status = "FAIL" if sens > smax else ("PASS" if sref.verified else "REVIEW")
    add(c)


def _spd(res: EResult, rules: RuleSet, add):
    m = res.model
    ref = rules.ref("SPD_SELECTION")
    spds = [n for n in m.nodes.values() if n.type == "spd"]
    src = next((n for n in m.nodes.values() if n.type == "source"), None)
    if src is None:
        return
    if not spds:
        c = Check(f"{src.id}:spd", src.id, "spd", "서지보호장치", "REVIEW",
                  evidence=Evidence(inputs=[src.id], formula="서지가 유입되는 선로 → SPD 설치 (KEC 153.1.4)", rule=ref))
        c.missing = []
        add(c)
        return
    for n in spds:
        c = Check(f"{n.id}:spd", n.id, "spd", "서지보호장치 선정", "REVIEW",
                  evidence=Evidence(inputs=[n.id], formula="KS C IEC 61643-12 · 60364-5-53 에 따른 선정", rule=ref,
                                    values={k: v for k, v in (("Uc(V)", n.installed.get("uc")),
                                                              ("Up(V)", n.installed.get("up"))) if v}))
        add(c)
