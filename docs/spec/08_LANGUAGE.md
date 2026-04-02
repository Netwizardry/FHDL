# 09. 언어 및 문법 (Language & Syntax) 명세

FHDL은 유체 설비의 구성과 연결 관계를 기술하기 위한 **선언형(Declarative)** 및 **구조형(Structured)** 도메인 특화 언어입니다.

## 1. 문법 설계 원칙

*   **선언 우선:** "어떻게 계산할지"가 아닌 "무엇이 있고 어떻게 연결되는지"를 기술합니다.
*   **블록 구조:** `<유형> <ID> { <속성> = <값>; }` 형태의 블록 구조를 가집니다.
*   **연결 분리:** 구성요소의 속성 정의와 네트워크 위상(Topology) 정의를 분리합니다.
*   **단위 통합:** 값과 단위를 결합하여 표기함으로 해석 오류를 방지합니다.

## 2. 상위 구성요소 (Top-level Blocks)

### 2.1 `system` (최상위 블록)
설계 프로젝트의 메타데이터와 전역 설정을 정의합니다.
*   **속성:** 
    *   `unit_system`: `METRIC` | `IMPERIAL`
    *   `fluid`: `water` | `brine` (기본값: water)
    *   `temp`: 유체 온도 (기본값: 20.0)
    *   `friction_model`: `DW` (Darcy-Weisbach) | `HW` (Hazen-Williams) - **필수 선택**
*   **예시:**
    ```fhd
    system demo_project {
        unit_system = METRIC;
        fluid = water;
        friction_model = DW;
    }
    ```

### 2.2 `source` / `tank` (수원)
*   `source`: 외부 급수원 등 추상적 수원.
*   `tank`: 실제 용량 산정 대상인 저수조.
*   **속성:** `volume`, `level_min`, `level_max`, `elevation`.

### 2.3 `pump` (가압 장치)
*   **속성:** `flow`, `head`, `elevation`, `efficiency`, `power`.
*   **특징:** `flow`와 `head`를 `auto`로 설정하여 시스템 요구치에 맞는 사양을 자동 산정할 수 있습니다.

### 2.4 `pipe` (배관)
*   **속성:** 
    *   `length` (필수): 배관 길이.
    *   `diameter`: `auto` | 고정값.
    *   `material`: 재질 식별자.
    *   `loss_k`: 국부 손실 계수.
    *   **[물리 모델별 전용 속성]**
        *   `roughness` (DW 전용): 절대 거칠기 ($\epsilon$, mm 단위).
        *   `c_factor` (HW 전용): 마찰 계수 ($C$, 무차원).
*   **제약:** `friction_model`이 `DW`일 때 `c_factor` 사용 시 `SEM004` 에러 발생. (자의적 변환 금지)
*   **특징:** `diameter = auto;` 설정 시 허용 유속 범위 내에서 관경을 자동 선정합니다.

### 2.5 `nozzle` / `sprinkler` (말단 장치)
*   **속성:** `flow`, `required_pressure`, `jet_height` (노즐 전용), `count`.
*   **특징:** 분수 노즐의 경우 `jet_height`를 입력하면 필요한 유량과 압력을 역산합니다.

### 2.6 `junction` (분기/합류점)
*   **속성:** `type` (split, merge), `loss_k`, `elevation`.
*   **특징:** 복잡한 네트워크 구조에서 명시적으로 분기점을 정의할 때 사용합니다.

### 2.7 `constraint` (설계 제약조건)
*   **속성:** `velocity_min`, `velocity_max`, `safety_factor`, `tank_runtime_min`.
*   **특징:** 전역 또는 국소 설계 규칙을 정의하며, 자동 산정 엔진의 판단 기준이 됩니다.

## 3. 위상 정의 (Connections)

### 3.1 `connect` 문
`->` 연산자를 사용하여 구성요소 간의 상류-하류 관계를 정의합니다.
*   **단일 경로:** `connect tank_1 -> pump_1 -> main_1 -> j1;`
*   **분기 경로:** 여러 개의 `connect` 문을 사용하여 트리 구조를 형성합니다.
    ```fhd
    connect j1 -> branch_1 -> n1;
    connect j1 -> branch_2 -> n2;
    ```
*   **범위 연결:** `..` 표기법으로 여러 말단에 동시 연결을 선언합니다.
    *   `connect main_1 -> n1..n10;`

## 4. 값 표현 및 산정 모드

### 4.1 값과 단위 (Value with Units)
모든 수치 데이터는 단위를 포함할 수 있으며, 파서는 이를 내부 표준 단위(SI)로 변환합니다.
*   **길이:** `50m`, `100mm`, `2ft`
*   **유량:** `60LPM`, `10GPM`, `1.5m3s`
*   **압력:** `2.0bar`, `0.5MPa`, `30psi`
*   **유속:** `1.5mps`, `5fps`

### 4.2 산정 모드 (Sizing Modes)
*   **`manual` (값 지정):** 사용자가 명시한 고정값을 사용합니다. (예: `diameter = 50mm;`)
*   **`auto` (자동 산정):** 시스템이 설계 제약조건에 맞춰 최적값을 계산합니다. (예: `flow = auto;`)
*   **`derived` (유도):** 다른 속성으로부터 자동으로 유도되는 값임을 명시합니다.

## 5. 반복 및 범위 선언 (Loops & Ranges)

실무에서의 대량 반복 선언을 위해 범위 문법을 지원합니다.
*   **ID 범위:** `nozzle n1 to n10 { ... }`
*   **수량 기반:** `sprinkler head_group { count = 12; ... }`

## 6. 템플릿 및 재사용 (Reusability - M01)

대규모 프로젝트의 반복되는 설비 구조를 효율적으로 정의하기 위해 템플릿 기능을 제공합니다.

### 6.1 `template` 정의
```fhd
template sprinkler_branch(id_prefix, elevation) {
    pipe {id_prefix}_p1 { length = 10m; diameter = auto; }
    sprinkler {id_prefix}_s1 { elevation = {elevation}; flow = 80LPM; }
    connect {id_prefix}_p1 -> {id_prefix}_s1;
}
```

### 6.2 `instance` 사용
```fhd
instance b1: sprinkler_branch("b1", 2.5m);
instance b2: sprinkler_branch("b2", 5.0m);
```

### 6.3 템플릿 매핑 규칙
*   **ID 치환:** `{id_prefix}` 변수는 인스턴스 생성 시 전달된 문자열로 치환되어 고유 ID를 형성합니다.
*   **속성 주입:** 템플릿 내의 속성값은 인스턴스 인자를 통해 동적으로 결정됩니다.

---
[목차로 돌아가기](./INDEX.md)
