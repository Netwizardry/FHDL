"""표준 부속류(fitting) K-factor 단일 진실원.

배관에 부착되는 밸브·엘보·티·레듀서 등의 국부손실 계수(K)를 정의한다.
core(해석 엔진)와 db(라이브러리)가 모두 이 표를 참조하여 중복 정의를 막는다.

K-factor 출처: Crane TP-410 / 일반 수리편람 대표값.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# 부속 타입 → (K, 설명)
FITTINGS: Dict[str, Tuple[float, str]] = {
    "ELBOW90":     (0.90, "90도 엘보"),
    "ELBOW45":     (0.45, "45도 엘보"),
    "TEE_BRANCH":  (1.80, "티 분기"),
    "TEE_THROUGH": (0.60, "티 직통"),
    "GATE_VALVE":  (0.20, "게이트 밸브"),
    "GLOBE_VALVE": (10.0, "글로브 밸브"),
    "CHECK_VALVE": (2.50, "체크 밸브"),
    "REDUCER":     (0.50, "리듀서"),
    "ENTRANCE":    (0.50, "입구 손실"),
    "EXIT":        (1.00, "출구 손실"),
}


def fitting_k(name: str) -> float:
    """부속 1개의 K값 (미정의 시 0.0)."""
    entry = FITTINGS.get(name.strip().upper())
    return entry[0] if entry else 0.0


# 항목 토큰: ELBOW90 / ELBOW90*2 / 2*ELBOW90 / ELBOW90 x2
_COUNT_RE = re.compile(
    r"^\s*(?:(\d+)\s*[\*xX]\s*)?([A-Za-z_]\w*)(?:\s*[\*xX]\s*(\d+))?\s*$"
)


def parse_fittings(spec: str) -> List[Tuple[str, int]]:
    """`[ELBOW90, GATE_VALVE, ELBOW90*2]` → [('ELBOW90',1),('GATE_VALVE',1),('ELBOW90',2)].

    대괄호는 선택. 쉼표로 구분. 개수 표기는 `N*NAME`, `NAME*N`, `NAME xN` 허용.
    인식 불가 항목은 무시한다.
    """
    if not spec:
        return []
    s = spec.strip().strip("[]")
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
        items.append((name.upper(), max(count, 1)))
    return items


def sum_fittings_k(spec: str) -> float:
    """피팅 명세 문자열의 총 K 합산."""
    return sum(fitting_k(name) * count for name, count in parse_fittings(spec))


# 꺾임각(도) → 엘보 K 추정 (auto_k 용)
def elbow_k_for_angle(angle_deg: float) -> float:
    """경로 꺾임각으로 엘보 K를 추정한다.

    0°(직선)≈0, 45°≈ELBOW45, 90°이상≈ELBOW90. 사이값은 선형 보간.
    """
    a = abs(angle_deg)
    k45 = FITTINGS["ELBOW45"][0]
    k90 = FITTINGS["ELBOW90"][0]
    if a < 10.0:
        return 0.0
    if a <= 45.0:
        return k45 * (a / 45.0)
    if a >= 90.0:
        return k90
    return k45 + (k90 - k45) * ((a - 45.0) / 45.0)
