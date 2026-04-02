# FHDL (Fluid Hardware Description Language) 시스템 명세서

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


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

| ID | 상위 요구사항 (Source) | 설계 요소 (Design) | 검증 기준 (Test Case) |
| :--- | :--- | :--- | :--- |
| **R01** | **자동 관경 산정 (Auto-Sizing)** | [S-DSL-001](./08_LANGUAGE.md), [S-FOR-002](./09_FORMULAS.md) | [T-AUTO-001](./16_TESTS.md) |
| **R02** | **2-Pass 수리해석 (Steady-state)** | [S-SOL-001](./11_SOLVER.md), [S-FLO-002](./05_EXECUTION_FLOW.md) | [T-CAL-001](./16_TESTS.md) |
| **R03** | **NPSHa/캐비테이션 진단** | [S-SOL-003](./11_SOLVER.md), [S-ERR-003](./15_ERRORS.md) | [T-ERR-005](./16_TESTS.md) |
| **R04** | **비동기 UI 연동 (Async UI)** | [S-PIP-001](./12_PIPELINE.md), [S-GUI-001](./14_GUI.md) | [T-NFR-003](./16_TESTS.md) |
| **R05** | **데이터 무결성 (Atomic Save)** | [S-PIP-004](./12_PIPELINE.md), [S-NFR-001](./06_NON_FUNCTIONAL_REQUIREMENTS.md) | [T-NFR-001](./16_TESTS.md) |
| **R06** | **Hazen-Williams 마찰 모델** | [S-FOR-003](./09_FORMULAS.md), [S-CAL-002](./02_CALCULATION_REQUIREMENTS.md) | [T-CAL-002](./16_TESTS.md) |
| **R07** | **Inverse Sync (GUI <-> DSL)** | [S-PIP-002](./12_PIPELINE.md), [S-GUI-003](./14_GUI.md) | [T-SYN-001](./16_TESTS.md) |
| **R08** | **상태기계 기반 흐름 통제** | [S-FLO-001](./05_EXECUTION_FLOW.md), [S-ARC-002](./04_ARCHITECTURE.md) | [T-FLO-001](./16_TESTS.md) |
| **R09** | **진단 코드 정합성** | [S-ERR-001](./15_ERRORS.md), [S-SOL-005](./11_SOLVER.md) | [T-ERR-001](./16_TESTS.md) |
| **R10** | **저널링 기반 장애 복구** | [S-PIP-005](./12_PIPELINE.md), [S-OPS-003](./19_OPERATIONS.md) | [T-OPS-002](./16_TESTS.md) |
| **R11** | **Provenance (데이터 출처 관리)** | [S-MOD-004](./10_MODELS.md), [S-REP-003](./13_REPORTING.md) | [T-REP-001](./16_TESTS.md) |
| **R12** | **단위 체계 일관성 (SI/IMP)** | [S-MOD-001](./10_MODELS.md), [S-FOR-001](./09_FORMULAS.md) | [T-UNIT-001](./16_TESTS.md) |

## 4. 프로젝트 거버넌스 (Governance)

### 4.1. 문서 우선순위 (Conflict Resolution Priority)
문서 간 내용이 상충할 경우 다음 순서에 따라 우선순위를 결정한다.
1.  **1순위:** `00_CONCEPT.md` (시스템의 목적 및 MVP 범위)
2.  **2순위:** `11_SOLVER.md`, `09_FORMULAS.md` (기술적 계산 규범)
3.  **3순위:** `04_ARCHITECTURE.md`, `10_MODELS.md` (구조적 설계 규범)
4.  **4순위:** 기타 상세 명세 문서

### 4.2. 수정 및 버전 관리 (Revision History)
| 버전 | 일자 | 수정 내용 | 비고 |
| :--- | :--- | :--- | :--- |
| v0.1 | 2026-03-20 | 초기 명세서 초안 작성 | - |
| v1.5 | 2026-03-25 | MVP 범위 확정 및 테스트 시나리오 추가 | - |
| v4.0 | 2026-04-02 | 감사 보고서 지적 사항 반영 및 RTM 확장 (현재) | Audit Fixed |

---
*최종 업데이트: 2026-04-02 (Audit Fixed v4.0)*
