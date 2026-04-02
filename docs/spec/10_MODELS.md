# 11. 데이터 모델 및 내부 구조 명세

FHDL 프로그램은 입력 문법 처리, 의미 검증, 계산 수행, 결과 출력이 서로 독립적으로 유지될 수 있도록 계층적으로 분리된 데이터 모델을 사용합니다.

## 1. 데이터 모델 계층 구조

프로그램은 내부적으로 다음 6단계의 레이어를 거쳐 데이터를 처리합니다.

1.  **Source Layer:** 원본 FHDL 텍스트 및 메타데이터.
2.  **Syntax Layer:** 토큰화된 데이터 및 추상 구문 트리(AST).
3.  **Semantic Layer:** 의미 검증이 완료된 정규화 설비 객체(Entity).
4.  **Network Layer:** 계산용 노드-엣지 그래프 구조.
5.  **Calculation Layer:** 구간별 유량, 유속, 손실 등 계산 상태 데이터.
6.  **Reporting Layer:** 출력용 결과표, 요약, 진단(오류/경고) 정보.

## 2. 주요 레이어별 모델 상세

### 2.1 Syntax Model (AST)
파서가 생성하는 구조적 트리입니다.
*   **SystemNode:** 전역 설정 및 단위 정보.
*   **ComponentNode:** 설비 타입, ID, 속성 리스트.
*   **ConnectNode:** `->` 연산자로 연결된 경로 세그먼트.

### 2.2 Semantic Model (Entities)
AST를 실제 설계 객체로 변환하고 단위 정규화 및 참조 해결이 완료된 상태입니다. 모든 수치는 내부적으로 SI 표준 단위를 사용합니다.

#### [Entity 속성 제약 조건표 (A06/C01)]

| Entity | 필드명 | 필수 | 타입 | 허용 범위 (SI) | 기본값 |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **Tank** | `volume` | N | float | $> 0$ | 무제한 |
| | `elevation` | Y | float | -100 ~ 10000 | 0.0 |
| | `overflow_level` | N | float | $\le level_{max}$ | - |
| **Pump** | `flow` | N | float/auto | $\ge 0$ | `auto` |
| | `head` | N | float/auto | $\ge 0$ | `auto` |
| | `efficiency` | N | float | 0.0 ~ 1.0 | 0.75 |
| **Pipe** | `length` | Y | float | $> 0$ | - |
| | `diameter` | N | float/auto | $> 0$ | `auto` |
| | `roughness` | N | float | $> 0$ | 0.045 (Steel) |
| **Terminal** | `required_q` | N | float | $\ge 0$ | 0.0 |
| | `required_p` | N | float | $\ge 0$ | 0.0 |
| | `k_factor` | N | float | $\ge 0$ | 오리피스 특성 계수 |

*   **Nullable 정책:** '필수'가 N인 항목은 입력 누락 시 기본값이 적용되거나 `auto` 산정 로직으로 전이됩니다.
*   **ID 규칙:** 모든 엔티티는 시스템 내에서 유일한 문자열 ID를 가져야 합니다 (정규식: `^[a-zA-Z_][a-zA-Z0-9_]*$`).

### 2.3 Network Model (Calculation Graph - C02)
물리적 계산을 수행하기 위한 노드-엣지 정규화 모델입니다.

#### [수리적 정규화 규칙]
1.  **Node Responsibility:** 모든 `NetworkNode`는 해당 지점의 **정수두(Static Head, $z$)**와 **압력수두(Pressure Head, $P/\rho g$)**를 보유합니다.
2.  **Edge Responsibility:** 모든 `NetworkEdge` (배관)는 구간 내에서 발생하는 **마찰 손실($h_f$)**과 **국부 손실($h_k$)**을 계산하는 책임을 가집니다.
3.  **Virtual Node Injection:** 두 개의 배관이 직접 연결되는 경우, 시스템은 자동으로 그 사이에 `VirtualJunction` 노드를 생성합니다.

#### [수리적 경계 조건 (Boundary Conditions)]
*   **Fixed Head Node (Source/Tank):** 수두가 외부 조건에 의해 고정된 노드.
*   **Atmospheric Node (Weir/Overflow):** 압력이 항상 대기압(0 Pa Gauge)으로 유지되어야 하는 노드.
*   **Characteristic Node (Terminal):** $Q = K \sqrt{\Delta P}$ 비선형 특성식을 만족해야 하는 노드.

### 2.4 Calculation Model (Calc States)
각 실행 시점의 계산 상태를 저장하며, 입력 모델과 분리하여 관리합니다.
*   **SegmentCalcState:** 유량, 선정 관경, 유속, 마찰/국부 손실 합계.
*   **SystemCalcState:** 시스템 총유량, 총 요구양정, 최불리 경로 ID, 권장 사양 요약.

## 3. 진단 및 오류 모델 (Diagnostics)

... (기존 내용 유지)

---
[목차로 돌아가기](./INDEX.md)
