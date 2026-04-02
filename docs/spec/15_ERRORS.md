# 16. 오류 처리 및 진단 메시지 명세

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL 프로그램은 입력, 검증, 구조 해석, 수리 계산 및 결과 생성의 모든 단계에서 발생하는 문제와 경고를 구조화된 진단 정보로 생성하여 사용자에게 제시해야 합니다.

## 1. 진단 기본 원칙

*   **구조화 (Structured):** 모든 오류는 자유 문자열이 아닌 코드, 분류, 심각도, 위치 정보가 포함된 객체로 관리됩니다.
*   **단계별 분류:** 발생한 처리 단계(Syntax, Semantic, Network, Calc, Rules)에 따라 명확히 구분됩니다.
*   **수정 가능성 (Actionable):** 단순히 실패를 알리는 것이 아니라, 사용자가 무엇을 확인하고 수정해야 하는지 구체적인 힌트를 제공합니다.
*   **추적성 (Traceability):** 모든 오류는 원문 소스 코드의 정확한 위치(Line, Column)와 연결되어야 합니다.

## 2. 진단 분류 및 코드 체계

진단 코드는 영역별 접두어와 3자리 숫자로 구성됩니다.

| 접두어 | 분류 (Category) | 설명 |
| :--- | :--- | :--- |
| **SYN** | Syntax | 토큰화 및 구문 분석 단계의 문법적 오류 |
| **SEM** | Semantic | 식별자 중복, 참조 누락, 속성 타입 불일치 등 의미적 오류 |
| **NET** | Network | 배관 연결 단절, 고립 노드, 공급원 없는 경로 등 위상적 결함 |
| **CAL** | Calculation | 계산 필수값 부족, 수렴 실패, 표준 관경 탐색 실패 등 계산 오류 |
| **WRN** | Warning | 설계 제약 이탈(과속, 저압), 기본값 적용 등 주의가 필요한 상태 |

## 3. 심각도 (Severity) 명세

*   **INFO:** 단순 참고용 정보. 실행에 지장이 없음. (예: 자동 산정값 적용 알림)
*   **WARNING:** 계산은 계속 가능하나 사용자의 검토가 필요한 상태. (예: 유속 권장 범위 이탈)
*   **ERROR:** 현재 단계의 해석을 중단하며 다음 단계로 진행 불가. (예: 필수 속성 누락)
*   **FATAL:** 시스템 오류 또는 모델 손상으로 전체 처리를 중단.

## 4. 진단 데이터 구조 (Diagnostic Object)

각 진단 항목은 내부적으로 다음 정보를 포함합니다.

| 필드명 | 타입 | 설명 |
| :--- | :--- | :--- |
| `code` | `str` | 고정된 진단 코드 (예: SEM003) |
| `severity` | `enum` | INFO, WARNING, ERROR, FATAL |
| `message` | `str` | 사용자 표시용 핵심 에러 메시지 |
| `source_span` | `obj` | 원문 내 위치 (start/end line & column) |
| `related_id` | `str` | 문제가 발생한 구성요소 ID (예: pipe p1) |
| `suggested_action` | `str` | 해결을 위해 설계자가 취해야 할 조치 가이드 |

## 5. 상세 진단 코드 명세 (Diagnostic Catalog)

### 5.1 Syntax Errors (SYN)
*   **SYN001 (Unexpected Token):** 문법에 맞지 않는 토큰 발견.
    *   *Action:* 해당 라인의 오타나 누락된 `;` 또는 `{`를 확인하세요.
*   **SYN002 (Invalid Unit):** 지원하지 않는 단위 사용.
    *   *Action:* `08. LANGUAGE.md`에 명시된 표준 단위(m, LPM, MPa 등)를 사용하세요.

### 5.2 Semantic Errors (SEM)
*   **[S-ERR-001] SEM001~003:** 중복 ID, 참조 누락, 필수 속성 누락 (기존 유지).
*   **[S-ERR-002] SEM005 (Altitude Guard):** 노드 고도가 허용 범위를 벗어남 ($-100 \sim 10000m$).
    *   *Remedy:* 실제 지형 고도 또는 상대 고도를 범위 내로 조정하세요.
*   **[S-ERR-003] SEM006 (Temperature Guard):** 유체 온도가 허용 범위를 벗어남 ($0 \sim 100^\circ C$).
    *   *Remedy:* `system` 블록의 `temp` 설정을 상온 범위로 수정하세요.
*   **[S-ERR-004] SEM007 (Length Guard):** 배관 길이가 0 이하거나 유효하지 않음.
    *   *Remedy:* 배관의 `length` 속성에 양수 값을 입력하세요.

### 5.3 Network Errors (NET)
*   **[S-ERR-005] NET001~003:** 고립 노드, 공급원 없음, 도달 불가 (기존 유지).
*   **[S-ERR-006] NET004 (Complex Loop Warning):** v0.1에서 지원하지 않는 복합 루프망 탐지.
    *   *Remedy:* 병렬 배관 이외의 루프 구조를 단순 트리형으로 수정하거나 v0.2 업그레이드를 대기하세요.
*   **[S-ERR-007] NET005 (Dead Loop Error):** 공급원 없는 순환 루프 발견.
    *   *Remedy:* 루프를 끊거나 반드시 외부 공급원(`Tank/Source`)과 연결하세요.

### 5.4 Calculation Errors (CAL)
*   **[S-ERR-008] CAL001 (Missing Data for Calculation):** 계산에 필요한 데이터(밀도, 점도, 마찰계수 등)를 도출할 수 없음. (조건: 물리적 상수 평가 실패, Action: 유체 온도나 파이프 재질을 올바르게 설정하세요, Pipeline: Calculation)
*   **CAL002 (Convergence Failure):** 유량/압력 계산 루프가 최대 반복 횟수 내에 수렴하지 않음. (조건: Newton-Raphson 최대 반복 도달, Action: 네트워크 구조를 단순화하거나 초기값을 조정하세요, Pipeline: Calculation)
*   **CAL003 (Invalid Operation):** 0으로 나누기 등의 수학적 연산 오류. (조건: 유량 0 상태에서의 마찰 손실 등, Action: 비정상적인 파라미터나 0값을 확인하세요, Pipeline: Calculation)
*   **[S-ERR-009] CAL005 (Sizing Failed):** 모든 표준 관경 규격이 유속 제약조건을 위반함.
    *   *Remedy:* `velocity_max` 제한을 완화하거나 요구 유량을 줄이세요.

### 5.5 Design Warnings (WRN)
*   **[S-ERR-010] WRN001 (Velocity Violation):** 계산된 유속이 권장/제약 범위를 벗어남. (조건: V < V_min 또는 V > V_max, Severity: WARNING, Action: 관경을 조정하거나 유량을 변경하세요, Pipeline: Rules)
*   **WRN002 (Low Pressure):** 노드의 압력이 요구 압력(P_req)보다 낮음. (조건: P_actual < P_req, Severity: WARNING, Action: 펌프 양정을 키우거나 마찰 손실을 줄이세요, Pipeline: Rules)
*   **WRN003 (Cavitation Risk):** 펌프 흡입측 유효흡입수두(NPSHa)가 요구치(NPSHr)보다 부족함. (조건: NPSHa < NPSHr * 1.1, Severity: WARNING, Action: 수조 수위를 높이거나 흡입관의 손실을 줄이세요, Pipeline: Rules)
*   **WRN005 (Vacuum Limit):** 계산된 압력이 진공 한계치(-1.0e5 Pa)에 도달함. (조건: P <= -100,000 Pa, Severity: WARNING, Action: 극단적인 부압 원인(수두 차, 마찰)을 확인하세요, Pipeline: Rules)
*   **[S-ERR-011] WRN004 (High Surge Risk):** 정상상태 유속 기반 수격 위험 지수 초과.
    *   *Remedy:* 유속을 낮추기 위해 관경을 키우거나 밸브 폐쇄 시간을 조절하세요.

---
[목차로 돌아가기](./INDEX.md)
