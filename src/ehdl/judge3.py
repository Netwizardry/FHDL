"""Phase 3 판정 (SPEC 5.10·5.12) — 접지계통·고장보호(전원 자동차단)·보호도체·등전위본딩·수전 종합.

고장루프임피던스 (TN, KEC 211.2.5의 6):  Zs = 전원(변압기) + 고장점까지 선도체 + 보호도체,  Zs × Ia ≤ U0
  변압기: 지락 루프 ≈ ZT (Dyn 결선, 영상 ≈ 정상 가정 — 추정), 전원 측: Un²/S''k 환산(c = 1)
  배선: (ρ1·L/S + ρ1·L/S_PE) + j·λ·L    (ρ1 = 통상 사용 온도 저항률, 부속서 G)
  Ia: 누전차단기면 IΔn, 차단기면 순시 트립 상한 × In (표 212.3-3 B 5·C 10·D 20 In, 산업용 instantaneous) —
      순시 영역은 의도적 지연 없이 동작하므로 표 211.2-1 차단시간 안에 든다고 본다.
TT (211.2.6): 누전차단기 RA × IΔn ≤ 50 V. 누전차단기 없이 과전류보호장치면 Zs(RA + RB + 선로) × Ia ≤ U0.
IT (211.2.7): 1차 고장 RA × Id ≤ 50 V(교류), 절연감시장치.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .judge2 import _upstream_breaker, inst_band
from .model import Check, EResult, Evidence, Requirement
from .rules import RuleSet

SQRT3 = math.sqrt(3.0)


def pe_min(rules: RuleSet, s: float) -> float:
    """표 142.3-1: S ≤ 16 → S, 16 < S ≤ 35 → 16, S > 35 → S/2."""
    return s if s <= 16 else (16.0 if s <= 35 else s / 2.0)


def _path(res: EResult, nid: str) -> List[str]:
    p, cur = [], nid
    while cur is not None and cur not in p:
        p.append(cur)
        cur = res.upstream.get(cur)
    return list(reversed(p))


def _rcd_in_path(res: EResult, nid: str) -> Tuple[Optional[str], Optional[float]]:
    cur = nid
    while cur is not None:
        n = res.model.nodes[cur]
        if n.type == "rcd" or (n.type == "breaker" and n.installed.get("sensitivity")):
            return cur, n.installed.get("sensitivity")
        cur = res.upstream.get(cur)
    return None, None


def fault_loop(res: EResult, rules: RuleSet, nid: str):
    """→ (Zs 복소 Ω 또는 None, 추정 메모, 누락). 변압기 2차(또는 저압 전원)부터 nid 까지."""
    m = res.model
    rho1 = rules.values("RESISTIVITY_SERVICE")
    lam0 = rules.values("REACTANCE_DEFAULT")["x_ohm_per_m"]
    notes, missing = [], []
    z = 0j
    started = False
    for p in _path(res, nid):
        n = m.nodes[p]
        if n.type == "source":
            un, sk = n.params.get("voltage"), n.params.get("sc_mva")
            if un and un <= 1000:
                if not sk:
                    missing.append(f"{p}: 전원 단락용량(sc_mva) — 저압 수전 전원 임피던스")
                    return None, notes, missing
                z += complex(0.1, 1.0) / math.sqrt(1.01) * un * un / sk
                started = True
            continue
        if n.type == "transformer":
            sec, srt, uk = n.params.get("secondary"), n.installed.get("rated"), n.installed.get("uk")
            if not (sec and srt and uk):
                missing.append(f"{p}: 변압기 정격·uk")
                return None, notes, missing
            ur = n.installed.get("ur") or 0.0
            zb = sec * sec / srt
            z = complex(ur * zb, math.sqrt(max(uk * uk - ur * ur, 0.0)) * zb)
            notes.append(f"{p}: 지락 루프 변압기 임피던스 ≈ ZT (Dyn, 영상 ≈ 정상 가정)")
            started = True
            continue
        eid = res.via_edge.get(p)
        if not eid or not started:
            continue
        e = m.edges[eid]
        L, S, mat = e.params.get("length"), e.installed.get("size"), e.installed.get("material")
        if L is None or S is None or mat is None:
            missing.append(f"{eid}: 길이·단면적·재질")
            return None, notes, missing
        par = int(e.installed.get("parallel") or 1)
        spe = e.installed.get("pe_size")
        if spe is None:
            spe = pe_min(rules, S)
            notes.append(f"{eid}: PE 단면적 미입력 → 표 142.3-1 최소 {spe:g}㎟ 가정")
        r = rho1[mat] * L / S / par + rho1[mat] * L / spe
        x = (e.params.get("x") or lam0) * L / par
        z += complex(r, x)
    if not started:
        missing.append("전원 측 임피던스")
        return None, notes, missing
    return z, notes, missing


def phase3_checks(res: EResult, rules: RuleSet, add) -> None:
    m = res.model
    sysp = m.settings
    earthing = sysp.get("earthing")
    rcds = [n.id for n in m.nodes.values()
            if n.type == "rcd" or (n.type == "breaker" and n.installed.get("sensitivity"))]
    if earthing == "TN-C" and rcds:
        ref = rules.ref("TNC_NO_RCD")
        for rid in rcds:
            add(Check(f"{rid}:tnc_rcd", rid, "tnc_rcd", "TN-C 계통 누전차단기", "FAIL",
                      evidence=Evidence(inputs=[rid], formula="TN-C 계통에는 누전차단기 사용 금지", rule=ref)))
    if earthing == "IT":
        _it(res, rules, add)
    for n in m.loads():
        if n.id in res.upstream:
            _fault_protection(res, rules, n.id, earthing, add)
    for eid, e in m.edges.items():
        if e.type == "cable" and e.installed.get("size"):
            _pe_size(res, rules, eid, add)
    _bonding(res, rules, earthing, add)
    _supply(res, rules, add)


def _disconnect_time(rules: RuleSet, system: str, u0: float, final: bool) -> float:
    v = rules.values("DISCONNECT_TIME")
    key = "TT" if system == "TT" else "TN"
    if not final:
        return v["distribution"][key]
    for lim, t in v["final"][key]:
        if u0 <= lim:
            return t
    return v["final"][key][-1][1]


def _fault_protection(res: EResult, rules: RuleSet, nid: str, earthing, add):
    m = res.model
    v_ll = res.levels.get(nid, (None,))[0]
    ev = Evidence(inputs=[nid])
    c = Check(f"{nid}:fault_protection", nid, "fault_protection", "고장보호(전원 자동차단)", "UNKNOWN", unit="A",
              evidence=ev)
    if not earthing:
        c.missing = ["계통접지 방식(system earthing = TN-S / TN-C / TN-C-S / TT / IT)"]
        add(c)
        return
    if earthing == "IT" or not v_ll:
        return
    u0 = v_ll / SQRT3
    via = res.via_edge.get(nid)
    final = (m.edges[via].params.get("circuit") or "final") == "final" if via else True
    prot = _upstream_breaker(res, nid)
    in_prot = m.nodes[prot].installed.get("rated_current") if prot else None
    if final and in_prot is not None and in_prot > 32:
        final = False                      # 표 211.2-1 은 32 A 이하 분기회로 — 그 밖은 TN 5 s / TT 1 s (211.2.3의 3)
    t_req = _disconnect_time(rules, earthing, u0, final)
    ev.values = {"U0(V)": round(u0, 1), "허용 차단시간(s)": t_req}
    rcd, sens = _rcd_in_path(res, nid)
    if earthing == "TT":
        ref = rules.ref("ADS_TT")
        ev.rule = ref
        ra = m.settings.get("ra")
        if rcd:
            ev.formula = "RA × IΔn ≤ 50 V (211.2.6의 3)"
            ev.inputs.append(rcd)
            if ra is None or sens is None:
                c.missing = [x for x, ok in (("RA(system ra)", ra is not None), (f"{rcd} 감도", sens)) if not ok]
            else:
                c.unit, c.actual = "V", ra * sens
                c.required = Requirement("RA × IΔn", "≤", 50.0, "V", ref.id)
                c.status = "PASS" if ra * sens <= 50.0 else "FAIL"
            add(c)
            return
        ev.formula = "누전차단기 없음 → 과전류보호장치: Zs(RA + RB + 선로) × Ia ≤ U0 (211.2.6의 4)"
        rb = m.settings.get("rb")
        if ra is None or rb is None:
            c.missing = ["TT 계통은 누전차단기로 고장보호(211.2.6의 2)", "또는 RA·RB(접지저항)"]
            add(c)
            return
    else:
        ref = rules.ref("ADS_TN")
        ev.rule = ref
        ev.formula = "Zs × Ia ≤ U0 (211.2.5의 6), Zs = 전원 + 선도체 + 보호도체"
    zs, notes, missing = fault_loop(res, rules, nid)
    ev.assumptions += notes
    if earthing == "TT" and zs is not None:
        zs += complex(m.settings["ra"] + m.settings["rb"], 0.0)
    if rcd and earthing != "TT":
        ia, dev = sens, rcd
        if ia is None:
            missing.append(f"{rcd} 감도")
    else:
        dev = _upstream_breaker(res, nid)
        band = inst_band(rules, m.nodes[dev]) if dev else None
        In = m.nodes[dev].installed.get("rated_current") if dev else None
        ia = band[1] * In if (band and In) else None
        if ia is None:
            missing.append(f"{dev or '보호 차단기'}: 정격·순시 특성(curve 또는 instantaneous)")
    if missing or zs is None:
        c.missing = missing
        add(c)
        return
    ev.inputs.append(dev)
    i_f = u0 / abs(zs)
    c.actual, c.installed = i_f, ia
    c.required = Requirement(f"고장전류 U0/Zs (Ia, {dev})", "≥", ia, "A", ref.id)
    ev.values.update({"Zs(Ω)": round(abs(zs), 4), "If = U0/Zs(A)": round(i_f), "Ia(A)": round(ia, 1),
                      "Zs 허용 U0/Ia(Ω)": round(u0 / ia, 4)})
    c.estimated = bool(ev.assumptions)
    if i_f < ia and t_req >= 1.0 and not (rcd and earthing != "TT"):
        c.status = "REVIEW"                # 순시 영역 밖 — 허용 시간(1~5 s) 안 동작은 제조사 시간-전류 곡선으로 확인
        ev.assumptions.append(f"고장전류 {i_f:.0f} A 가 순시 영역({ia:.0f} A) 아래 — 허용 {t_req:g}초 안 동작 여부는 "
                              "제조사 시간-전류 곡선으로 확인")
    else:
        c.status = "FAIL" if i_f < ia else ("REVIEW" if c.estimated else "PASS")
    add(c)


def _it(res: EResult, rules: RuleSet, add):
    m = res.model
    src = next((n for n in m.nodes.values() if n.type == "source"), None)
    ref = rules.ref("ADS_IT")
    ra, idf = m.settings.get("ra"), m.settings.get("id_first_fault")
    c = Check(f"{src.id}:it_first_fault", src.id, "it_first_fault", "IT 계통 1차 고장", "UNKNOWN", unit="V",
              evidence=Evidence(inputs=[src.id], formula="RA × Id ≤ 50 V (교류, 211.2.7의 2)", rule=ref))
    if ra is None or idf is None:
        c.missing = [x for x, ok in (("RA(system ra)", ra is not None), ("1차 고장전류 Id(system id_first_fault)", idf))
                     if not ok]
    else:
        c.actual = ra * idf
        c.required = Requirement("RA × Id", "≤", 50.0, "V", ref.id)
        c.status = "FAIL" if c.actual > 50 else ("PASS" if m.settings.get("insulation_monitor") == "yes" else "REVIEW")
        if c.status == "REVIEW":
            c.evidence.assumptions.append("절연감시장치(insulation_monitor) 미확인 — 1차 고장 지속 시 알림 필요 (211.2.7의 3)")
    add(c)


def _pe_size(res: EResult, rules: RuleSet, eid: str, add):
    e = res.model.edges[eid]
    ref = rules.ref("PE_MIN_SIZE")
    S = e.installed["size"]
    req = pe_min(rules, S)
    sep = e.installed.get("pe_separate") == "yes"
    if sep:
        req = max(req, rules.values("PE_MIN_SIZE")["separate_cu_unprotected" if (e.installed.get("material") or "Cu") == "Cu"
                                                    else "separate_al"])
    spe = e.installed.get("pe_size")
    c = Check(f"{eid}:pe_size", eid, "pe_size", "보호도체 단면적", "N/A" if spe is None else "PASS", installed=spe,
              unit="mm²", actual=spe, required=Requirement("보호도체 단면적", "≥", req, "mm²", ref.id),
              evidence=Evidence(inputs=[eid], formula="표 142.3-1: S ≤ 16 → S, ≤ 35 → 16, > 35 → S/2", rule=ref,
                                values={"선도체(㎟)": S, "PE 최소(㎟)": req}))
    if spe is not None and spe < req:
        c.status = "FAIL"
    if spe is not None:
        c.utilization = req / spe
    add(c)


def _bonding(res: EResult, rules: RuleSet, earthing, add):
    m = res.model
    ref = rules.ref("BONDING_MAIN")
    v = rules.values("BONDING_MAIN")
    mains = [e for e in m.edges.values() if e.type == "bond" and e.params.get("kind") == "main"]
    pes = [e.installed.get("pe_size") or pe_min(rules, e.installed["size"]) for e in m.edges.values()
           if e.type == "cable" and e.installed.get("size")]
    biggest = max(pes, default=0.0)
    if earthing and not mains:
        src = next((n for n in m.nodes.values() if n.type == "source"), None)
        add(Check(f"{src.id}:main_bonding", src.id, "main_bonding", "주 보호등전위본딩", "REVIEW",
                  evidence=Evidence(inputs=[src.id], formula="건축물 인입 도전부 → 주접지단자 보호등전위본딩 (KEC 143.2)",
                                    rule=ref)))
    for e in mains:
        mat = e.installed.get("material") or "Cu"
        req = max(v["min"][mat], biggest / 2.0)
        if mat == "Cu":
            req = min(req, v["cap_cu"])
        size = e.installed.get("size")
        c = Check(f"{e.id}:bonding", e.id, "bonding", "보호등전위본딩 도체", "UNKNOWN" if size is None else
                  ("PASS" if size >= req else "FAIL"), installed=size, actual=size, unit="mm²",
                  required=Requirement("본딩 도체 단면적", "≥", req, "mm²", ref.id),
                  evidence=Evidence(inputs=[e.id], formula="≥ 가장 큰 보호접지도체 × 1/2, 최소 Cu 6·Al 16·강 50 ㎟ (Cu 25 ㎟ 초과 불요)",
                                    rule=ref, values={"가장 큰 PE(㎟)": biggest}))
        if size is None:
            c.missing = [f"{e.id}: 단면적"]
        add(c)


def _supply(res: EResult, rules: RuleSet, add):
    """수전 종합 (SPEC 5.12): 설비용량·최대수요전력·계약전력·변압기 정격을 따로 보여 주고 비교."""
    m = res.model
    src = next((n for n in m.nodes.values() if n.type == "source"), None)
    if src is None:
        return
    rated = res.scenarios["rated"].nodes[src.id]
    sid = res.design_scenario
    worst = max((res.scenarios[s] for s in res.scenarios if s != "rated"), key=lambda s: s.nodes[src.id].P)
    dem = worst.nodes[src.id]
    ev = Evidence(inputs=[src.id], formula="수용률 = 최대수요전력 ÷ 설비용량 (검사·점검 기준 230.4.3)",
                  rule=rules.ref("TX_CAPACITY"), scenario=worst.scenario.id,
                  values={"설비용량 합계(kVA)": round(rated.S / 1000, 1), "설비용량 합계(kW)": round(rated.P / 1000, 1),
                          "최대수요전력(kW)": round(dem.P / 1000, 1), "최대수요전력(kVA)": round(dem.S / 1000, 1),
                          "수용률(계산)": round(dem.P / rated.P, 3) if rated.P else 0.0})
    tx = [n for n in m.nodes.values() if n.type == "transformer" and n.installed.get("rated")]
    for t in tx:
        ev.values[f"{t.id} 정격(kVA)"] = t.installed["rated"] / 1000
    # 반별 수용률(사용자 입력) + 부등률 → 식 230-6
    panels = [n for n in m.nodes.values() if n.type in ("switchboard", "panel") and n.params.get("demand_factor")]
    if panels:
        tot = sum(res.scenarios["rated"].nodes[p.id].S * p.params["demand_factor"] for p in panels)
        div = m.settings.get("diversity") or 1.0
        alpha = m.settings.get("capacity_margin") or 1.0
        ev.values["식 230-6 변압기 용량(kVA)"] = round(tot / div * alpha / 1000, 1)
        if not m.settings.get("diversity"):
            ev.assumptions.append("부등률 미입력 → 1.0")
    c = Check(f"{src.id}:supply_summary", src.id, "supply_summary", "수전 종합 (설비용량·최대수요·계약·변압기)", "PASS",
              unit="W", actual=dem.P, evidence=ev)
    contract = m.settings.get("contract_kw")
    if contract is not None:
        cref = rules.ref("CONTRACT_POWER")
        c.installed = contract
        c.required = Requirement("계약전력", "≥", dem.P, "W", cref.id)
        c.utilization = dem.P / contract
        ev.values["계약전력(kW)"] = contract / 1000
        c.status = "FAIL" if dem.P > contract else ("PASS" if cref.verified else "REVIEW")
    elif panels and tx and ev.values["식 230-6 변압기 용량(kVA)"] * 1000 > tx[0].installed["rated"]:
        c.status = "FAIL"
    add(c)
