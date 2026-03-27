# 04. 시스템 아키텍처 및 모듈 분리 명세

FHDL 시스템은 입력 문법 처리, 설비 구조 해석, 수리 계산, 결과 출력, 저장 기능이 서로 독립적으로 유지되면서도 유기적인 설계 워크플로우를 형성하도록 계층화된 아키텍처를 가집니다.

## 1. 아키텍처 설계 원칙

*   **계층 분리 (Layered Separation):** 각 계층은 고유의 책임을 가지며, 하위 계층은 상위 계층의 존재를 알 필요가 없습니다.
*   **단방향 흐름 (Unidirectional Flow):** 데이터는 `입력 -> 파싱 -> 정규화 -> 그래프 생성 -> 계산 -> 리포트` 순으로 단방향으로 흐릅니다.
*   **모델 경계 (Model Boundaries):** 각 계층은 다음 단계에 필요한 정규화된 중간 모델(AST, Entity, Graph 등)만을 전달합니다.
*   **책임 고립 (Responsibility Isolation):** 파서는 계산을 하지 않으며, 계산 엔진은 원문 문법을 알지 못합니다.

## 2. 8대 핵심 계층 (Core Layers)

### 2.1 UI Layer (사용자 인터페이스)
*   **책임:** DSL 텍스트 편집, 실행 요청, 결과 및 오류 시각화.
*   **원칙:** 계산이나 파싱을 직접 수행하지 않고 `Application Layer`에 요청합니다.

### 2.2 Application Layer (응용 제어)
*   **책임:** 전체 워크플로우 오케스트레이션, 모듈 간 데이터 전달 및 트랜잭션 관리.
*   **원칙:** 사용자의 명령을 받아 파서부터 리포트 생성까지의 파이프라인을 구동합니다.

### 2.3 Parser Layer (문법 처리)
*   **책임:** 텍스트 토큰화, 구문 분석, 추상 구문 트리(AST) 생성.
*   **산출물:** `TokenStream`, `AST`, `SyntaxDiagnostics`.

### 2.4 Semantic Layer (의미 해석)
*   **책임:** AST의 정규화, 단위 변환, 참조 해결(Reference Resolution) 및 의미론적 검증.
*   **산출물:** `NormalizedEntities`, `SemanticDiagnostics`.

### 2.5 Network Builder Layer (네트워크 구성)
*   **책임:** 엔티티를 노드-엣지 기반의 물리적 계산 그래프로 변환.
*   **산출물:** `NetworkGraph`, `TopologyDiagnostics`.

### 2.6 Calculation Engine Layer (계산 엔진)
*   **책임:** 유량 집계, 관경 선정, 손실 및 양정 계산, 펌프/탱크 사양 산출.
*   **산출물:** `CalculationStates`, `HydraulicDiagnostics`.

### 2.7 Report & Diagnostic Layer (결과 및 진단)
*   **책임:** 계산 상태를 사용자용 표/요약 리포트로 변환, 모든 단계의 진단 정보 통합.
*   **산출물:** `FinalReport`, `DiagnosticSummary`.

### 2.8 Storage Layer (저장 관리)
*   **책임:** 설계 문서(.fhd), 프로젝트 메타데이터, 계산 결과의 영속성 관리.
*   **원칙:** 파일 포맷의 직렬화/역직렬화만을 담당합니다.

## 3. 실행 파이프라인 (Execution Pipeline)

### 3.1 문법 검사 파이프라인
`SourceDocument` -> `Parser` -> `Semantic Analyzer` -> `UI (Diagnostics Only)`

### 3.2 전체 해석 파이프라인
`SourceDocument` -> `Parser` -> `Semantic` -> `Network Builder` -> `Calc Engine` -> `Report Generator` -> `UI/Storage`

---
[목차로 돌아가기](./INDEX.md)
