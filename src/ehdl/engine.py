"""EHDL 결정론적 계산 엔진 (Phase 1) — 토폴로지·부하·시나리오·상향 집계·전압강하.

계산 흐름 (SPEC 5.1):
  토폴로지: 각 노드의 전원 측 설비 = 들어오는 배선의 from → feed → parent(반 모선)
  부하 전력: P(입력 kW) · Q = P·tan(acos pf) · 상 배분(삼상 1/3, L-N 단상 그 상, 선간 단상 두 상에 1/2)
  시나리오: rated(정격 합계) · normal(정상 운전 상태) · max_demand(동시운전 그룹 제약 내 최대) · 사용자 정의
  상향 집계: 유효·무효전력을 각각 합산(피상전력을 단순 합하지 않음, SPEC 5.2), 상별 복소 피상전력 합
  전류: 상별 |S_k| / V_LN (단상 상 미지정이 있으면 평형 가정 추정)
  전압강하: ΔV = k·I·L·(R cosφ + X sinφ), k = √3(삼상)·2(단상), 전원/변압기 2차부터 누적
입력이 없으면 지어내지 않는다 — 그 부하는 집계에서 빼고 incomplete 로 남겨 UNKNOWN 판정의 근거가 된다.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from fhdl.core.models import DiagnosticItem

from .model import EResult, NodeResult, Scenario, ScenarioResult, SystemModel
from .rules import RuleSet

SQRT3 = math.sqrt(3.0)
_PHASE_IDX = {"L1": (0,), "L2": (1,), "L3": (2,), "L1L2": (0, 1), "L2L3": (1, 2), "L3L1": (2, 0)}
NON_MECHANICAL = ("lighting", "receptacle", "heater")    # kW = 전기 입력이 정의상 자명한 용도


# ---------------------------------------------------------------------------
# 토폴로지
# ---------------------------------------------------------------------------

def build_topology(m: SystemModel, diags: List[DiagnosticItem]):
    """(upstream, via_edge, children, order) — order 는 전원에서 내려가는 순서."""
    incoming: Dict[str, List[str]] = {}
    for e in m.edges.values():
        if e.type == "cable" and e.to_id in m.nodes:
            incoming.setdefault(e.to_id, []).append(e.id)
    upstream: Dict[str, Optional[str]] = {}
    via: Dict[str, Optional[str]] = {}
    for n in power_nodes(m):
        cabs = incoming.get(n.id, [])
        if len(cabs) > 1:
            diags.append(DiagnosticItem("ENET003", "ERROR",
                                        f"'{n.id}' 에 배선이 {len(cabs)}개 들어옵니다 ({', '.join(cabs)}) — "
                                        "Phase 1 은 방사형(전원 측 1개)만 지원합니다.", n.span, n.id))
        if cabs:
            upstream[n.id], via[n.id] = m.edges[cabs[0]].from_id, cabs[0]
        elif n.feed:
            upstream[n.id], via[n.id] = n.feed, None
        elif n.parent:
            upstream[n.id], via[n.id] = n.parent, None
        else:
            upstream[n.id], via[n.id] = None, None
    sources = [n.id for n in m.nodes.values() if n.type == "source"]
    if not sources:
        diags.append(DiagnosticItem("ENET001", "ERROR", "전원(source)이 없습니다.", nodes_span(m), "",
                                    "source KEPCO { voltage = 380V; phases = 3; } 를 추가하세요."))
    elif len(sources) > 1:
        diags.append(DiagnosticItem("ENET006", "ERROR",
                                    f"전원이 {len(sources)}개입니다 ({', '.join(sources)}) — 단일 전원만 지원합니다.",
                                    m.nodes[sources[1]].span, sources[1]))
    for s in sources:
        if upstream.get(s):
            diags.append(DiagnosticItem("ENET002", "ERROR", f"전원 '{s}' 에 상위 설비가 연결되어 있습니다.",
                                        m.nodes[s].span, s))
            upstream[s] = None
    # 순환·고립·부하 아래 연결
    for n in power_nodes(m):
        seen, cur = [], n.id
        while cur is not None and cur not in seen:
            seen.append(cur)
            cur = upstream.get(cur)
        if cur is not None:
            diags.append(DiagnosticItem("ENET004", "ERROR", f"'{n.id}' 의 전원 측 연결이 순환합니다.", n.span, n.id))
            upstream[n.id] = None
        elif m.nodes[seen[-1]].type != "source" and n.type != "source":
            diags.append(DiagnosticItem("ENET002", "ERROR", f"'{n.id}' 이(가) 전원에 연결되어 있지 않습니다.",
                                        n.span, n.id, "배선(cable)·feed·parent 로 상위 설비에 연결하세요."))
    for nid, up in upstream.items():
        if up and m.nodes[up].type == "load":
            diags.append(DiagnosticItem("ENET005", "ERROR", f"'{nid}' 이(가) 부하 '{up}' 아래에 연결되어 있습니다.",
                                        m.nodes[nid].span, nid))
    children: Dict[str, List[str]] = {n.id: [] for n in power_nodes(m)}
    for nid, up in upstream.items():
        if up in children:
            children[up].append(nid)
    order: List[str] = []
    stack = list(reversed(sources))
    while stack:
        nid = stack.pop()
        order.append(nid)
        stack.extend(reversed(children[nid]))
    return upstream, via, children, order


def power_nodes(m: SystemModel):
    """전력 트리에 속하는 노드 (접지·보호도체 노드 제외)."""
    return [n for n in m.nodes.values() if n.type != "earth"]


def nodes_span(m: SystemModel):
    from fhdl.core.models import SourceSpan
    return next((n.span for n in m.nodes.values()), SourceSpan())


# ---------------------------------------------------------------------------
# 전압 레벨
# ---------------------------------------------------------------------------

def voltage_levels(m: SystemModel, order, upstream, diags) -> Dict[str, Tuple[Optional[float], Optional[float], int]]:
    """노드 → (입력 측 선간전압, 출력 측 선간전압, 계통 상수)."""
    lv: Dict[str, Tuple[Optional[float], Optional[float], int]] = {}
    for nid in order:
        n = m.nodes[nid]
        if n.type == "source":
            v = n.params.get("voltage")
            ph = int(n.params.get("phases") or 3)
            lv[nid] = (v, v, ph)
            continue
        up = upstream.get(nid)
        v_in, ph = (lv[up][1], lv[up][2]) if up in lv else (None, 3)
        v_out = v_in
        if n.type == "transformer":
            prim, sec = n.params.get("primary"), n.params.get("secondary")
            if prim and v_in and abs(prim - v_in) / v_in > 0.1:
                diags.append(DiagnosticItem("ENET007", "WARNING",
                                            f"변압기 '{nid}' 1차 전압 {prim:g}V 가 상위 전압 {v_in:g}V 와 다릅니다.",
                                            n.span, nid))
            v_out = sec
        lv[nid] = (v_in, v_out, ph)
    return lv


# ---------------------------------------------------------------------------
# 부하 전력
# ---------------------------------------------------------------------------

PF_UNKNOWN_NOTE = "역률(pf) 미입력 — 피상전력(kVA) 정격으로 전류·용량은 산술합(보수적), 전압강하는 최악 역률각"


def load_power(n) -> Tuple[Optional[complex], List[str], List[str]]:
    """(복소 피상전력 P+jQ [VA], 누락 입력, 가정) — 누락이 있으면 전력은 None.

    kVA 정격인데 역률만 없으면 크기는 알므로 (S∠0, [], [PF_UNKNOWN_NOTE]) — 집계는 S_extra(산술합)로 한다.
    """
    p = n.params
    missing: List[str] = []
    kind = p.get("kind")
    rating = p.get("rating")
    unit = n.unit_kinds.get("rating")
    pf = p.get("pf")
    if rating is None:
        missing.append("정격(rating)")
    if not p.get("phases"):
        missing.append("상수(phases: 1 또는 3)")
    P = None
    if rating is not None and unit == "apparent":
        if pf is None:
            if not missing:
                return complex(rating, 0.0), [], [PF_UNKNOWN_NOTE]
            missing.append("역률(pf)")
        else:
            P = rating * pf
    elif rating is not None:
        basis = p.get("basis") or ("input" if kind in NON_MECHANICAL else None)
        if basis is None:
            missing.append("정격 기준(basis: output=기계 출력 / input=전기 입력)")
        elif basis == "output":
            if p.get("efficiency") is None:
                missing.append("효율(efficiency) — 기계 출력 기준")
            else:
                P = rating / p["efficiency"]
        else:
            P = rating
        if pf is None:
            missing.append("역률(pf)")
    if missing or P is None:
        return None, missing, []
    Q = P * math.tan(math.acos(min(max(pf, 1e-6), 1.0)))
    return complex(P, Q), [], []


def phase_share(n, S: complex, sys_phases: int) -> Tuple[Optional[Tuple[complex, complex, complex]], bool]:
    """(상별 복소 피상전력, 상 미지정 여부)."""
    ph = n.params.get("phases")
    if sys_phases == 1:
        return (S, 0j, 0j), False
    if ph == 3:
        return (S / 3, S / 3, S / 3), False
    idx = _PHASE_IDX.get(n.params.get("phase") or "")
    if not idx:
        return None, True
    parts = [0j, 0j, 0j]
    for i in idx:
        parts[i] += S / len(idx)
    return tuple(parts), False


# ---------------------------------------------------------------------------
# 시나리오
# ---------------------------------------------------------------------------

def scenarios(m: SystemModel, load_S: Dict[str, Optional[complex]], diags, children) -> List[Scenario]:
    loads = [n.id for n in m.loads()]
    normal = {i for i in loads if m.nodes[i].params.get("state") != "off"}
    unset = [i for i in loads if not m.nodes[i].params.get("state")]
    out = [Scenario("rated", set(loads), builtin=True, description="정격 합계 — 모든 부하 운전 (참고용)"),
           Scenario("normal", normal, builtin=True,
                    description="정상 운전 상태(state) 기준" + (f" — 상태 미지정 {len(unset)}개는 ON" if unset else ""))]
    if m.groups:
        chosen = set(normal)
        notes = []
        for g in m.groups.values():
            members = [i for i in normal if m.nodes[i].params.get("group") == g.id]
            if g.max_on is not None and len(members) > g.max_on:
                # 제약 기반 선택: 피상전력이 큰 순으로 max_on 대 (전체 조합 나열 없이 최대 부하)
                ranked = sorted(members, key=lambda i: (-(abs(load_S[i]) if load_S.get(i) else 0.0), i))
                for i in ranked[g.max_on:]:
                    chosen.discard(i)
                notes.append(f"{g.id}: {len(members)}대 중 {g.max_on}대")
        out.append(Scenario("max_demand", chosen, builtin=True,
                            description="동시운전 그룹 제약 내 최대 부하 (" + ", ".join(notes) + ")" if notes
                            else "동시운전 그룹 제약 내 최대 부하"))
    new = {i for i in loads if _is_new(m, i)}
    if new:
        out.append(Scenario("existing", normal - new, builtin=True,
                            description=f"기존 설비만 (신규 부하 {len(new)}개 제외) — 혼합 모드 비교 기준(참고용)"))
    for s in m.scenarios.values():
        on: Set[str] = set(normal) if s.on is None else set()
        for ref in (s.on or set()):
            if ref == "all":
                on |= set(loads)
            elif ref in m.groups:
                on |= {i for i in loads if m.nodes[i].params.get("group") == ref}
            elif ref in m.nodes:
                on |= loads_under(m, children, ref)
        for ref in s.off:
            if ref in m.groups:
                on -= {i for i in loads if m.nodes[i].params.get("group") == ref}
            elif ref in m.nodes:
                on -= loads_under(m, children, ref)
        for g in m.groups.values():
            cnt = sum(1 for i in on if m.nodes[i].params.get("group") == g.id)
            if g.max_on is not None and cnt > g.max_on:
                diags.append(DiagnosticItem("ESCN001", "WARNING",
                                            f"시나리오 '{s.id}' 에서 그룹 {g.id} 가 {cnt}대 운전 — 제약 {g.max_on}대를 넘습니다.",
                                            s.span, s.id, "운전 제약을 확인하세요."))
        out.append(Scenario(s.id, on, set(s.off), description="사용자 정의", span=s.span))
    return out


def _is_new(m: SystemModel, lid: str) -> bool:
    """신규 부하 — 자신이 new 이거나 전원 쪽 소속·연결 설비(parent/feed) 중 new 가 있으면."""
    seen, cur = set(), lid
    while cur and cur in m.nodes and cur not in seen:
        seen.add(cur)
        n = m.nodes[cur]
        if n.stage == "new":
            return True
        inc = next((e for e in m.edges.values() if e.type == "cable" and e.to_id == cur), None)
        if inc is not None and inc.stage == "new":
            return True
        cur = inc.from_id if inc is not None else (n.feed or n.parent)
    return False


def loads_under(m: SystemModel, children, nid: str) -> Set[str]:
    """nid 아래(전기적 하류)의 부하 — nid 가 부하면 자신."""
    out, stack = set(), [nid]
    while stack:
        cur = stack.pop()
        if m.nodes[cur].type == "load":
            out.add(cur)
        stack.extend(children.get(cur, []))
    return out


# ---------------------------------------------------------------------------
# 집계 · 전류 · 전압강하
# ---------------------------------------------------------------------------

def aggregate(m: SystemModel, sc: Scenario, order, upstream, via, children, levels,
              load_S, load_missing, rules: RuleSet, pf_unknown=frozenset()) -> ScenarioResult:
    res = ScenarioResult(sc, on_loads=sorted(sc.on or []))
    for nid in reversed(order):                       # 말단 → 전원
        n = m.nodes[nid]
        v_in, v_out, sys_ph = levels.get(nid, (None, None, 3))
        r = NodeResult(nid, voltage=v_in, phases=sys_ph)
        ph = [0j, 0j, 0j]
        ex = [0.0, 0.0, 0.0]
        unassigned = False
        contrib: Dict[str, float] = {}
        if n.type == "load" and nid in (sc.on or set()):
            S = load_S.get(nid)
            if S is None:
                r.incomplete.append(nid)
            elif nid in pf_unknown:
                r.S_extra = abs(S)
                r.pf_unknown.append(nid)
                share, unassigned = phase_share(n, S, sys_ph)
                if share:
                    ex = [abs(s) for s in share]
                contrib[nid] = abs(S)
            else:
                r.P, r.Q = S.real, S.imag
                share, unassigned = phase_share(n, S, sys_ph)
                if share:
                    ph = list(share)
                contrib[nid] = abs(S)
        for c in children[nid]:
            cr = res.nodes[c]
            r.P += cr.P
            r.Q += cr.Q
            r.S_extra += cr.S_extra
            r.pf_unknown += cr.pf_unknown
            for i in range(3):
                ex[i] += cr.phase_extra[i]
            r.incomplete += cr.incomplete
            unassigned = unassigned or cr.balanced_estimate
            for i in range(3):
                ph[i] += cr.phase_S[i]
            for lid, s in cr.contributors:
                contrib[lid] = contrib.get(lid, 0.0) + s
        r.phase_S = tuple(ph)
        r.phase_extra = tuple(ex)
        r.contributors = sorted(contrib.items(), key=lambda kv: (-kv[1], kv[0]))
        r.balanced_estimate = unassigned
        v = v_in if n.type != "source" else v_out
        if v:
            if sys_ph == 1:
                r.current = r.S / v
                r.phase_current = (r.current, 0.0, 0.0)
            elif unassigned:
                r.current = r.S / (SQRT3 * v)
            else:
                vln = v / SQRT3
                pc = tuple((abs(s) + e) / vln for s, e in zip(ph, ex))
                r.phase_current = pc
                r.current = max(pc)
        res.nodes[nid] = r
    for nid in order:                                  # 전원 → 말단: 누적 전압강하
        r = res.nodes[nid]
        up = upstream.get(nid)
        if up is None:
            r.vdrop_pct, r.path_length = 0.0, 0.0
            continue
        ur = res.nodes[up]
        base_v, base_L, est = ur.vdrop_pct, ur.path_length, ur.vdrop_estimated
        if m.nodes[up].type == "transformer":         # 변압기 2차에서 새로 시작 (내부 강하는 Phase 2)
            base_v, base_L, est = 0.0, 0.0, False
        eid = via.get(nid)
        if eid is None:
            r.vdrop_pct, r.path_length, r.vdrop_estimated = base_v, base_L, est
            continue
        dv, L, e_est, _ = cable_vdrop(m, eid, r, levels, rules)
        res.edges[eid] = r
        if dv is None or base_v is None:
            r.vdrop_pct = None
        else:
            r.vdrop_pct = base_v + dv
        r.path_length = base_L + (L or 0.0)
        r.vdrop_estimated = est or e_est
    return res


def circuit_unbalance_pct(r: NodeResult) -> Optional[float]:
    """회로 불평형률 = (상별 |S| 최대 − 최소) ÷ (합 ÷ 3) × 100. 상 배분을 모르면 None."""
    if r.balanced_estimate:
        return None
    mags = [abs(s) for s in r.phase_S]
    tot = sum(mags)
    return (max(mags) - min(mags)) / (tot / 3.0) * 100.0 if tot > 0 else 0.0


def cable_vdrop(m: SystemModel, eid: str, r: NodeResult, levels, rules: RuleSet):
    """KS C IEC 60364-5-52 부속서 G: u = b(ρ1·L/S·cosφ + λ·L·sinφ)·IB, Δu% = 100·u/U0.

    b = 1(3상, U0 = 상전압) · 2(단상). 30% 이상 불평형(단상 부하) 3상 회로는 단상으로 간주(b=2,
    최대 상전류). ρ1 = 20℃ 저항률의 1.25배(기준값), λ 미입력 시 0.08 mΩ/m(기준 기본값).
    반환: (전압강하 %, 길이, 추정 여부, 메모 목록). 필수 입력이 없으면 전압강하 None.
    """
    e = m.edges[eid]
    p, inst = e.params, e.installed
    notes: List[str] = []
    missing = [lab for key, lab in (("length", "길이(length)"),) if p.get(key) is None]
    missing += [lab for key, lab in (("size", "단면적(size)"), ("material", "재질(material)")) if inst.get(key) is None]
    if missing or r.current is None:
        return None, p.get("length"), False, missing + ([] if r.current is not None else ["부하 전류(입력 부족)"])
    est = (p.get("length_basis") or "estimate") == "estimate"
    if est:
        notes.append("길이 = 추정값(length_basis 미지정 또는 estimate)")
    par = int(inst.get("parallel") or 1)
    R = rules.values("RESISTIVITY_SERVICE")[inst["material"]] / inst["size"] / par
    X = p.get("x")
    if X is None:
        X = rules.values("REACTANCE_DEFAULT")["x_ohm_per_m"]
        notes.append(f"기준 기본값 λ = {X * 1000:g} mΩ/m")
    X = X / par
    if r.S_extra > 0:
        # 역률 미입력 부하 포함 — R cosφ + X sinφ 가 최대인 역률각 (보수적, 추정)
        cos = R / math.hypot(R, X) if (R or X) else 1.0
        est = True
        notes.append(f"역률 미입력 부하 {len(set(r.pf_unknown))}개 포함 → 최악 역률각 cosφ {cos:.2f}(보수적)")
    else:
        cos = r.pf if r.pf is not None else 1.0
    sin = math.sqrt(max(0.0, 1 - cos * cos))
    v_in, _, sys_ph = levels.get(e.to_id, (None, None, 3))
    load = m.nodes.get(e.to_id)
    if sys_ph == 1:
        b, U0, I = 2.0, v_in, r.current
    elif load is not None and load.type == "load" and load.params.get("phases") == 1:
        ll = (load.params.get("phase") or "") in ("L1L2", "L2L3", "L3L1")
        U0 = v_in if ll else v_in / SQRT3
        b, I = 2.0, r.S / U0
    else:
        ub = circuit_unbalance_pct(r)
        lim = rules.values("VD_UNBALANCED_AS_1PH")["unbalance_pct"]
        if ub is not None and ub >= lim:
            b = 2.0
            notes.append(f"불평형률 {ub:.0f}% ≥ {lim:g}% → 단상 회로로 간주(b=2)")
        else:
            b = 1.0
        U0, I = v_in / SQRT3, r.current
    u = b * I * p["length"] * (R * cos + X * sin)
    return u / U0 * 100.0, p["length"], est, notes


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def solve(m: SystemModel, rules: RuleSet, diags: List[DiagnosticItem]) -> EResult:
    res = EResult(model=m)
    upstream, via, children, order = build_topology(m, diags)
    res.upstream, res.via_edge = upstream, via
    if any(d.is_blocking for d in diags):
        return res
    levels = voltage_levels(m, order, upstream, diags)
    load_S: Dict[str, Optional[complex]] = {}
    load_missing: Dict[str, List[str]] = {}
    load_assumed: Dict[str, List[str]] = {}
    for n in m.loads():
        S, missing, assumed = load_power(n)
        load_S[n.id] = S
        load_missing[n.id] = missing
        if assumed:
            load_assumed[n.id] = assumed
    pfu = frozenset(i for i, a in load_assumed.items() if PF_UNKNOWN_NOTE in a)
    for sc in scenarios(m, load_S, diags, children):
        res.scenarios[sc.id] = aggregate(m, sc, order, upstream, via, children, levels, load_S, load_missing, rules,
                                         pfu)
    res.load_missing = load_missing          # judge 에서 UNKNOWN 근거로 사용
    res.load_assumed = load_assumed
    res.levels = levels
    res.children = children
    res.order = order
    return res
