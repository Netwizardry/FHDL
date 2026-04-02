# 01. 핵심 구성요소 (Core Components)

FHDL 시스템은 유기적으로 연결된 8개의 핵심 계층(Layers)으로 구성됩니다.

## 1. 사용자 및 제어 계층 (User & Control)

### 1.1 UI Layer (사용자 인터페이스)
*   **역할:** DSL 텍스트 편집, 실시간 구문 강조, 해석 결과 시각화.
*   **구성:** `MainEditor`, `NetworkViewer`, `DiagnosticPanel`.

### 1.2 Application Layer (응용 제어)
*   **역할:** 전체 워크플로우 오케스트레이션 및 파이프라인 관리.
*   **구성:** `ProjectManager`, `PipelineManager`.

## 2. 해석 및 처리 계층 (Processing & Analysis)

### 2.1 Parser Layer (문법 처리)
*   **역할:** DSL 텍스트를 토큰화하고 추상 구문 트리(AST)로 변환.
*   **구성:** `Lexer`, `FHDLParser`.

### 2.2 Semantic Layer (의미 해석)
*   **역할:** AST의 정규화, 단위 변환 및 의미론적 검증.
*   **구성:** `SemanticAnalyzer`, `UnitConverter`.

### 2.3 Network Builder Layer (네트워크 구성)
*   **역할:** 설비 엔티티를 수리 계산용 그래프 모델로 변환.
*   **구성:** `GraphBuilder`, `TopologyChecker`.

## 3. 엔진 및 데이터 계층 (Engine & Data)

### 3.1 Calculation Engine Layer (계산 엔진)
*   **역할:** 2-Pass 알고리즘을 통한 수리 해석 및 자동 산정.
*   **구성:** `HydraulicSolver`, `AutoSizer`.

### 3.2 Report & Diagnostic Layer (결과 및 진단)
*   **역할:** 계산 결과서 생성 및 통합 진단 정보 관리.
*   **구성:** `ReportGenerator`, `DiagnosticManager`.

### 3.3 Storage Layer (저장 관리)
*   **역할:** 파일(.fhd), 메타데이터, 캐시 DB의 영속성 관리.
*   **구성:** `StorageProvider`, `CacheDBManager`.

---
[목차로 돌아가기](./INDEX.md)
