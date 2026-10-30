"""표준 부속류(fitting) K-factor 단일 진실원.

배관에 부착되는 밸브·엘보·티·레듀서 등의 국부손실 계수(K)를 정의한다.
core(해석 엔진)·db(라이브러리)·gui(입력 다이얼로그)가 모두 이 표를 참조한다.

정본 키는 GUI 입력 다이얼로그가 쓰는 소문자 키(elbow_90, valve_gate, ...)이며,
명세/기존 DSL 의 대문자 표기(ELBOW90, GATE_VALVE, ...)는 별칭으로 호환한다.

K-factor 출처: Crane TP-410 / 일반 수리편람 대표값.
"""
from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Tuple

# 정본 부속 키(소문자) → (K, 설명)
FITTINGS: Dict[str, Tuple[float, str]] = {
    # 배관 피팅재
    "elbow_90":        (0.90, "90도 엘보"),
    "elbow_45":        (0.40, "45도 엘보"),
    "tee_straight":    (0.60, "정티(직선통과)"),
    "tee_branch":      (1.80, "분기티(분기통과)"),
    "tee_reducing":    (1.20, "이경티"),
    "reducer":         (0.50, "리듀서/확대관"),
    "reducer_ecc":     (0.50, "편심 리듀서"),
    "union":           (0.08, "유니온"),
    "coupling":        (0.08, "소켓/커플링"),
    "cap_plug":        (0.00, "캡/플러그(폐단)"),
    # 밸브류
    "valve_gate":      (0.20, "게이트 밸브"),
    "valve_globe":     (10.0, "글로브 밸브"),
    "valve_ball":      (0.05, "볼 밸브"),
    "valve_butterfly": (0.60, "버터플라이 밸브"),
    "valve_plug":      (0.34, "플러그 밸브(직통, 18·fT)"),
    "valve_diaphragm": (2.30, "다이어프램 밸브(위어형)"),
    "valve_needle":    (5.00, "니들 밸브"),
    "valve_check":     (2.50, "체크 밸브"),
    "valve_foot":      (1.50, "풋 밸브"),
    "valve_relief":    (2.00, "안전/릴리프 밸브"),
    "valve_prv":       (2.00, "감압밸브(PRV)"),
    "valve_solenoid":  (3.00, "솔레노이드 밸브"),
    "valve_air":       (0.00, "에어 릴리스 밸브"),
    "valve_drain":     (0.20, "드레인 밸브"),
    "sample_valve":    (0.20, "샘플링 밸브"),
    # 플랜지·연결류
    "flange_joint":    (0.00, "플랜지 조인트"),
    "insul_flange":    (0.00, "절연 플랜지"),
    "expansion_joint": (0.30, "신축이음(벨로즈)"),
    "flexible_joint":  (0.30, "가요성 이음"),
    "strainer_y":      (2.00, "스트레이너(Y형)"),
    "strainer_basket": (1.50, "스트레이너(바스켓)"),
    # 계기·기타
    "pressure_gauge":  (0.00, "압력계"),
    "flow_meter":      (0.50, "유량계"),
    "thermometer":     (0.00, "온도계"),
    "sight_glass":     (0.30, "사이트 글라스"),
    # 경계 손실
    "entrance":        (0.50, "입구 손실"),
    "exit":            (1.00, "출구 손실"),
}

# 정본 부속 키 → 도면 기호 ID (drawing.symbols 에서 정의). 기호표 기준:
# ISO 6412-2 아이소메트릭 배관 기호(밸브=나비넥타이형, 계기=원형 태그).
# 없는 키는 도면에 기호를 그리지 않는다(엘보·티는 경로 꺾임/분기에서 자동 표시).
FITTING_SYMBOLS: Dict[str, str] = {
    "reducer": "reducer", "reducer_ecc": "reducer_ecc", "union": "union", "coupling": "coupling",
    "cap_plug": "cap",
    "valve_gate": "valve_gate", "valve_globe": "valve_globe",
    "valve_ball": "valve_ball", "valve_butterfly": "valve_butterfly",
    "valve_plug": "valve_plug", "valve_diaphragm": "valve_diaphragm",
    "valve_needle": "valve_needle", "valve_check": "valve_check",
    "valve_foot": "valve_check", "valve_relief": "valve_relief",
    "valve_prv": "valve_prv", "valve_solenoid": "valve_solenoid",
    "valve_air": "valve_air", "valve_drain": "valve_gate",
    "sample_valve": "valve_needle",
    "flange_joint": "flange", "insul_flange": "flange",
    "expansion_joint": "expansion_joint", "flexible_joint": "expansion_joint",
    "strainer_y": "strainer", "strainer_basket": "strainer",
    "pressure_gauge": "inst_pi", "flow_meter": "inst_fe",
    "thermometer": "inst_ti", "sight_glass": "sight_glass",
}

# 별칭(대문자/대체 표기) → 정본 키
_ALIASES: Dict[str, str] = {
    "ELBOW90": "elbow_90", "ELBOW45": "elbow_45",
    "TEE_THROUGH": "tee_straight", "TEE_STRAIGHT": "tee_straight",
    "TEE_BRANCH": "tee_branch",
    "GATE_VALVE": "valve_gate", "GLOBE_VALVE": "valve_globe",
    "BALL_VALVE": "valve_ball", "CHECK_VALVE": "valve_check",
    "PLUG_VALVE": "valve_plug", "DIAPHRAGM_VALVE": "valve_diaphragm", "ECC_REDUCER": "reducer_ecc",
    "FOOT_VALVE": "valve_foot",
    "REDUCER": "reducer", "ENTRANCE": "entrance", "EXIT": "exit",
}


def _canonical(name: str) -> str:
    key = name.strip()
    if key in FITTINGS:
        return key
    low = key.lower()
    if low in FITTINGS:
        return low
    up = key.upper()
    if up in _ALIASES:
        return _ALIASES[up]
    if low in _ALIASES:
        return _ALIASES[low]
    return ""


def fitting_k(name: str) -> float:
    """부속 1개의 K값 (미정의 시 0.0). 정본 키·별칭·대소문자 모두 허용."""
    canon = _canonical(name)
    return FITTINGS[canon][0] if canon else 0.0


# 항목 토큰: elbow_90 / elbow_90*2 / 2*elbow_90 / elbow_90 x2 / elbow_90:2
# 위치(선택): elbow_90@2m / valve_gate@1500mm / valve_gate@50% (배관 시작점 기준)
_COUNT_RE = re.compile(
    r"^\s*(?:(\d+)\s*[\*xX]\s*)?([A-Za-z_]\w*)(?:\s*[\*xX:]\s*(\d+))?"
    r"\s*(?:@\s*([+-]?[\d.]+)\s*(m|mm|%)?)?\s*$"
)


def parse_fittings(spec: str) -> List[Tuple[str, int]]:
    """피팅 명세 문자열 → [(name, count), ...].

    래퍼는 대괄호 `[...]` 또는 중괄호 `{...}` 모두 허용(생략 가능).
    쉼표로 구분, 개수는 `N*NAME`·`NAME*N`·`NAME xN`·`NAME:N` 허용.
    이름의 대소문자는 보존하며 인식 불가 항목은 무시한다.
    """
    if not spec:
        return []
    s = spec.strip().strip("[]{}").strip()
    if not s:
        return []
    items: List[Tuple[str, int]] = []
    for raw in s.split(","):
        token = raw.strip()
        if not token:
            continue
        m = _COUNT_RE.match(token)
        if not m:
            continue
        pre, name, post = m.group(1), m.group(2), m.group(3)
        count = int(pre or post or 1)
        items.append((name, max(count, 1)))
    return items


class FittingPlacement(NamedTuple):
    name: str                       # 입력 표기(대소문자 보존)
    canon: str                      # 정본 키 ("" = 미정의)
    count: int
    at_m: Optional[float] = None    # 배관 시작점 기준 경로 거리(m)
    at_frac: Optional[float] = None  # 경로 길이 비율(0~1)


def parse_fitting_placements(spec: str) -> List[FittingPlacement]:
    """피팅 명세 → 위치 포함 목록. 위치 생략 시 at_m/at_frac 는 None."""
    if not spec:
        return []
    s = spec.strip().strip("[]{}").strip()
    out: List[FittingPlacement] = []
    for raw in s.split(","):
        m = _COUNT_RE.match(raw)
        if not raw.strip() or not m:
            continue
        pre, name, post, pos, unit = m.groups()
        at_m = at_frac = None
        if pos is not None:
            v = float(pos)
            if unit == "%":
                at_frac = min(max(v / 100.0, 0.0), 1.0)
            else:
                at_m = v / 1000.0 if unit == "mm" else v
        out.append(FittingPlacement(name, _canonical(name), max(int(pre or post or 1), 1),
                                    at_m, at_frac))
    return out


def fitting_symbol(name: str) -> str:
    """부속의 도면 기호 ID ("" = 기호 없음)."""
    return FITTING_SYMBOLS.get(_canonical(name), "")


def sum_fittings_k(spec: str) -> float:
    """피팅 명세 문자열의 총 K 합산."""
    return sum(fitting_k(name) * count for name, count in parse_fittings(spec))


def elbow_k_for_angle(angle_deg: float) -> float:
    """경로 꺾임각으로 엘보 K를 추정한다 (auto_k 용).

    0°(직선)≈0, 45°≈45도 엘보, 90°이상≈90도 엘보. 사이값은 선형 보간.
    """
    a = abs(angle_deg)
    k45 = fitting_k("elbow_45")
    k90 = fitting_k("elbow_90")
    if a < 10.0:
        return 0.0
    if a <= 45.0:
        return k45 * (a / 45.0)
    if a >= 90.0:
        return k90
    return k45 + (k90 - k45) * ((a - 45.0) / 45.0)
