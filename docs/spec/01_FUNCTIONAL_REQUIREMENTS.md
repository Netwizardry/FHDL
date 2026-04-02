# 02. 핵심 기능 요구사항 (Functional Requirements)

FHDL 시스템은 설계자의 의도를 해석하여 물리적으로 타당한 설비 사양을 자동으로 도출하기 위해 다음과 같은 기능을 수행해야 합니다. (A04: 입출력 조건 중심 명세)

## 1. 설계 입력 및 문법 검증 (Input & Validation)

### 1.1 설계 기술 기능
*   **시스템 선언:** 
    *   **Input:** 단위계(Metric/Imperial), 유체 종류, 온도 등.
    *   **Process:** 전역 환경 변수를 설정하고 단위 변환 엔진 초기화.
    *   **Output:** SI 표준 단위로 정규화된 시스템 컨텍스트.
*   **구성요소 및 위상 선언:**
    *   **Input:** ID, 타입, 속성, `connect` 문.
    *   **Process:** 식별자 등록 및 연결 관계를 인접 리스트로 변환.
    *   **Output:** 추상 구문 트리(AST) 및 초기 엔티티 맵.

### 1.2 문법 및 논리 검증 기능
*   **구문/참조 검증:**
    *   **Input:** AST 및 식별자 맵.
    *   **Process:** 중복 ID 검사 및 존재하지 않는 ID 참조 여부 확인.
    *   **Output:** `SYN`, `SEM` 계열 진단 메시지.
*   **연결성 검사:**
    *   **Input:** 네트워크 그래프 모델.
    *   **Process:** 소스에서 터미널까지의 경로 존재 여부(Reachability) 확인.
    *   **Output:** `NET` 계열 진단 메시지 (고립 노드, 경로 단절 등).

## 2. 구조 해석 및 수리 계산 (Analysis & Calculation)

### 2.1 수리 계산 (Pass 1: Synthesis)
*   **Input:** 말단 장치 요구 유량($Q_{req}$), 네트워크 위상.
*   **Process:** 하류에서 상류로 유량을 누적 합산 ($Q_{up} = \sum Q_{down}$).
*   **Output:** 구간별 설계 유량($Q_{design}$).

### 2.2 수리 계산 (Pass 2: Verification)
*   **Input:** 구간 유량, 관경, 재질(거칠기), 고도차.
*   **Process:** Darcy-Weisbach 식을 사용하여 손실수두($h_f$) 산정 및 노드별 수두($H$) 평형 계산.
*   **Output:** 노드별 압력($P$), 배관별 유속($V$) 및 손실수두.

## 3. 자동 산정 및 결과 출력 (Sizing & Output)

### 3.1 배관경 자동 산정 (Auto-Sizing)
*   **Input:** 구간 설계 유량, 설계 제약(허용 유속 범위 $V_{min} \sim V_{max}$), 표준 관경 테이블.
*   **Process:** 허용 유속 범위를 만족하는 최소 표준 관경 탐색.
*   **Output:** 선정 관경($D_{selected}$) 및 선정 근거 메시지.

### 3.2 펌프 사양 산정
*   **Input:** 시스템 총 유량, 최불리 경로 총 요구 수두, 안전율.
*   **Process:** $H_{pump} = H_{req, total} \times SafetyFactor$ 계산.
*   **Output:** 권장 펌프 유량($Q_p$) 및 양정($H_p$).

## 4. 결과 리포팅 및 경고
*   **Input:** 계산 완료된 `FluidSystem` 모델.
*   **Process:** 설계 제약(과속, 저압, 캐비테이션 등) 위반 여부 판정.
*   **Output:** 상세 결과 리포트 및 `WRN` 계열 경고 메시지.

---
[목차로 돌아가기](./INDEX.md)
