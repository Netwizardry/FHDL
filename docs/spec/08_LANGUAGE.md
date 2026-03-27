# 02. 언어 및 문법 (Language & Syntax) 명세

FHDL은 유체 설비의 구성과 연결 관계를 기술하기 위한 **선언형(Declarative)** 및 **구조형(Structured)** 도메인 특화 언어입니다.

## 1. 문법 설계 원칙

*   **선언 우선:** "어떻게 계산할지"가 아닌 "무엇이 있고 어떻게 연결되는지"를 기술합니다.
*   **블록 구조:** `<유형> <ID> { <속성> = <값>; }` 형태의 블록 구조를 가집니다.
*   **연결 분리:** 구성요소의 속성 정의와 네트워크 위상(Topology) 정의를 분리합니다.
*   **단위 통합:** 값과 단위를 결합하여 표기함으로 해석 오류를 방지합니다.

## 2. 상위 구성요소 (Top-level Blocks)

### 2.1 `system` (최상위 블록)
설계 프로젝트의 메타데이터와 전역 설정을 정의합니다.
*   **속성:** `unit_length`, `unit_flow`, `unit_pressure`, `fluid` (기본값: water).
*   **예시:**
    ```fhd
    system demo_project {
        unit_length = m;
        unit_flow = LPM;
        fluid = water;
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
*   **속성:** `length` (필수), `diameter`, `material`, `roughness`, `loss_k`.
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

---
[목차로 돌아가기](./INDEX.md)
