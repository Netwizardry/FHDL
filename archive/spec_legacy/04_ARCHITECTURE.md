# 05. 시스템 아키텍처 및 모듈 분리 명세

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL 시스템은 입력 문법 처리, 설비 구조 해석, 수리 계산, 결과 출력, 저장 기능이 서로 독립적으로 유지되면서도 유기적인 설계 워크플로우를 형성하도록 계층화된 아키텍처를 가집니다.

## 1. 아키텍처 설계 원칙

*   **계층 분리 (Layered Separation):** 각 계층은 고유의 책임을 가지며, 하위 계층은 상위 계층의 존재를 알 필요가 없습니다.
*   **단방향 흐름 (Unidirectional Flow):** 데이터는 `입력 -> 파싱 -> 정규화 -> 그래프 생성 -> 계산 -> 리포트` 순으로 단방향으로 흐릅니다.
*   **모델 경계 (Model Boundaries):** 각 계층은 다음 단계에 필요한 정규화된 중간 모델(AST, Entity, Graph 등)만을 전달합니다.
*   **책임 고립 (Responsibility Isolation):** 파서는 계산을 하지 않으며, 계산 엔진은 원문 문법을 알지 못합니다.

## 2. 8대 핵심 계층 (Core Layers)

### 2.1 [S-ARC-001] UI Layer (사용자 인터페이스)
*   **책임:** DSL 텍스트 편집, 실행 요청, 결과 및 오류 시각화.
*   **원칙:** 계산이나 파싱을 직접 수행하지 않고 `Application Layer`에 요청한다.

### 2.2 [S-ARC-002] Application Layer (응용 제어)
*   **책임:** 전체 워크플로우 오케스트레이션, 모듈 간 데이터 전달 및 트랜잭션 관리.
*   **원칙:** 사용자의 명령을 받아 파서부터 리포트 생성까지의 파이프라인을 구동한다.

### 2.3 [S-ARC-003] Parser Layer (문법 처리)
*   **책임:** 텍스트 토큰화, 구문 분석, 추상 구문 트리(AST) 생성.
*   **산출물:** `TokenStream`, `AST`, `SyntaxDiagnostics`.

### 2.4 [S-ARC-004] Semantic Layer (의미 해석)
*   **책임:** AST의 정규화, 단위 변환, 참조 해결(Reference Resolution) 및 의미론적 검증.
*   **산출물:** `NormalizedEntities`, `SemanticDiagnostics`.

### 2.5 [S-ARC-005] Network Builder Layer (네트워크 구성)
*   **책임:** 엔티티를 노드-엣지 기반의 물리적 계산 그래프로 변환.
*   **산출물:** `NetworkGraph`, `TopologyDiagnostics`.

### 2.6 [S-ARC-006] Calculation Engine Layer (계산 엔진)
*   **책임:** 유량 집계, 관경 선정, 손실 및 양정 계산, 펌프/탱크 사양 산출.
*   **산출물:** `CalculationStates`, `HydraulicDiagnostics`.

### 2.7 [S-ARC-007] Report & Diagnostic Layer (결과 및 진단)
*   **책임:** 계산 상태를 사용자용 표/요약 리포트로 변환, 모든 단계의 진단 정보 통합.
*   **산출물:** `FinalReport`, `DiagnosticSummary`.

### 2.8 [S-ARC-008] Storage Layer (저장 관리)
*   **책임:** 설계 문서(.fhd), 프로젝트 메타데이터, 계산 결과의 영속성 관리.

## 3. 데이터 무결성 계층 (Integrity & Persistence Layer)

### 3.1 [S-ARC-009] 저널링 및 상태 복구 (Journaling)
시스템은 모든 파괴적 변경(Destructive Change) 이전에 저널 파일을 생성하여 비정상 종료 시 복구 경로를 제공한다.
*   **Write-Ahead Log:** 데이터 본 파일 수정 전 변경 내역을 `.journal` 파일에 선기록한다.
*   **Recovery Trigger:** 기동 시 유효하지 않은 종료 플래그 감지 시 저널을 기반으로 상태를 재구축한다.

### 3.2 [S-ARC-010] 원자적 저장 (Atomic Save)
파일 저장 시 중간 단계의 데이터 손실을 방지하기 위해 다음 절차를 따른다.
1.  **Stage:** 임시 디렉토리에 전체 프로젝트 데이터를 직렬화하여 기록한다.
2.  **Verify:** 기록된 파일의 무결성을 체크섬으로 검증한다.
3.  **Swap:** 원본 파일과 임시 파일을 원자적(`Rename`)으로 교체한다.

## 4. 동시성 및 데이터 통신 규격 (Concurrency & Interfaces)

GUI와 Core 엔진 간의 비동기 통신은 JSON-RPC 스타일의 메시지 버스를 통해 수행되며, 직접적인 메모리 공유를 최소화한다.

### 4.1 [S-ARC-011] 비동기 통신 인터페이스 (Async Interface)
*   **Request Channel:** GUI는 `Command(Type, Payload)` 객체를 통해 분석 시작, 중단, 저장을 요청한다.
*   **Event Channel:** Core는 다음 이벤트를 발행하여 GUI 상태를 갱신한다.
    *   `StatusUpdate(Code, Message)`: 파이프라인 현재 단계 알림.
    *   `DataSync(EntityMap)`: 정규화 완료된 엔티티 맵 전달 (Inverse Sync 용).
    *   `AnalysisFinished(ResultData, ErrorList)`: 해석 완료 통지 및 결과 데이터 전달.

### 4.2 [S-ARC-012] 스냅샷 격리 (Snapshot Isolation)
해석 엔진은 실행 시점의 엔티티 맵에 대해 불변 스냅샷(Immutable Snapshot)을 생성하여 독립된 워커 쓰레드에서 계산을 수행함으로써 GUI 프리징(Freezing)을 방지한다.
*   **스냅샷 생성:** 해석이 시작되는 시점에 현재의 `Semantic Model` 데이터를 깊은 복사(Deep Copy)하여 스레드 간 참조를 끊는다.
*   **격리 연산:** 해석 스레드는 오직 스냅샷 데이터만 읽고 쓰며, 메인 스레드의 수정 사항은 무시한다.
*   **결과 병합:** 계산이 완료되면 `AnalysisFinished` 이벤트를 통해 결과 델타(Delta)만 메인 스레드로 반환하여 UI에 반영한다.

## 5. 저장 및 영속성 전략 (Storage Strategy)

### 5.1 [S-ARC-013] 로컬 SQLite 저장소 전략
*   프로젝트의 구조적 데이터(엔티티, 네트워크 위상)와 해석 이력은 로컬 SQLite 데이터베이스(`.fhproj` 내장)에 영속화된다.
*   계산 결과 파생 필드(유속, 손실 등 `Recompute Allowed`=Y 인 데이터)는 디스크 용량 최적화를 위해 별도 저장하지 않거나 캐시 만료 정책을 적용하여 필요 시 재계산한다.

---
[목차로 돌아가기](./INDEX.md)
