"""전동기 기동 해석 (SPEC 5.6, TC-04) — 다른 부하는 판정 시나리오대로 운전, 대상 전동기만 기동.

기동 전압강하 (전기설비 검사·점검 기준 240절):  ε(%) = K·Ims·L(R cosθs + X sinθs) / V × 100
구간마다 전류 = (그 구간의 운전 전류 − 대상 전동기 운전 전류) + 기동전류 Ims∠−θs (복소 합) 로 놓고
  배선      Δu = b·L·(R·Ip + X·Iq) ÷ U0     (R = ρ1/S, X = λ — 부속서 G 와 같은 값)
  변압기    Δu% = I/IrT·(uR·cosφ + uX·sinφ)  (uk 가 있을 때)
  전원      Δu = I·(RQ cosφ + XQ sinφ)        (단락용량이 있을 때, c = 1)
를 전원부터 전동기 단자까지 더한다. 필수 입력이 없으면 None 과 누락 목록.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .model import EResult
from .rules import RuleSet

SQRT3 = math.sqrt(3.0)


def _path(res: EResult, nid: str) -> List[str]:
    p, cur = [], nid
    while cur is not None and cur not in p:
        p.append(cur)
        cur = res.upstream.get(cur)
    return list(reversed(p))


def start_current(rules: RuleSet, mo, i_rated: float):
    """기동전류 (검사·점검 기준 240.3.1) → (A 또는 None, 메모, 누락).

    전전압·Y-△·리액터: C × β × 정격 (C = 1.0 / 0.33 / Tap 값). 소프트스타터·인버터: 전류제한 비율 × 정격.
    """
    p = mo.params
    method = p.get("start_method") or "dol"
    v = rules.values("START_METHOD")
    notes = [] if p.get("start_method") else ["기동 방식 미입력 → 전전압 기동(기동전류 최대, 보수적)"]
    if method in ("soft_starter", "inverter"):
        lim = p.get("start_limit")
        if lim is None:
            lo, hi = v["limit_range"][method]
            return None, notes, [f"기동 전류제한 비율 start_limit ({method} 설정값 — 원문 참고 범위 {lo:g}∼{hi:g})"]
        return lim * i_rated, notes + [f"{method}: 기동전류 = 전류제한 비율 {lim:g} × 정격 {i_rated:.1f} A"], []
    beta = p.get("start_multiplier")
    if beta is None:
        return None, notes, ["기동전류 배수 β(start_multiplier)"]
    if method == "reactor":
        tap = p.get("start_tap")
        if tap is None:
            return None, notes, ["리액터 Tap 값(start_tap)"]
        C = tap
    else:
        C = v["C"][method]
    if method == "star_delta":
        notes.append("Y-△: Δ 전환 시 돌입전류는 별도(제조사·운전 조건) 확인")
    return C * beta * i_rated, notes + [f"기동전류 = C {C:g} × β {beta:g} × 정격 {i_rated:.1f} A"], []


def start_vdrop(res: EResult, rules: RuleSet, mid: str, scenario: Optional[str] = None):
    """→ (기동 전압강하 %, 기동전류 A, 메모, 누락)."""
    m = res.model
    mo = m.nodes[mid]
    sc = res.scenarios[scenario or res.design_scenario]
    pf_s = mo.params.get("start_pf")
    rated = res.scenarios["rated"].nodes[mid]
    missing = [x for x, ok in (("기동 시 역률(start_pf)", pf_s),
                               ("부하 입력", rated.current is not None and rated.S > 0)) if not ok]
    if missing:
        return None, None, [], missing
    v_m = res.levels[mid][0]
    i_rated = rated.current
    i_st, notes, miss = start_current(rules, mo, i_rated)
    if miss:
        return None, None, notes, miss
    ist_ph = i_st * complex(pf_s, -math.sqrt(1 - pf_s * pf_s))         # 지상 전류 (Iq 양수 = −Im)
    running = mid in sc.on_loads
    notes = notes + [f"기동전류 {i_st:.0f} A, cosθs {pf_s:g}"]
    rho1 = rules.values("RESISTIVITY_SERVICE")
    lam0 = rules.values("REACTANCE_DEFAULT")["x_ohm_per_m"]
    total = 0.0

    def seg_current(nid: str, V: float) -> complex:
        r = sc.nodes[nid]
        i = complex(r.P, -r.Q) / (SQRT3 * V)
        if running:
            mr = sc.nodes[mid]
            i -= complex(mr.P, -mr.Q) / (SQRT3 * V)
        return i + ist_ph * (v_m / V)

    for nid in _path(res, mid):
        n = m.nodes[nid]
        if n.type == "source":
            s_k, un = n.params.get("sc_mva"), n.params.get("voltage")
            if s_k and un and res.upstream.get(nid) is None:
                rx = n.params.get("rx") or 0.1
                z = un * un / s_k
                x = z / math.sqrt(1 + rx * rx)
                child = next((c for c in _path(res, mid)[1:2]), None)
                if child:
                    I = seg_current(child, un)
                    total += (I.real * rx * x + (-I.imag) * x) / (un / SQRT3) * 100
                    notes.append("전원 임피던스 강하 포함(단락용량 기준)")
            else:
                notes.append("전원 단락용량 미입력 → 전원 임피던스 강하 제외")
            continue
        if n.type == "transformer":
            sec, srt, uk = n.params.get("secondary"), n.installed.get("rated"), n.installed.get("uk")
            if not (sec and srt and uk):
                notes.append(f"{nid}: uk 등 미입력 → 변압기 강하 제외")
                continue
            ur = n.installed.get("ur") or 0.0
            ux = math.sqrt(max(uk * uk - ur * ur, 0.0))
            I = seg_current(nid, sec)
            irt = srt / (SQRT3 * sec)
            mag = abs(I)
            cos = I.real / mag if mag else 1.0
            sin = -I.imag / mag if mag else 0.0
            total += mag / irt * (ur * cos + ux * sin) * 100
            notes.append(f"{nid}: 변압기 강하 포함 (uk {uk * 100:g}%)")
            continue
        eid = res.via_edge.get(nid)
        if not eid:
            continue
        e = m.edges[eid]
        L, S, mat = e.params.get("length"), e.installed.get("size"), e.installed.get("material")
        if L is None or S is None or mat is None:
            return None, i_st, notes, [f"{eid}: 길이·단면적·재질"]
        V = res.levels[nid][0]
        par = int(e.installed.get("parallel") or 1)
        R = rho1[mat] / S / par
        X = (e.params.get("x") or lam0) / par
        I = seg_current(nid, V)
        total += L * (R * I.real + X * (-I.imag)) / (V / SQRT3) * 100
    return total, i_st, notes, []
