# 09. 언어 및 문법 (Language & Syntax) 명세

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL은 유체 설비의 구성과 연결 관계를 기술하기 위한 **선언형(Declarative)** 및 **구조형(Structured)** 도메인 특화 언어입니다.

## 1. 문법 설계 원칙

*   **선언 우선:** "어떻게 계산할지"가 아닌 "무엇이 있고 어떻게 연결되는지"를 기술합니다.
*   **블록 구조:** `<유형> <ID> { <속성> = <값>; }` 형태의 블록 구조를 가집니다.
*   **연결 분리:** 구성요소의 속성 정의와 네트워크 위상(Topology) 정의를 분리합니다.
*   **단위 통합:** 값과 단위를 결합하여 표기함으로 해석 오류를 방지합니다.

## 2. DSL-to-Entity 매핑 규범 (Mapping Rules)

파싱된 DSL 블록은 다음 규칙에 따라 내부 데이터 모델(`10_MODELS.md`)의 엔티티로 정규화된다.

| DSL 키워드 | 내부 엔티티 (Class) | 주요 속성 매핑 | 비고 |
| :--- | :--- | :--- | :--- |
| **`system`** | `FluidSystem` | `unit_system`, `fluid`, `temp` | 전역 컨텍스트 |
| **`tank`** | `Tank` | `volume`, `level_max`, `elevation` | 공급원/저장소 |
| **`source`** | `Tank` | `type='source'`, `elevation` | 무한 공급원 |
| **`pump`** | `Pump` | `flow`, `head`, `efficiency` | 가압 장치 |
| **`pipe`** | `Pipe` | `length`, `diameter`, `material` | 연결 배관 |
| **`nozzle`** | `Terminal` | `type='nozzle'`, `flow`, `k_factor` | 유량 소모 말단 |
| **`sprinkler`**| `Terminal` | `type='sprinkler'`, `required_p` | 압력 기준 말단 |
| **`component`**| `Component` | `loss_k`, `type='custom'` | 범용 기기 |

### 2.1 [S-DSL-001] 산정 모드(Sizing Mode) 정규화
각 수치 속성은 다음 세 가지 모드를 가지며, 내부 모델의 `SizingState` 필드로 변환된다.
*   **`manual` (고정값):** 사용자가 직접 입력한 값. 계산 엔진은 이를 상수로 취급한다. (예: `diameter = 50mm;`)
*   **`auto` (자동산정):** 시스템이 설계 제약에 따라 결정할 값. 내부적으로 `None` 또는 `Pending` 상태로 초기화된다. (예: `diameter = auto;`)
*   **`derived` (유도값):** 타 속성으로부터 물리적으로 유도되는 값. (예: `flow = derived;`)

## 3. 세부 문법 명세 (Detailed Syntax)

### 3.1 [S-DSL-002] `system` 블록 및 마찰 모델 설정
```fhdl
system my_project {
    unit_system = METRIC;
    fluid = water;
    temp = 25.0degC;
    friction_model = DW; // DW(Darcy-Weisbach) 또는 HW(Hazen-Williams)
}
```

### 3.2 [S-DSL-003] 배관 및 마찰 파라미터
```fhdl
pipe p1 {
    length = 10.5m;
    diameter = auto; // 관경 자동 산정 요청
    material = "PVC";
    roughness = 0.01mm; // DW용 조도
    c_factor = 140;     // HW용 C-계수
}
```

## 4. 템플릿 및 재사용 (Reusability)

### 4.1 [S-DSL-004] `template` 정의 및 `instance` 호출
반복되는 설비 군을 하나의 템플릿으로 정의하여 재사용할 수 있다.

**정의 문법:**
```fhdl
template sprinkler_branch(id_prefix, flow_val) {
    pipe ${id_prefix}_p { length = 2m; diameter = auto; }
    sprinkler ${id_prefix}_s { flow = ${flow_val}; }
    connect ${id_prefix}_p -> ${id_prefix}_s;
}
```

**호출 문법:**
```fhdl
instance branch_1 = sprinkler_branch("B1", 15Lpm);
instance branch_2 = sprinkler_branch("B2", 15Lpm);
```

### 4.2 [S-DSL-005] 범위 연결(Range Connection)
```fhdl
connect main_pipe -> branch_1..branch_10; // 다중 연결 단축 표기
```

---
[목차로 돌아가기](./INDEX.md)
