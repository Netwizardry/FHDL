# FHDL (Fluid Hardware Description Language) 시스템 명세서

> **FHDL 프로그램은 유체 설비 설계 의도를 언어로 입력받아, 이를 계산 가능한 배관 시스템으로 변환하고, 핵심 설계 사양을 자동 선정하여 설계 결과서로 출력하는 선언형 유체설비 설계 자동화 시스템이다.**

이 문서는 FHDL 프로그램의 설계 및 구현 상세를 정의하는 공식 명세서입니다. 모든 작업은 본 명세서를 기준으로 수행됩니다.

## 1. 시스템 설계 기반 (Design Foundation)

### [00. 목적 및 범위 (Objectives & Scope)](./00_CONCEPT.md)
### [01. 시스템 구성 요소 (Core Components)](./01_COMPONENTS.md)
### [02. 기능적 요구사항 (Functional Requirements)](./01_FUNCTIONAL_REQUIREMENTS.md)
### [03. 계산 및 설계 요구사항 (Calculation Requirements)](./02_CALCULATION_REQUIREMENTS.md)
### [04. UI/UX 요구사항 (UI/UX Requirements)](./03_UI_UX_REQUIREMENTS.md)
### [05. 시스템 아키텍처 및 모듈 분리 (Architecture & Modules)](./04_ARCHITECTURE.md)
### [06. 실행 흐름 및 상태 전이 (Execution Flow)](./05_EXECUTION_FLOW.md)
### [07. 비기능 요구사항 (Non-Functional Requirements)](./06_NON_FUNCTIONAL_REQUIREMENTS.md)
### [08. 구현 로드맵 및 MVP 범위 (Roadmap & MVP)](./07_ROADMAP.md)

## 2. 상세 기술 명세 (Technical Specifications)

### [09. 언어 및 문법 (Language & Syntax)](./08_LANGUAGE.md)
### [10. 계산식 및 판정 규칙 (Formulas & Rules)](./09_FORMULAS.md)
### [11. 데이터 모델 및 내부 구조 (Data Models & Structure)](./10_MODELS.md)
### [12. 솔버 엔진 (Solver Engine)](./11_SOLVER.md)
### [13. 파이프라인 및 인터페이스 (Pipeline & Interfaces)](./12_PIPELINE.md)
### [14. 리포트 및 출력 (Reporting & Output)](./13_REPORTING.md)
### [15. 사용자 인터페이스 (GUI Implementation)](./14_GUI.md)
### [16. 오류 처리 및 진단 메시지 명세 (Diagnostics)](./15_ERRORS.md)
### [17. 테스트 시나리오 및 검증 기준 (Test Scenarios)](./16_TESTS.md)
### [18. 용어 정의 및 명명 규칙 (Terminology & Naming)](./17_TERMINOLOGY.md)
### [19. 운영 및 배포 (Operations & Deployment)](./19_OPERATIONS.md)
### [20. 저장소 스키마 및 직렬화 (Storage & Schema)](./20_STORAGE_SCHEMA.md)

### [부록 A. 기본 테이블 및 기본값 규칙 (Defaults & Tables)](./APPENDIX_A_DEFAULTS.md)

## 3. 요구사항 추적성 (Traceability Matrix)

| 상위 요구사항 (Source) | 설계 요소 (Design) | 검증 기준 (Test) |
| :--- | :--- | :--- |
| **R1. 자동 관경 산정** | [09. DSL `auto`](./08_LANGUAGE.md), [10. 산정식](./09_FORMULAS.md) | [T-AUTO-001](./16_TESTS.md) |
| **R2. 2-Pass 수리해석** | [12. 솔버 엔진](./11_SOLVER.md), [06. 상태 전이](./05_EXECUTION_FLOW.md) | [T-CAL-006](./16_TESTS.md) |
| **R3. NPSHa/진공 진단** | [12. 가용수두 공식](./11_SOLVER.md), [16. WRN003](./15_ERRORS.md) | [T-ERR-005](./16_TESTS.md) |
| **R4. 비동기 UI 연동** | [13. 파이프라인](./12_PIPELINE.md), [15. GUI](./14_GUI.md) | [T-NFR-003](./16_TESTS.md) |
| **R5. 데이터 무결성** | [13. Atomic Save](./12_PIPELINE.md), [07. NFR](./06_NON_FUNCTIONAL_REQUIREMENTS.md) | [T-NFR-001](./16_TESTS.md) |

---
*최종 업데이트: 2026-04-02 (Audit Fixed v4.0)*
