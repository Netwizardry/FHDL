# 06. 실행 흐름 및 상태 전이 명세

FHDL 프로그램은 설계자의 입력을 물리적 모델로 변환하고 계산 결과를 생성하는 과정에서 명확한 단계별 실행 흐름과 상태 전이를 유지해야 합니다.
### 1.2 데이터 가드 (Data Guard Layer)
구문 분석 직후, 모든 엔티티의 수치 속성을 대상으로 유효 범위를 강제 검증합니다.
*   **고도 가드:** $z \in [-100, 10000]$ (m). 범위를 벗어나면 `SEM005` 발생.
*   **온도 가드:** $temp \in [0.0, 100.0]$ (°C). 범위를 벗어나면 `SEM006` 발생.
*   **길이 가드:** $length > 0$ (m). 0 이하일 경우 `SEM007` 발생.
*   **결과:** 모든 가드를 통과한 데이터만 `Validated` 상태로 전이되어 솔버에 전달됩니다. (GIGO 방지)

### 1.3 토폴로지 검증 (Topology Guard)
네트워크 모델 생성 직후, 수리 해석의 수렴성을 보장하기 위해 위상 구조를 검증합니다.
*   **Cycle Detection:** 시스템은 NetworkX의 `simple_cycles` 알고리즘을 사용하여 폐회로를 탐지합니다.
*   **Loop Policy:** 
    *   **Open Tree:** 루프가 없는 트리 구조는 즉시 Pass.
    *   **Parallel Pipes:** 동일 노드 사이의 병렬 배관은 허용하되, 복합 루프망은 v0.1에서 `NET004` 경고를 발생시킵니다.
    *   **Dead Loop:** 공급원(Source) 없이 순환만 하는 고립 루프는 `NET005` 에러로 처리하여 실행을 중단합니다.

## 2. 상태 정의 (State Definitions)
...
### 2.1 문서 상태 (Document States)
*   **Idle:** 활성 문서가 없는 초기 상태.
*   **Editing:** 사용자가 설계 문서를 편집 중인 상태.
*   **Dirty:** 문서가 수정되었으나 아직 저장되거나 재검증되지 않은 상태.
*   **Saved:** 현재 편집 내용이 파일에 영속화된 상태.

### 2.2 해석 파이프라인 상태 (Pipeline States)
*   **Validating:** 문법 및 의미 검증(Syntax/Semantic check)이 진행 중인 상태.
*   **Validated:** 검증을 통과하여 모델 생성 및 계산이 가능한 상태.
*   **Calculating:** 수리 해석 엔진이 동작 중인 상태.
*   **Calculated:** 수치 해석이 성공적으로 완료된 상태.
*   **ReportReady:** 계산 결과를 바탕으로 사용자용 리포트가 생성된 최종 상태.

### 2.3 오류 및 예외 상태 (Failure & Exception States)
*   **ValidationFailed:** 문법/의미 오류로 인해 해석 중단.
*   **CalculationFailed:** 수렴 실패 또는 수리적 발산으로 인해 계산 중단.
*   **Aborted:** 사용자가 의도적으로 해석 프로세스를 중단한 상태.
*   **SyncError:** 모델 동기화(GUI-Solver 간) 과정에서 Race Condition 또는 데이터 불일치 발생 시.
*   **PartialSuccess:** 수치 해석은 완료되었으나 설계 제약 조건(과속, 저압 등) 위반 경고가 포함된 상태.

## 3. 상세 상태 전이 규칙 (Transition Rules - A07)

| 현재 상태 | 이벤트 (동작) | 다음 상태 | 조건 및 비고 |
| :--- | :--- | :--- | :--- |
| **Idle** | New/Open Document | **DocumentLoaded** | 파일 로드 성공 시 |
| **Any** | Text Changed | **Dirty** | 이전 결과 무효화 |
| **Dirty/Saved** | Run Analysis | **Validating** | 해석 파이프라인 진입 |
| **Validating** | Critical Error | **ValidationFailed** | 파서/세만틱 검증 실패 |
| **Validating** | No Critical Error | **Validated** | Semantic 모델 확보 |
| **Validated** | Start Solver | **Calculating** | 그래프 기반 계산 시작 |
| **Calculating** | Success | **ReportReady** | 결과 리포트 생성 완료 |
| **Calculating** | Warnings | **PartialSuccess** | 계산 완료 + 설계 제약 위반 |
| **Calculating** | Convergence Fail | **CalculationFailed** | Newton-Raphson 발산 시 |
| **Calculating** | Abort Request | **Aborted** | 사용자 중단 버튼 클릭 시 |
| **Calculating** | Sync Failure | **SyncError** | 모델 스냅샷 생성/병합 실패 시 |
| **Any** | Save Request | **Saved** | 파일 쓰기 성공 시 |

## 4. 예외 발생 및 복구 시나리오 (Recovery Scenarios)

### 4.1 수리적 발산 (CalculationFailed) 복구
1.  **시나리오:** 반복 계산 500회 초과 또는 수치 폭주 발생.
2.  **조치:** 솔버는 즉시 중단되고 `CAL003` 에러를 진단 패널에 출력.
3.  **복구:** 사용자가 배관 연결 상태나 펌프 곡선을 수정한 후(상태: **Dirty**) 다시 `Run` 요청.

### 4.2 사용자 중단 (Aborted) 복구
1.  **시나리오:** 대규모 네트워크 해석 중 사용자가 `Stop` 버튼 클릭.
2.  **조치:** 진행 중인 모든 쓰레드를 안전하게 종료(Safe-termination)하고 현재까지의 부분 결과 폐기.
3.  **상태:** 시스템은 **Dirty/Saved** 상태로 복귀하여 재실행 대기.

### 4.3 동기화 오류 (SyncError) 복구
1.  **시나리오:** GUI 스레드와 솔버 스레드 간의 스냅샷 불일치 발생.
2.  **조치:** 즉시 `FATAL` 오류 발생 및 `SyncError` 로그 기록.
3.  **복구:** 메모리 내 모델 강제 초기화(Flush) 후 문서를 재로드하여 정합성 확보.

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
