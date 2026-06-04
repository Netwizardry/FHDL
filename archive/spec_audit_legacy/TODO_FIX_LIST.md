# FHDL 명세서 정규화 및 완결성 확보 초정밀 To-do List

본 문서는 `codex_20260402_165117_audit_report.md`의 FAIL 판정을 극복하고, 프로젝트의 모든 규범 문서를 실전 구현이 가능한 수준으로 보정하기 위한 초정밀 실행 계획이다.

---

## 1. 기반 및 거버넌스 (Foundation & Governance)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`INDEX.md`** | 1. [L36] 추적 매트릭스(RTM)를 `R1~R5`에서 전체 요구사항(`R01~R20+`)으로 확장.<br>2. [L40] 설계(S)와 테스트(T) 링크를 실제 항목 ID로 전수 연결.<br>3. [L47] 전체 프로젝트 Revision History 및 문서 간 우선순위(Conflict Priority) 섹션 신설. | #4, #9, #12 | P1 |
| **`00_CONCEPT.md`** | 1. [L25] `v0.1 필수`, `MVP 제외`, `향후 확장` 항목을 단일 표로 재정의.<br>2. NPSHa/수충격의 v0.1 포함 여부를 타 문서(`11_SOLVER`)와 일치시킴. | #2 | P1 |
| **`07_ROADMAP.md`** | 1. [L23] v0.1~v0.4 로드맵 단계를 `00_CONCEPT`의 재정의된 범위와 동기화. | #2 | P2 |
| **`17_TERMINOLOGY.md`**| 1. 신규 도입되는 용어(Inverse Sync, Journaling, Provenance) 정의 추가. | #8, #11 | P3 |

## 2. 요구사항 및 규범 (Requirements & Norms)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`01_FUNC_REQ.md`** | 1. 모든 요구사항에 고유 ID(`R-FR-XXX`) 부여 및 RTM 연결 준비. | #4 | P2 |
| **`02_CALC_REQ.md`** | 1. [L39] 수충격(Time-dependent) 요구사항을 v0.1에서 삭제(정상상태만 수행).<br>2. [L25] Hazen-Williams 마찰 모델의 선택 기준과 입력 우선순위 명시. | #2, #7 | P1 |
| **`06_NFR.md`** | 1. [L14] 요구사항 코드 `CAL005`를 `15_ERRORS` 카탈로그와 일치시킴.<br>2. [L26] 성능 측정 조건(HW 사양, 데이터셋 규모) 정량화. | #3, #14 | P2 |
| **`03_UI_UX_REQ.md`**| 1. [L13] 5대 핵심 화면(Project/Viewer/Editor/Result/Error) 구조 확정 및 `14_GUI`와 동기화. | #10 | P2 |

## 3. 아키텍처 및 흐름 (Architecture & Flow)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`04_ARCH.md`** | 1. [L46] 번호 체계 정정 (`## 2` -> `## 3` 데이터 무결성 계층 추가).<br>2. [L66] Placeholder(`...`) 제거: 컴포넌트 간 인터페이스 및 통신 계약 실문장 기술. | #1, #13 | P1 |
| **`05_EXEC_FLOW.md`**| 1. [L19] Placeholder 제거: 파이프라인 단계별 Entry/Exit Criteria 상세화.<br>2. [L21, L43] 상태기계 폐쇄: `Calculated`, `DocumentLoaded` 등 누락 상태 및 전이 이벤트 표 통합. | #1, #5 | P1 |

## 4. 언어 및 데이터 모델 (Language & Models)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`08_LANGUAGE.md`**| 1. [L14] DSL 키워드(`source`, `nozzle` 등)와 `10_MODELS` 엔티티 간 매핑 규칙 명시.<br>2. [L69] "상세 문법 생략" 문구 제거 및 전체 EBNF 문법 복구. | #6, #13 | P1 |
| **`10_MODELS.md`** | 1. [L24] `Pipe.diameter` 등 `auto/derived` 필드의 정규화 처리 규칙 추가.<br>2. [L65] Placeholder 제거: 모든 엔티티의 필드명, 타입, 제약조건 전수 기록. | #1, #6 | P1 |
| **`20_STORAGE.md`** | 1. [L7] 리포트(`13_REPORTING`)에서 요구하는 `X,Y,Z`, `Surge` 등의 필드를 스키마에 추가 반영. | #8 | P2 |

## 5. 엔진 및 수식 (Engine & Formulas)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`09_FORMULAS.md`**| 1. [L24] Hazen-Williams 공식($h_f$ 산식), 유효 범위, $C$값 기본값 규범화. | #7 | P1 |
| **`11_SOLVER.md`** | 1. [L29, L87] Placeholder 제거: Newton-Raphson 자코비안 구성 및 수렴 판정 로직 실문장 기술.<br>2. [L71] 시간의존 수충격 해석 규범 삭제 (정상상태로 한정).<br>3. [L81] 오류 코드 `WRN004`를 `15_ERRORS`와 일치시킴. | #1, #2, #3 | P1 |

## 6. 파이프라인 및 리포트 (Pipeline & Reporting)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`12_PIPELINE.md`**| 1. [L21, L54] Placeholder 제거: 데이터 변환 경로 및 Provenance(출처) 추적 규칙 명시.<br>2. [L95] 캐시 재생성 및 저널 복구(Journal Recovery) 트리거 로직 추가. | #1, #8, #11 | P1 |
| **`13_REPORTING.md`**| 1. [L17, L27] 마찰 모델(HW/DW) 표시 정책 및 출력 컬럼별 데이터 소스 매핑표 추가. | #7, #8 | P2 |

## 7. 검증 및 운영 (Validation & Operations)

| 파일명 | 상세 작업 내용 (Audit 반영) | 관련 감사번호 | 우선순위 |
| :--- | :--- | :---: | :---: |
| **`15_ERRORS.md`** | 1. [L44] 감사에서 지적된 누락 코드(`CAL005`, `WRN004`, `SEM005~007`, `NET004~005`) 전수 등록. | #3 | P1 |
| **`16_TESTS.md`** | 1. [L26] 테스트 케이스(TC)를 3개에서 20개 이상으로 확장 (NPSH, Inverse Sync, 수격 위험도 등 포함).<br>2. 각 TC와 요구사항 ID(`R-XXX`) 연결. | #4, #9 | P2 |
| **`14_GUI.md`** | 1. [L5] 화면 구조를 `03_UI_UX_REQ`와 동기화 (5대 컴포넌트 체제).<br>2. [L16] 성능 측정 도구 및 벤치마크 환경 명시. | #10, #14 | P2 |
| **`19_OPERATIONS.md`**| 1. [L38, L51] Placeholder 제거: 기동/종료/복구/캐시 재빌드 단계별 절차(Runbook) 기술. | #1, #11 | P1 |
