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

AST를 실제 설계 객체로 변환하고 단위 정규화 및 참조 해결이 완료된 상태이다.

#### [S-MOD-001] 엔티티 필드 상세 명세 (Entity Specifications)

| Entity | 필드명 | 필수 | 타입 | 제약 조건 (SI 단위 기준) | 기본값 |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **Tank** | `elevation` | Y | float | $-100 \sim 10000 m$ | 0.0 |
| | `volume` | N | float | $> 0 m^3$ | `INF` |
| | `level_max` | N | float | $> 0 m$ | 2.0 |
| **Pump** | `elevation` | Y | float | $-100 \sim 10000 m$ | 0.0 |
| | `flow` | N | float | `SizingMode` (auto/manual) | `auto` |
| | `head` | N | float | `SizingMode` (auto/manual) | `auto` |
| | `efficiency` | N | float | $0.1 \sim 1.0$ | 0.75 |
| **Pipe** | `length` | Y | float | $> 0 m$ | - |
| | `diameter` | N | float | `SizingMode` (auto/manual) | `auto` |
| | `material` | N | string | `APPENDIX_A` 참조 | "Steel" |
| | `roughness` | N | float | $> 0 mm$ (DW용) | 0.045 |
| | `c_factor` | N | float | $50 \sim 150$ (HW용) | 120 |
| **Terminal** | `elevation` | Y | float | $-100 \sim 10000 m$ | 0.0 |
| | `required_q` | N | float | $\ge 0 m^3/h$ | 0.0 |
| | `required_p` | N | float | $\ge 0 Pa$ (Gauge) | 0.0 |
| | `k_factor` | N | float | $\ge 0$ | - |

#### [S-MOD-002] 산정 상태 모델 (SizingState)
모든 가변 수치 속성(`flow`, `head`, `diameter` 등)은 내부적으로 다음 구조를 가진다.
*   **`mode`:** `MANUAL` (사용자 고정), `AUTO` (시스템 산정), `DERIVED` (물리적 유도).
*   **`value`:** 현재 할당된 SI 수치값.
*   **`source_id`:** `AUTO`인 경우 선정을 결정한 제약조건 ID (예: `R-NFR-008`).

### 2.3 Network Model (Calculation Graph)

#### [S-MOD-003] 네트워크 노드 및 엣지 속성
*   **NetworkNode:**
    *   `z`: 정수두 (m).
    *   `h_total`: 총 수두 (m).
    *   `p_gauge`: 게이지 압력 (Pa).
    *   `is_boundary`: 경계 조건 노드 여부 (Source/Terminal).
*   **NetworkEdge:**
    *   `q_actual`: 실제 흐르는 유량 ($m^3/h$).
    *   `v_actual`: 실제 유속 ($m/s$).
    *   `h_loss_f`: 마찰 손실 수두 (m).
    *   `h_loss_k`: 국부 손실 수두 (m).

### 2.4 [S-MOD-004] 데이터 출처 모델 (Provenance Model)
계산 결과의 투명성을 위해 각 결과값은 `ProvenanceItem`을 보유한다.
*   **`formula_id`:** 사용된 계산 공식 ID (예: `FOR-DW-001`).
*   **`input_references`:** 계산에 입력된 엔티티 ID 및 필드 목록.
*   **`assumptions`:** 적용된 엔지니어링 기본값(Default) 목록.

### 2.4 Calculation Model (Calc States)
각 실행 시점의 계산 상태를 저장하며, 입력 모델과 분리하여 관리합니다.
*   **SegmentCalcState:** 유량, 선정 관경, 유속, 마찰/국부 손실 합계.
*   **SystemCalcState:** 시스템 총유량, 총 요구양정, 최불리 경로 ID, 권장 사양 요약.

## 3. 진단 및 오류 모델 (Diagnostics)

... (기존 내용 유지)

---
[목차로 돌아가기](./INDEX.md)
