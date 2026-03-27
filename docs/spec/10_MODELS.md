# 07. 데이터 모델 및 내부 구조 명세

FHDL 프로그램은 입력 문법 처리, 의미 검증, 계산 수행, 결과 출력이 서로 독립적으로 유지될 수 있도록 계층적으로 분리된 데이터 모델을 사용합니다.

## 1. 데이터 모델 계층 구조

프로그램은 내부적으로 다음 6단계의 레이어를 거쳐 데이터를 처리합니다.

1.  **Source Layer:** 원본 FHDL 텍스트 및 메타데이터.
2.  **Syntax Layer:** 토큰화된 데이터 및 추상 구문 트리(AST).
3.  **Semantic Layer:** 의미 검증이 완료된 정규화 설비 객체(Entity).
4.  **Network Layer:** 계산용 노드-엣지 그래프 구조.
5.  **Calculation Layer:** 구간별 유량, 유속, 손실 등 계산 상태 데이터.
6.  **Reporting Layer:** 출력용 결과표, 요약, 진단(오류/경고) 정보.

## 2. 주요 레이어별 모델 상세

### 2.1 Syntax Model (AST)
파서가 생성하는 구조적 트리입니다.
*   **SystemNode:** 전역 설정 및 단위 정보.
*   **ComponentNode:** 설비 타입, ID, 속성 리스트.
*   **ConnectNode:** `->` 연산자로 연결된 경로 세그먼트.

### 2.2 Semantic Model (Entities)
AST를 실제 설계 객체로 변환하고 단위 정규화 및 참조 해결이 완료된 상태입니다.
*   **EntityBase:** ID, 원문 위치(Source Span), 산정 모드(`auto/manual`)를 포함한 공통 베이스.
*   **TankEntity:** 용량, 수위, 고도 정보.
*   **PumpEntity:** 유량/양정 모드, 효율, 동력 정보.
*   **PipeEntity:** 길이, 재질, 거칠기, 손실계수.
*   **TerminalEntity:** 노즐/스프링클러 통합 모델 (유량, 압력, 분사높이 요구조건).

### 2.3 Network Model (Calculation Graph)
물리적 계산을 수행하기 위한 노드-엣지 정규화 모델입니다.
*   **NetworkNode:** 수원, 펌프, 분기점, 말단 장치를 노드로 정의.
*   **NetworkEdge:** 배관 구간을 엣지로 정의하며, 해당 구간의 고유 유량과 손실 데이터를 보유.

### 2.4 Calculation Model (Calc States)
각 실행 시점의 계산 상태를 저장하며, 입력 모델과 분리하여 관리합니다.
*   **SegmentCalcState:** 유량, 선정 관경, 유속, 마찰/국부 손실 합계.
*   **SystemCalcState:** 시스템 총유량, 총 요구양정, 최불리 경로 ID, 권장 사양 요약.

## 3. 진단 및 오류 모델 (Diagnostics)

오류와 경고를 구조화된 객체로 관리하여 UI와 연동합니다.
*   **DiagnosticItem:** 
    *   `Severity`: Info, Warning, Error, Fatal.
    *   `Category`: Syntax, Semantic, Hydraulic, Logic.
    *   `Message`: 사용자 친화적 설명 및 수정 힌트.
    *   `SourceSpan`: 원문 내 발생 위치 (Line, Column).

## 4. 저장 및 프로젝트 구조

초기 버전은 텍스트 기반의 소스 관리와 JSON 기반의 메타데이터 관리를 병행합니다.
*   **design.fhd:** 설계 원문 (Source of Truth).
*   **project.meta.json:** 프로젝트 설정 및 마지막 계산 결과 요약.
*   **cache/state.db:** 고성능 쿼리를 위한 현재 상태 캐시.

---
[목차로 돌아가기](./INDEX.md)
