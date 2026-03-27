# 05. 실행 흐름 및 상태 전이 명세

FHDL 프로그램은 설계자의 입력을 물리적 모델로 변환하고 계산 결과를 생성하는 과정에서 명확한 단계별 실행 흐름과 상태 전이를 유지해야 합니다.

## 1. 실행 흐름 기본 원칙

*   **단계적 처리 (Sequential Processing):** `문서 준비 -> 검증 -> 모델 생성 -> 계산 -> 리포트` 순으로 진행됩니다.
*   **실패 시 중단 (Fail-Stop):** 특정 단계에서 치명적 오류(Error/Fatal) 발생 시 이후 단계 진행을 차단합니다. (단, Warning은 진행 허용)
*   **재계산 무효화 (Invalidation on Edit):** 문서 원문이 수정되면 이전의 검증 및 계산 결과는 즉시 무효화(`Dirty`) 처리됩니다.

## 2. 상태 정의 (State Definitions)

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

### 2.3 오류 상태 (Failure States)
*   **ValidationFailed:** 문법/의미 오류로 인해 해석 중단.
*   **CalculationFailed:** 수렴 실패 또는 수리적 발산으로 인해 계산 중단.

## 3. 주요 상태 전이 규칙 (Transition Rules)

| 현재 상태 | 이벤트 (동작) | 다음 상태 | 조건 및 비고 |
| :--- | :--- | :--- | :--- |
| **Idle** | New/Open Document | **DocumentLoaded** | 파일 로드 성공 시 |
| **Any** | Text Changed | **Dirty** | 이전 결과 무효화 |
| **Dirty/Saved** | Run Analysis | **Validating** | 해석 파이프라인 진입 |
| **Validating** | No Critical Error | **Validated** | Semantic 모델 확보 |
| **Validated** | Start Solver | **Calculating** | 그래프 기반 계산 시작 |
| **Calculating** | Success | **ReportReady** | 결과 리포트 생성 완료 |
| **Any** | Save Request | **Saved** | 파일 쓰기 성공 시 |

## 4. 표준 실행 시나리오

### 4.1 신규 설계 및 계산 흐름
1.  **Idle** -> 프로젝트 생성 -> **Editing** (설계 기술)
2.  **Run** 요청 -> **Validating** (문법 검사) -> **Calculating** (수리 해석)
3.  **ReportReady** (결과 검토) -> **Saved** (저장)

### 4.2 오류 발생 및 복구 흐름
1.  **Validating** 중 구문 오류 발견 -> **ValidationFailed** 상태 전이.
2.  사용자에게 오류 위치 표시 -> **Editing/Dirty** (수정 시작).
3.  수정 후 다시 **Run** 요청 -> 해석 파이프라인 재진입.

## 5. 캐시 및 리소스 무효화

*   **즉시 무효화:** 사용자가 텍스트를 1자라도 수정하는 즉시 `AST`, `NetworkGraph`, `CalcResult`는 폐기되거나 '만료됨' 플래그가 설정되어야 합니다.
*   **UI 반영:** `Dirty` 상태에서 표시되는 이전 결과에는 "현재 문서 기준이 아님"을 시각적으로 명시해야 합니다.

---
[목차로 돌아가기](./INDEX.md)
