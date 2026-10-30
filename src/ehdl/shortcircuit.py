"""단락전류 계산 (SPEC 5.7) — 전기설비 검사·점검 기준 220.1.2 (KS C IEC 60909-0) 의 최대·최소 조건.

  Ik'' = c·Un / (√3·|Zk|)      (3상 대칭 초기 단락전류, 원격 고장 가정)

임피던스(상당, Ω)는 전원에서 각 노드까지 누적하고 변압기를 지나면 2차 전압 기준으로 환산한다.
  전원      ZQ = c·Un² / S''kQ (한전 제공 단락용량), XQ = ZQ/√(1+(R/X)²), RQ = (R/X)·XQ
  변압기    ZT = uk·UrT²/SrT, RT = ur·UrT²/SrT, XT = √(ZT²−RT²); 최대 조건은 × KT (IEC 60909, 미확인 규칙)
  배선      R = ρ·L/S (최대: 20℃ — ρ20 = ρ1/1.25, 최소: 단락 온도한계 표 220-4), X = λ·L
조건 (220.1.2):
  최대  cmax(표 220-3), 최소 등가 전원 임피던스(sc_mva), 전동기 기여 포함, 선로 20℃
  최소  cmin, 최대 등가 전원 임피던스(sc_mva_min), 전동기 기여 무시, 선로 단락 온도한계
전동기 기여(최대): 같은 저압 모선(변압기 2차) 아래 운전 전동기를 모선에 모은 등가 임피던스 cmax·Un/(√3·Σβ·IrM)
로 계통과 병렬로 두고(테브난), 모선 → 고장점 임피던스를 더한다(전동기 ~ 모선 배선 무시 → 보수적).
β 미입력 전동기는 기여를 넣을 수 없어 결과가 '추정'이 된다.
필수 입력(전원 단락용량, 변압기 uk)이 없으면 그 하류는 계산하지 않는다(SPEC 5.7 — 확정값으로 표시 금지).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .model import EResult
from .rules import RuleSet

SQRT3 = math.sqrt(3.0)


@dataclass
class SCResult:
    node: str
    voltage: Optional[float] = None          # 그 노드의 공칭 선간전압
    ik_max: Optional[float] = None           # A
    ik_min: Optional[float] = None
    z_max: Optional[complex] = None          # 최대 조건 임피던스 (Ω, 그 노드 전압 기준)
    z_min: Optional[complex] = None
    motor_contrib: float = 0.0               # A
    missing: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    unverified: List[str] = field(default_factory=list)   # 미확인 규칙 사용


def _cfactor(rules: RuleSet, un: float, src) -> (float, float, str):
    v = rules.values("SC_VOLTAGE_FACTOR")
    if un <= 1000.0:
        tol = (src.params.get("tolerance") if src is not None else None) or "6%"
        return (v["lv"]["cmax_10pct"] if tol == "10%" else v["lv"]["cmax_6pct"]), v["lv"]["cmin"], \
            f"저압 cmax {'1.10(+10%)' if tol == '10%' else '1.05(+6%)'}"
    return v["mv"]["cmax"], v["mv"]["cmin"], "고압 cmax 1.1"


def cable_z(rules: RuleSet, e, S: float):
    """배선 임피던스 → (최대 조건 R20+jX, 최소 조건 R(단락 온도한계)+jX, 메모). S 는 단면적(㎟)."""
    rho1 = rules.values("RESISTIVITY_SERVICE")
    lam0 = rules.values("REACTANCE_DEFAULT")["x_ohm_per_m"]
    tlim = rules.values("SC_TEMP_LIMIT")
    alpha = rules.values("SC_RESISTANCE_TEMP")["alpha"]
    L, mat = e.params["length"], e.installed["material"]
    par = int(e.installed.get("parallel") or 1)
    r20 = rho1[mat] / 1.25 * L / S / par
    ins = e.installed.get("insulation")
    note = ""
    if ins in ("XLPE", "EPR"):
        te = tlim[ins]
    elif ins == "PVC":
        te = tlim["PVC_le300"] if S <= 300 else tlim["PVC_gt300"]
    else:
        te = tlim["XLPE"]
        note = f"{e.id}: 절연 미입력 → 최소 단락용 온도한계 {te:g}℃(가장 높은 저항, 보수적)"
    r_hot = r20 * (1 + alpha * (te - 20.0))
    x = (e.params.get("x") or lam0) * L / par
    return complex(r20, x), complex(r_hot, x), note


def ik_min_at_end(res: EResult, rules: RuleSet, eid: str, S: float) -> Optional[float]:
    """배선 eid 의 단면적을 S 로 둘 때 배선 끝 최소 단락전류 (전원 측 z_min + 배선). 계산 불가면 None."""
    e = res.model.edges[eid]
    up = res.sc.get(e.from_id)
    if up is None or up.z_min is None or not up.voltage or e.params.get("length") is None \
            or e.installed.get("material") is None:
        return None
    src = next((n for n in res.model.nodes.values() if n.type == "source"), None)
    _, cmin, _ = _cfactor(rules, up.voltage, src)
    return cmin * up.voltage / (SQRT3 * abs(up.z_min + cable_z(rules, e, S)[1]))


def compute(res: EResult, rules: RuleSet) -> Dict[str, SCResult]:
    m = res.model
    out: Dict[str, SCResult] = {}
    sc = res.scenarios.get(res.design_scenario) or next(iter(res.scenarios.values()), None)
    on = set(sc.on_loads) if sc else set()
    rho1 = rules.values("RESISTIVITY_SERVICE")
    lam0 = rules.values("REACTANCE_DEFAULT")["x_ohm_per_m"]
    tlim = rules.values("SC_TEMP_LIMIT")
    alpha = rules.values("SC_RESISTANCE_TEMP")["alpha"]
    kt = rules.values("TRANSFORMER_KT")
    src = None
    for nid in res.order:
        n = m.nodes[nid]
        v_in, v_out, _ = res.levels.get(nid, (None, None, 3))
        r = SCResult(nid, voltage=v_out if n.type in ("source", "transformer") else v_in)
        up = res.upstream.get(nid)
        if n.type == "source":
            src = n
            un = n.params.get("voltage")
            s_max = n.params.get("sc_mva")
            if not un or not s_max:
                r.missing.append(f"{nid}: 전원 단락용량(sc_mva) — 한전 제공 자료(검사·점검 기준 표 220-2)")
            else:
                s_min = n.params.get("sc_mva_min") or s_max
                cmax, cmin, _ = _cfactor(rules, un, n)
                rx = n.params.get("rx")
                if rx is None:
                    rx = 0.1
                    r.assumptions.append(f"{nid}: 전원 R/X 미입력 → 0.1 가정")
                def zq(c, s):
                    z = c * un * un / s
                    x = z / math.sqrt(1 + rx * rx)
                    return complex(rx * x, x)
                r.z_max, r.z_min = zq(cmax, s_max), zq(cmin, s_min)
            out[nid] = r
            continue
        ur_ = out.get(up)
        if ur_ is None or ur_.z_max is None:
            r.missing = list(ur_.missing) if ur_ else ["전원 측 단락 임피던스"]
            out[nid] = r
            continue
        r.assumptions, r.unverified = list(ur_.assumptions), list(ur_.unverified)
        zmax, zmin = ur_.z_max, ur_.z_min
        if n.type == "transformer":
            prim, sec, srt = n.params.get("primary"), n.params.get("secondary"), n.installed.get("rated")
            uk, urr = n.installed.get("uk"), n.installed.get("ur")
            if not (prim and sec and srt and uk):
                r.missing.append(f"{nid}: 변압기 " + ", ".join(x for x, ok in (("1차·2차 전압", prim and sec),
                                                                             ("정격용량", srt), ("%임피던스 uk", uk)) if not ok))
                out[nid] = r
                continue
            ratio = (sec / prim) ** 2
            zmax, zmin = zmax * ratio, zmin * ratio
            zb = sec * sec / srt
            if urr is None:
                urr = 0.0
                r.assumptions.append(f"{nid}: %저항 uR 미입력 → 0 (임피던스 전부 리액턴스)")
            zt = complex(urr * zb, math.sqrt(max(uk * uk - urr * urr, 0.0)) * zb)
            cmax, _, _ = _cfactor(rules, sec, src)
            xt = math.sqrt(max(uk * uk - urr * urr, 0.0))
            KT = kt["a"] * cmax / (1 + kt["b"] * xt)
            r.unverified.append("변압기 보정계수 KT (IEC 60909, 원문 미제공)")
            zmax, zmin = zmax + zt * KT, zmin + zt
        eid = res.via_edge.get(nid)
        if eid:
            e = m.edges[eid]
            L, S, mat = e.params.get("length"), e.installed.get("size"), e.installed.get("material")
            if L is None or S is None or mat is None:
                r.missing.append(f"{eid}: " + ", ".join(x for x, ok in (("길이", L is not None), ("단면적", S),
                                                                       ("재질", mat)) if not ok))
                out[nid] = r
                continue
            z_c_max, z_c_min, note = cable_z(rules, e, S)
            if note:
                r.assumptions.append(note)
            if "선로 고온 저항 환산 계수 0.004/K (IEC 60909, 원문 미제공)" not in r.unverified:
                r.unverified.append("선로 고온 저항 환산 계수 0.004/K (IEC 60909, 원문 미제공)")
            zmax += z_c_max
            zmin += z_c_min
        r.z_max, r.z_min = zmax, zmin
        out[nid] = r
    # 단락전류 + 전동기 기여 (최대)
    # 같은 전압 레벨의 '저압 모선'(변압기 2차 또는 전원) 아래 운전 전동기를 그 모선에 모은 등가 임피던스
    # Z_M = cmax·Un/(√3·ΣIM)(리액턴스)로 보고, 모선 테브난 Z_th = Z_계통 ∥ Z_M 에 모선 → 고장점 임피던스를 더한다.
    # (전동기 ~ 모선 사이 배선 임피던스 무시 → 보수적)
    motors = [m.nodes[i] for i in on if m.nodes[i].params.get("kind") == "motor"]

    def lv_root(nid):
        cur = nid
        while True:
            up = res.upstream.get(cur)
            if up is None or m.nodes[cur].type in ("transformer", "source"):
                return cur
            cur = up

    groups: Dict[str, List] = {}
    for mo in motors:
        groups.setdefault(lv_root(mo.id), []).append(mo)
    for nid, r in out.items():
        if r.z_max is None or not r.voltage:
            continue
        cmax, cmin, _ = _cfactor(rules, r.voltage, src)
        root = lv_root(nid)
        z_bus = out[root].z_max if root in out else None
        contrib, unknown = 0.0, []
        for mo in groups.get(root, []):
            beta = mo.params.get("start_multiplier")
            cur = sc.nodes[mo.id].current if sc else None
            if beta is None or cur is None:
                unknown.append(mo.id)
                continue
            contrib += beta * cur
        z_eff = r.z_max
        if contrib and z_bus is not None and abs(z_bus) > 0:
            zm = complex(0.0, cmax * r.voltage / (SQRT3 * contrib))
            z_th = z_bus * zm / (z_bus + zm)
            z_eff = z_th + (r.z_max - z_bus)
        r.ik_max = cmax * r.voltage / (SQRT3 * abs(z_eff))
        r.ik_min = cmin * r.voltage / (SQRT3 * abs(r.z_min))
        r.motor_contrib = max(r.ik_max - cmax * r.voltage / (SQRT3 * abs(r.z_max)), 0.0)
        if unknown:
            r.assumptions.append("전동기 기여 미포함(기동전류 배수 미입력): " + ", ".join(sorted(unknown)))
    return out
