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

### 2.2 `source` / `tank` (수원)
*   `source`: 외부 급수원 등 추상적 수원.
*   `tank`: 수위 동특성 및 월류를 지원하는 저수조.
*   **속성:** `volume`, `level_min`, `level_max`, `elevation`, `overflow_level`, `overflow_pipe`.

### 2.3 `pump` (가압 장치)
*   **속성:** `flow`, `head`, `elevation`, `efficiency`, `power`.
*   **특징:** `flow`와 `head`를 `auto`로 설정하여 시스템 요구치에 맞는 사양을 자동 산정할 수 있습니다.

### 2.4 `pipe` (배관)
*   **속성:** `length` (필수), `diameter`, `material`, `roughness`, `loss_k`, `c_factor`.

### 2.5 `nozzle` / `sprinkler` (말단 장치)
*   **속성:** `flow`, `required_p`, `k_factor`, `jet_height`, `count`.
*   **특징:** `k_factor` 입력 시 $Q = K\sqrt{P}$ 특성식으로 해석하며, 미입력 시 `flow`를 고정 요구량으로 취급합니다.

### 2.6 `component` (범용 구성요소 - M02)
정의되지 않은 특수 기기(열교환기, 감압밸브, 월류보 등)를 정의할 때 사용합니다.
*   **속성:** `type`, `loss_k` (고정 손실), `loss_curve` (유량별 손실 곡선), `boundary_p` (고정 압력 경계).

### 2.7 `constraint` (설계 제약조건)
*   **속성:** `velocity_min`, `velocity_max`, `safety_factor`, `tank_runtime_min`.

## 3. 위상 정의 (Connections)

### 3.1 `connect` 문 및 포트 선택자 (C01)
`->` 연산자를 사용하여 구성요소 간의 상류-하류 관계를 정의합니다.
*   **포트 선택자:** `.in`, `.out`을 통해 방향성 명시 가능.

### 3.2 분기 및 다중 연결
*   **범위 연결:** `connect main_1 -> n1..n10;` (다중 말단 동시 연결)

## 4. 값 표현 및 산정 모드

### 4.1 값과 단위 (Value with Units)
모든 수치 데이터는 단위를 포함할 수 있으며, 파서는 이를 내부 표준 단위(SI)로 변환합니다.

### 4.2 산정 모드 (Sizing Modes)
*   **`manual` / `auto` / `derived`** 지원.

## 5. 반복 및 범위 선언 (Loops & Ranges)
*   `nozzle n1 to n10 { ... }`

## 6. 템플릿 및 재사용 (Reusability - M01)

대규모 프로젝트의 반복되는 설비 구조를 효율적으로 정의하기 위해 템플릿 기능을 제공합니다.

### 6.1 `template` 정의 및 `instance` 사용
(상세 문법 생략 - 이전 작업 내용 유지)

---
[목차로 돌아가기](./INDEX.md)
