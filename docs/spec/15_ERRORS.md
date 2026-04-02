# 16. 오류 처리 및 진단 메시지 명세

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
*   **SEM001 (Duplicate ID):** 동일한 식별자가 중복 선언됨.
    *   *Action:* 구성요소의 ID를 고유하게 수정하세요.
*   **SEM002 (Undefined Reference):** 존재하지 않는 ID를 참조함.
    *   *Action:* `connect` 문에 사용된 ID가 위에서 정의되었는지 확인하세요.
*   **SEM003 (Missing Property):** 필수 속성(예: pipe의 length)이 누락됨.
    *   *Action:* 해당 구성요소의 필수 속성을 입력하세요.

### 5.3 Network Errors (NET)
*   **NET001 (Isolated Node):** 어떤 연결도 없는 고립 노드 발견.
    *   *Action:* `connect` 문을 사용하여 네트워크에 포함시키거나 삭제하세요.
*   **NET002 (No Source Path):** 공급원(Tank/Source)에서 시작되지 않는 경로 존재.
    *   *Action:* 모든 배관은 반드시 수로나 펌프를 통해 공급원과 연결되어야 합니다.
*   **NET003 (Unreachable Terminal):** 말단 장치까지 도달할 수 없는 경로.
    *   *Action:* 연결 방향(`->`)이 올바른지 확인하세요.

### 5.4 Calculation Errors (CAL)
*   **CAL001 (Insufficient Data):** 계산에 필요한 수치가 부족함.
    *   *Action:* 유량이나 관경 등 최소 하나의 결정 변수가 필요합니다.
*   **CAL002 (No Sizing Solution):** 허용 유속을 만족하는 표준 관경을 찾을 수 없음.
    *   *Action:* 요구 유량을 줄이거나 유속 제한(`velocity_max`)을 완화하세요.
*   **CAL003 (Solver Divergence):** 수리 해석이 수렴하지 않고 발산함.
    *   *Action:* 네트워크에 루프가 있는지, 혹은 유량이 너무 극단적인지 확인하세요.

### 5.5 Design Warnings (WRN)
*   **WRN001 (Velocity Out of Range):** 유속이 권장 범위를 벗어남.
    *   *Action:* 관경을 조정하여 적정 유속(1.0~2.5m/s)을 유지하세요.
*   **WRN002 (Pressure Low):** 말단 요구압력보다 실제 압력이 낮음.
    *   *Action:* 펌프 양정을 높이거나 배관 손실을 줄이세요.
*   **WRN003 (Cavitation Risk):** 해당 지점의 압력이 증기압에 근접하여 캐비테이션 위험 발생.
    *   *Action:* 펌프 흡입측 손실을 줄이거나 펌프 고도를 낮추세요.

---
[목차로 돌아가기](./INDEX.md)
