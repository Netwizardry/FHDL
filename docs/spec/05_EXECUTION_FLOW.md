# 06. 실행 흐름 및 상태 전이 명세

FHDL 프로그램은 설계자의 입력을 물리적 모델로 변환하고 계산 결과를 생성하는 과정에서 명확한 단계별 실행 흐름과 상태 전이를 유지해야 합니다.

## 1. 해석 파이프라인 단계 (Execution Pipeline Stages)

FHDL 엔진은 설계 입력을 최종 리포트로 변환하기 위해 다음 4단계의 엄격한 파이프라인을 거친다.

### 1.1 [S-FLO-001] 파싱 및 구문 분석 (Parsing)
*   **Entry:** DSL 소스 코드 입력 또는 파일 로드 이벤트 발생.
*   **Process:** 텍스트 토큰화 및 추상 구문 트리(AST) 생성.
*   **Exit:** 문법 오류(`SYN`)가 없을 것. AST 객체 생성 완료.

### 1.2 [S-FLO-002] 의미 해석 및 정규화 (Semantic & Validation)
*   **Entry:** 유효한 AST 확보.
*   **Process:** 
    *   **단위 변환:** 입력 단위를 SI 표준으로 변환.
    *   **데이터 가드:** 고도($-100 \sim 10000m$), 온도($0 \sim 100^\circ C$), 길이($>0$) 유효성 검증.
    *   **토폴로지 검증:** 폐회로(Cycle) 탐지 및 고립 노드(Dead Loop) 확인.
*   **Exit:** 의미 오류(`SEM`, `NET`)가 없을 것. 정규화된 엔티티 맵 및 네트워크 그래프 생성 완료.

### 1.3 [S-FLO-003] 수리 해석 및 자동 산정 (Solving & Sizing)
*   **Entry:** 정규화된 네트워크 모델 및 계산 스냅샷 확보.
*   **Process:** 유량 집계(Pass 1), 수압 평형 계산(Pass 2), 관경/펌프 자동 산정.
*   **Exit:** 수렴 조건 만족 및 수치 결과 산출 완료. 계산 오류(`CAL`)가 없을 것.

### 1.4 [S-FLO-004] 결과 생성 및 리포팅 (Reporting)
*   **Entry:** 계산 완료된 수치 데이터 세트 확보.
*   **Process:** 설계 제약(과속, 저압 등) 위반 판정, 리포트 포맷팅, 데이터 출처(Provenance) 바인딩.
*   **Exit:** 최종 리포트 객체 및 진단 요약본 생성 완료.

## 2. 상태 정의 (State Definitions)

시스템은 다음의 폐쇄된 상태 집합을 유지하며, 각 상태는 상호 배타적이다.

### 2.1 [S-FLO-005] 문서 및 파이프라인 상태
*   **Idle:** 활성 프로젝트나 문서가 없는 초기 대기 상태.
*   **DocumentLoaded:** 문서가 메모리에 로드되었으나 아직 편집되지 않은 상태.
*   **Dirty:** 로드된 문서가 수정되어 이전 계산 결과가 무효화된 상태.
*   **Validating:** 파이프라인 1, 2단계(Parsing/Semantic)가 진행 중인 상태.
*   **Validated:** 모든 검증을 통과하여 모델 생성 및 계산이 가능한 상태.
*   **Calculating:** 수리 해석 엔진(3단계)이 동작 중인 상태.
*   **Calculated:** 수치 해석 및 자동 산정이 성공적으로 완료된 상태.
*   **ReportReady:** 리포트 생성(4단계)이 완료되어 사용자에게 결과가 제시된 최종 상태.
*   **Saved:** 현재 상태가 파일에 안전하게 기록된 상태.

### 2.2 [S-FLO-006] 오류 및 중단 상태
*   **ValidationFailed:** 문법/의미 오류로 인해 파이프라인 중단.
*   **CalculationFailed:** 수렴 실패 또는 수리적 오류로 인해 계산 중단.
*   **Aborted:** 사용자의 요청으로 프로세스가 강제 중단된 상태.

## 3. 상세 상태 전이표 (State Transition Matrix)

| 현재 상태 (From) | 이벤트 (Event) | 다음 상태 (To) | 조건 및 비고 |
| :--- | :--- | :--- | :--- |
| **Idle** | `OPEN` / `NEW` | **DocumentLoaded** | 파일 I/O 성공 시 |
| **DocumentLoaded** | `EDIT` | **Dirty** | 텍스트 변경 감지 |
| **DocumentLoaded** | `RUN` | **Validating** | 해석 실행 요청 |
| **Dirty** | `SAVE` | **Saved** | 파일 쓰기 성공 시 |
| **Dirty** | `RUN` | **Validating** | 해석 실행 요청 |
| **Validating** | `FAIL` | **ValidationFailed** | 문법/의미 오류 발견 |
| **Validating** | `PASS` | **Validated** | 검증 통과 |
| **Validated** | `SOLVE` | **Calculating** | 엔진 가동 |
| **Calculating** | `SUCCESS` | **Calculated** | 수렴 성공 |
| **Calculating** | `FAIL` | **CalculationFailed** | 수렴 실패 (`CAL` 에러) |
| **Calculating** | `STOP` | **Aborted** | 사용자 강제 중단 |
| **Calculated** | `REPORT` | **ReportReady** | 리포트 생성 완료 |
| **Calculated** | `EDIT` | **Dirty** | 결과 무효화 및 편집 모드 |
| **Any** | `CLOSE` | **Idle** | 문서 닫기 |

### 3.1 [S-FLO-007] 금지 전이 규칙 (Forbidden Transitions)
안정성을 위해 다음의 전이는 엄격히 금지하며, 발생 시 시스템 예외를 투척한다.
*   **Calculating → Saved:** 계산 중에는 원자적 저장을 수행할 수 없다. (먼저 중단 필요)
*   **Idle → Validating:** 로드된 문서 없이 해석 파이프라인에 진입할 수 없다.
*   **ValidationFailed → Calculating:** 검증을 통과하지 못한 모델은 솔버에 전달될 수 없다.
*   **ReportReady → Validated:** 리포트 상태에서 검증 완료 상태로 역전이할 수 없다. (Dirty를 거쳐야 함)

## 4. 예외 발생 및 복구 시나리오 (Recovery Scenarios)

### 4.1 수리적 발산 (CalculationFailed) 복구
1.  **시나리오:** 반복 계산 500회 초과 또는 수치 폭주 발생.
2.  **조치:** 솔버는 즉시 중단되고 `CAL003` 에러를 진단 패널에 출력.
3.  **복구:** 사용자가 배관 연결 상태나 펌프 곡선을 수정한 후(상태: **Dirty**) 다시 `Run` 요청.

### 4.2 사용자 중단 (Aborted) 복구
1.  **시나리오:** 대규모 네트워크 해석 중 사용자가 `Stop` 버튼 클릭.
2.  **조치:** 진행 중인 모든 쓰레드를 안전하게 종료(Safe-termination)하고 현재까지의 부분 결과 폐기.
3.  **상태:** 시스템은 **Dirty/Saved** 상태로 복귀하여 재실행 대기.

## 5. 리소스 무효화 및 증분 업데이트 (M02)

### 5.1 증분 업데이트 (Incremental Sync)
사용자가 텍스트를 수정할 때, 전체 문서를 다시 해석하는 대신 변경된 블록만 식별하여 부분 업데이트를 수행합니다.
*   **Dirty 블록 식별:** 수정된 라인이 포함된 `{...}` 블록을 탐지.
*   **부분 파싱:** 해당 블록만 재파싱하여 `FluidSystem` 엔티티 업데이트.
*   **영향도 전파:** 변경된 노드/배관과 연결된 하류(Downstream) 경로만 계산 상태를 'Dirty'로 설정.

### 5.2 즉시 무효화 기준
*   **위상 변경:** `connect` 문이나 ID 수정 시에는 네트워크 그래프 전체를 재빌드해야 하므로 전체 무효화를 수행합니다.
*   **속성 변경:** 단순히 `length`나 `manual_flow` 수정 시에는 증분 업데이트를 우선 적용합니다.

---
[목차로 돌아가기](./INDEX.md)
