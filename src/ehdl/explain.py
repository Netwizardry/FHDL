"""설명·질문 생성 (SPEC 7.3) — 계산값과 입력값만으로 문장을 만든다. 단정하지 않는다.

원칙
- FAIL: 무엇이 얼마나 넘는지 + 원인 부하 + 검토 방향을 '질문'으로.
- REVIEW: 왜 확정하지 못했는지(규칙 미확인·추정 입력·선정 근거 없음)를 밝힌다.
- UNKNOWN: 오류라고 하지 않고 필요한 정보를 묻는다.
"""
from __future__ import annotations

from typing import List

from .model import Check
from .units import fmt


def _who(c: Check, n: int = 3) -> str:
    top = c.evidence.contributors[:n]
    if not top:
        return ""
    parts = ", ".join(f"{i}({fmt(s, 'VA')})" for i, s in top)
    more = len(c.evidence.contributors) - len(top)
    return parts + (f" 외 {more}개" if more > 0 else "")


def explain(c: Check, name: str = "") -> None:
    """Check 에 explanation·questions 를 채운다."""
    who = name or c.target
    u = c.unit
    act, inst = c.actual, c.installed
    sc = f" ('{c.evidence.scenario}' 운전 조건)" if c.evidence.scenario else ""
    rule = c.evidence.rule
    unverified = rule is not None and not rule.verified
    q: List[str] = []

    if c.status == "UNKNOWN" and c.kind != "spd":
        need = ", ".join(c.missing) if c.missing else "필수 입력"
        c.explanation = (f"{who}: {c.title} 을(를) 판정하려면 {need} 이(가) 필요합니다. "
                         "입력이 없어 판정을 보류합니다(설계 오류라는 뜻이 아닙니다).")
        if act is not None and c.kind == "cable_size":
            c.explanation += f" 계산된 조건만으로는 {c.required.text()} 입니다."
        elif act is not None and inst is not None and c.kind not in ("voltage_drop", "unbalance"):
            c.explanation += f" 현재 확인된 부하만으로는 {fmt(act, u)} / 정격 {fmt(inst, u)} 입니다."
        q += [f"{who} 의 {m} 값을 알려 주실 수 있나요?" for m in c.missing[:4]]
    elif c.kind in ("source_limit", "transformer_rating", "board_rating", "breaker_load", "cable_ampacity"):
        if inst is None:
            c.explanation = (f"{who}: 현재 조건{sc}에서 요구되는 {c.title} 은(는) "
                             f"{c.required.text() if c.required else '-'} 입니다. 실제 규격이 입력되지 않아 검산 대상이 아닙니다.")
        else:
            ratio = f" 사용률 {c.utilization * 100:.0f}%" if c.utilization is not None else ""
            c.explanation = (f"{who}: 최대 예상 {fmt(act, u)}{sc}, 정격 {fmt(inst, u)}.{ratio}"
                             + (f", 여유율 {100 - c.utilization * 100:.0f}%." if c.utilization is not None
                                and c.utilization <= 1 else "."))
            if c.status == "FAIL":
                c.explanation += f" 정격을 {fmt(act - inst, u)} 초과합니다. 주요 원인 부하: {_who(c)}."
                q.append(f"{who} 의 정격 {fmt(inst, u)} 이(가) 최대 {fmt(act, u)} 보다 작습니다. "
                         "정격 상향·부하 분산·운전 제약 중 어떤 방안을 검토하셨나요?")
            if c.estimated:
                c.explanation += " (추정 입력이 포함된 결과입니다.)"
    elif c.kind == "breaker_cable_coord":
        c.explanation = (f"{who}: 보호장치 정격 In {fmt(inst, 'A')} 과 배선 허용전류 Iz {fmt(act, 'A')} 의 관계 "
                         f"(In ≤ Iz).")
        if c.status == "FAIL":
            q.append(f"{who} 의 정격이 보호하는 배선의 허용전류보다 큽니다. 배선 굵기 또는 차단기 정격을 다시 확인하셨나요?")
    elif c.kind == "voltage_drop":
        lim = c.required.value if c.required else None
        c.explanation = (f"{who}: 전원에서 부하까지 전압강하 {fmt(act, '%', 2)}{sc}, 허용 {fmt(lim, '%', 2)}.")
        if c.status == "FAIL":
            q.append(f"{who} 까지의 전압강하가 허용치를 넘습니다. 배선 굵기 상향이나 경로 단축을 검토하셨나요?")
        if c.estimated:
            c.explanation += " 추정 입력(" + "; ".join(c.evidence.assumptions) + ")이 포함되어 있습니다."
            q.append(f"{who} 경로의 배선 길이가 실측·CAD 값인가요? 그렇다면 length_basis 를 지정해 주세요.")
    elif c.kind == "unbalance":
        c.explanation = f"{who}: 단상 부하 설비불평형률 {fmt(act, '%')} (허용 {fmt(c.required.value if c.required else None, '%')})."
        if c.status == "FAIL":
            q.append(f"{who} 의 단상 부하를 다른 상으로 옮겨 불평형을 줄일 수 있나요?")
    elif c.kind == "sizing_rationale":
        c.explanation = (f"{who}: 최대 예상 {fmt(act, u)} 에 정격 {fmt(inst, u)} — 현재 조건의 사용률은 "
                         f"{c.utilization * 100:.0f}% 입니다.")
        if c.status == "PASS":
            c.explanation += f" 선정 근거: {c.evidence.values.get('justification_text', '') or '입력됨'}."
        else:
            c.explanation += " 향후 증설 등을 고려한 선정인지 확인할 수 있습니다(과대 설계로 단정하지 않습니다)."
            q.append(f"{fmt(inst, u)} 을(를) 선정한 이유가 향후 증설 때문인가요? 그렇다면 추가 예정 부하는 얼마인가요?")
    elif c.kind == "breaking_capacity":
        ik = fmt(act / 1000 if act else None, "kA", 1)
        if inst is None:
            c.explanation = f"{who}: 설치 점 최대 예상 단락전류 {ik} — 이보다 큰 정격차단용량이 필요합니다(실제 규격 미입력)."
        else:
            c.explanation = f"{who}: 설치 점 최대 예상 단락전류 {ik}, 정격차단용량 {fmt(inst / 1000, 'kA', 1)}."
            if c.status == "FAIL":
                q.append(f"{who} 의 차단용량 {fmt(inst / 1000, 'kA', 0)} 이(가) 예상 단락전류 {ik} 보다 작습니다. "
                         "차단용량 상향 또는 전원 측 후비보호(캐스케이드) 협조를 검토하셨나요?")
        extra = c.evidence.values.get("전동기 기여(A)")
        if extra:
            c.explanation += f" (전동기 기여 {extra / 1000:.1f} kA 포함)"
    elif c.kind == "selectivity":
        c.explanation = f"{who}: {c.title} — " + ("; ".join(c.evidence.assumptions) or
                                                 f"하위 설치 점 단락전류 {fmt(act, 'A', 0)} < 상위 순시 하한 {fmt(inst, 'A', 0)}.")
        if c.status == "REVIEW":
            q.append(f"{who} 와 상위 차단기의 선택차단을 제조사 선택차단표(또는 시간-전류 곡선)로 확인하셨나요?")
    elif c.kind == "thermal":
        c.explanation = (f"{who}: 최소 단락전류가 보호장치 동작시간 동안 흐를 때 필요한 단면적 "
                         f"{fmt(act, 'mm²', 1)}, 실제 {fmt(inst, 'mm²', 1)}.")
        if c.status == "FAIL":
            q.append(f"{who} 의 굵기가 단락 열적 내량에 부족합니다. 굵기 상향 또는 더 빠른 보호장치를 검토하셨나요?")
    elif c.kind == "motor_start_vd":
        c.explanation = f"{who}: 기동 순간 전동기 단자 전압강하 {fmt(act, '%', 1)} (다른 부하 운전 중)."
        if c.required:
            c.explanation += f" 허용 {fmt(c.required.value, '%', 1)}."
        else:
            q.append(f"{who} 기동 시 허용 전압강하(기기·제어 요구값)는 얼마인가요? (KEC 는 기동 중 수치 한도를 두지 않음)")
    elif c.kind == "motor_start_protection":
        c.explanation = f"{who}: 기동전류 {fmt(act, 'A', 0)} — " + ("; ".join(c.evidence.assumptions) or "순시·장시간 영역 모두 트립하지 않음.")
        if c.status != "PASS":
            q.append(f"{who} 를 보호하는 차단기의 제조사 동작곡선에서 최소동작시간 tb(기동시간 × 1.5)의 동작배율 δ 는 얼마인가요?")
    elif c.kind == "rcd_socket":
        if c.status == "FAIL" and c.installed is None:
            c.explanation = f"{who}: 일반인이 쓰는 20 A 이하 콘센트인데 전원 측에 누전차단기가 없습니다 (KEC 211.2.3의 4)."
            q.append(f"{who} 회로에 누전차단기(30 mA)를 두지 않은 이유가 있나요?")
        elif c.installed is not None:
            c.explanation = f"{who}: 누전차단기 감도 {c.installed:g} mA (요구 30 mA 이하)."
    elif c.kind == "spd":
        c.explanation = (f"{who}: 서지가 유입되는 선로에는 SPD 를 두어야 합니다(KEC 153.1.4). 선정 기준(Uc·Up)은 "
                         "KS C IEC 61643-12 에 따르며 제공 자료에 수치가 없어 확인만 요청합니다.")
        q.append("인입 선로(가공 인입·통신선 등)로 서지가 유입될 수 있나요? 그렇다면 SPD 의 위치와 Uc·Up 근거는 무엇인가요?")
    elif c.kind == "fault_protection":
        v = c.evidence.values
        if "Zs(Ω)" in v:
            ia = f"{inst * 1000:g} mA(누전차단기 IΔn)" if inst < 1 else fmt(inst, "A", 0)
            c.explanation = (f"{who}: 지락 시 고장루프임피던스 Zs {v['Zs(Ω)']:.3f} Ω → 고장전류 {fmt(act, 'A', 0)}, "
                             f"보호장치가 {v['허용 차단시간(s)']:g}초 안에 동작하려면 {ia} 이상 필요 "
                             f"(Zs 허용 {v['Zs 허용 U0/Ia(Ω)']:.3f} Ω)."
                             + (" " + "; ".join(a for a in c.evidence.assumptions if "곡선" in a)
                                if any("곡선" in a for a in c.evidence.assumptions) else ""))
        elif c.unit == "V" and act is not None:
            c.explanation = f"{who}: RA × IΔn = {act:.1f} V (허용 50 V)."
        if c.status == "FAIL":
            q.append(f"{who} 회로는 지락 때 제시간에 차단되지 않습니다. 보호도체 굵기·배선 길이·누전차단기 추가 중 무엇을 검토하셨나요?")
    elif c.kind == "tnc_rcd":
        c.explanation = f"{who}: TN-C 계통에는 누전차단기를 쓸 수 없습니다 (KEC 211.2.5의 8)."
        q.append("계통접지 방식이 TN-C 가 맞나요? TN-C-S 라면 누전차단기 부하측에 PEN 도체를 쓰지 않았는지 확인해 주세요.")
    elif c.kind == "it_first_fault":
        c.explanation = f"{who}: IT 계통 1차 고장 RA × Id = {fmt(act, 'V', 1)} (허용 50 V)."
    elif c.kind == "pe_size":
        req = c.required.value if c.required else act
        c.explanation = (f"{who}: 보호도체 최소 {fmt(req, 'mm²', 1)} (표 142.3-1)" +
                         (f", 실제 {fmt(inst, 'mm²', 1)}." if inst is not None else " — 실제 PE 굵기 미입력."))
        if c.status == "FAIL":
            q.append(f"{who} 의 보호도체가 표 142.3-1 최소값보다 가늡니다. 계산식(142.3.2의 나)으로 따로 확인하셨나요?")
    elif c.kind == "bonding":
        c.explanation = f"{who}: 보호등전위본딩 도체 최소 {fmt(c.required.value, 'mm²', 1)}" + (f", 실제 {fmt(inst, 'mm²', 1)}." if inst else ".")
    elif c.kind == "main_bonding":
        c.explanation = f"{who}: 주 보호등전위본딩(bond kind = main)이 모델에 없습니다."
        q.append("수도관·가스관·건축 철골 등 인입 도전부를 주접지단자에 본딩했나요? 본딩 도체 굵기는 얼마인가요?")
    elif c.kind == "supply_summary":
        v = c.evidence.values
        c.explanation = (f"{who}: 설비용량 {v['설비용량 합계(kW)']:g} kW · 최대수요전력 {v['최대수요전력(kW)']:g} kW "
                         f"({v['최대수요전력(kVA)']:g} kVA, 수용률 {v['수용률(계산)'] * 100:.0f}%)"
                         + "".join(f" · {k} {val:g}" for k, val in v.items() if k.endswith("정격(kVA)"))
                         + (f" · 계약전력 {v['계약전력(kW)']:g} kW" if "계약전력(kW)" in v else "")
                         + (f" · 식 230-6 변압기 용량 {v['식 230-6 변압기 용량(kVA)']:g} kVA" if "식 230-6 변압기 용량(kVA)" in v else "")
                         + ". 계약전력·최대수요전력·변압기 정격은 서로 다른 값입니다.")
        if c.status == "FAIL":
            q.append("최대수요전력이 계약전력(또는 산정 변압기 용량)을 넘습니다. 계약 변경이나 부하 제한을 검토하셨나요?")
        elif "계약전력(kW)" not in v:
            q.append("한전 계약전력은 얼마인가요? (최대수요전력과 별도로 관리됩니다)")
    elif c.kind == "cable_size":
        v = c.evidence.values
        cands = [f"{v[k]:g}㎟" for k in sorted(k for k in v if k.startswith("후보"))]
        parts = [f"{k.replace(' 최소(㎟)', '')} {v[k]:g}㎟" for k in v if k.endswith("최소(㎟)")]
        c.explanation = (f"{who}: 조건별 최소 단면적 — " + ", ".join(parts) + f". 모두 만족하는 {c.required.text()}, "
                         f"후보 {', '.join(cands)}.")
        if inst is None:
            c.explanation += " 실제 단면적이 입력되지 않아 기본설계 산정값만 보여 줍니다."
        elif c.status == "FAIL":
            c.explanation += f" 설계 {fmt(inst, 'mm²')} 은(는) 부족합니다."
            q.append(f"{who} 를 {cands[0]} 이상으로 키우거나, 지배 조건을 완화하는 방안"
                     "(경로 단축·부하 분산·보호장치 조정)을 검토하셨나요?")
        else:
            c.explanation += f" 설계 {fmt(inst, 'mm²')} 은(는) 충족합니다."
        if c.evidence.defaults:
            c.explanation += " (" + "; ".join(c.evidence.defaults[:2]) + ")"
    elif c.kind == "sc_min_trip":
        v = c.evidence.values
        far = c.evidence.inputs[-1] if len(c.evidence.inputs) > 1 else who
        c.explanation = (f"{who}: 보호 구간 끝({far})의 최소 단락전류 {fmt(act, 'A')}, 순시 트립 상한 {fmt(inst, 'A')}. "
                         f"이 차단기가 동작하면 부하 {v.get('차단 범위 부하 수', 0):g}개가 정전됩니다(차단 범위).")
        if act is not None and inst is not None and act < inst:
            c.explanation += " 순시 영역에 들지 않아 장한시 영역(수 초)에서 동작할 수 있습니다."
            q.append(f"{who} 의 제조사 시간-전류 곡선에서 {fmt(act, 'A')} 일 때 동작시간은 얼마인가요? "
                     "그 시간으로 배선 열적 내량이 충족되나요?")
    elif c.kind == "rated_voltage":
        c.explanation = f"{who}: 정격전압 {fmt(inst, 'V')}, 설치 점 계통전압 {fmt(act, 'V')}."
        if c.status == "FAIL":
            q.append(f"{who} 의 정격전압이 계통전압보다 낮습니다. 제품 정격을 다시 확인해 주시겠어요?")
    elif c.kind == "rcd_selectivity":
        c.explanation = (f"{who}: 상위 누전차단기와의 동작시간·감도 관계 — "
                         + ("; ".join(c.evidence.assumptions + c.evidence.defaults) or "형·감도 입력 필요") + ".")
        if c.evidence.assumptions:
            q.append(f"{who} 아래 누전에 상위 누전차단기도 함께 동작할 수 있습니다. 상위를 시연형(delayed)으로 하셨나요?")
    elif c.kind == "load_input" and c.status == "REVIEW":
        c.explanation = (f"{who}: " + "; ".join(c.evidence.assumptions) + ". 전류·용량 판정은 보수적인 값으로 하되 "
                         "확정하지 않습니다.")
        q.append(f"{who} 의 역률(pf)은 얼마인가요? (부하 일람표의 VA 만으로는 유효·무효전력을 나눌 수 없습니다)")
    elif c.kind == "load_input":
        c.explanation = f"{who}: 부하 전력을 계산하려면 {', '.join(c.missing)} 이(가) 필요합니다."
        q += [f"{who} 의 {m} 값을 알려 주실 수 있나요?" for m in c.missing]

    if c.status == "REVIEW" and any("원문 미제공" in d for d in c.evidence.defaults):
        c.explanation += (" 계산에 원문이 제공되지 않은 값(" + "; ".join(d for d in c.evidence.defaults if "원문 미제공" in d)
                          + ")을 써서 확정하지 않습니다.")
    if unverified and c.status in ("REVIEW", "FAIL") and c.kind in ("voltage_drop", "unbalance", "breaker_cable_coord"):
        c.explanation += (f" 적용 기준 '{rule.title}'({rule.source} {rule.clause}) 은(는) 원문 확인 전 값이라 "
                          "확정 판정하지 않습니다.")
    c.questions = q
