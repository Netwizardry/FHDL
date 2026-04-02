# 02. 핵심 기능 요구사항 (Functional Requirements)

FHDL 시스템은 설계자의 의도를 해석하여 물리적으로 타당한 설비 사양을 자동으로 도출하기 위해 다음과 같은 기능을 수행해야 합니다. (A04: 입출력 조건 중심 명세)

## 1. 설계 입력 및 문법 검증 (Input & Validation)

### 1.1 설계 기술 및 정규화
*   **[R-FR-001] 시스템 컨텍스트 선언:** 
    *   **Input:** 단위계(Metric/Imperial), 유체 종류(Water 고정), 온도, 설계 제약(Max Velocity 등).
    *   **Process:** 전역 환경 변수를 설정하고 단위 변환 엔진 초기화 및 SI 표준 단위로 정규화.
    *   **Output:** SI 표준 단위($m, m^3/h, kg/m^3$)로 정규화된 시스템 객체.
*   **[R-FR-002] 구성요소 및 위상 선언:**
    *   **Input:** 구성요소 ID, 타입(Pipe, Pump, Tank, Terminal), 속성, `connect` 문.
    *   **Process:** 식별자 등록 및 연결 관계를 그래프(Adjacency List)로 변환.
    *   **Output:** 추상 구문 트리(AST) 및 초기 네트워크 그래프 모델.

### 1.2 문법 및 논리 검증
*   **[R-FR-003] 구문 및 참조 정합성 검증:**
    *   **Input:** 파싱된 AST 및 식별자 맵.
    *   **Process:** 중복 ID 검사, 존재하지 않는 노드 참조 확인, 필수 속성 누락 체크.
    *   **Output:** `SYN`, `SEM` 계열 진단 메시지 및 검증 통과 여부.
*   **[R-FR-004] 네트워크 연결성 검사:**
    *   **Input:** 생성된 네트워크 그래프.
    *   **Process:** 소스(Tank/Pump)에서 모든 터미널(Nozzle/Sprinkler)까지의 경로 존재 여부(Reachability) 확인.
    *   **Output:** `NET` 계열 진단 메시지 (고립 노드, 경로 단절, 루프 형성 경고 등).

## 2. 구조 해석 및 수리 계산 (Analysis & Calculation)

### 2.1 수리 계산 프로세스
*   **[R-FR-005] 유량 집계 (Pass 1: Flow Synthesis):**
    *   **Input:** 말단 장치 요구 유량($Q_{req}$), 네트워크 위상(Topology).
    *   **Process:** 터미널에서 소스 방향으로 유량을 누적 합산 ($Q_{up} = \sum Q_{down}$).
    *   **Output:** 구간별 설계 유량($Q_{design}$) 및 총 시스템 유량.
*   **[R-FR-006] 압력 및 손실 계산 (Pass 2: Hydraulic Verification):**
    *   **Input:** 구간 유량, 관경, 재질 거칠기, 고도차, 입구 수두.
    *   **Process:** Darcy-Weisbach(기본) 또는 Hazen-Williams 식을 적용하여 마찰/국부 손실 산정 및 수압 평형 계산.
    *   **Output:** 노드별 압력($P$), 배관별 유속($V$) 및 손실수두($h_f$).

### 2.2 자동 산정 (Auto-Sizing)
*   **[R-FR-007] 관경 자동 산정:**
    *   **Input:** 설계 유량, 유속 제약조건($V_{limit}$), 표준 관경 테이블(`APPENDIX_A`).
    *   **Process:** 제약조건을 만족하는 가장 작은 표준 관경을 자동으로 탐색하여 할당.
    *   **Output:** 선정 관경($D_{selected}$) 및 유속 위반 시 경고 메시지.

## 3. 데이터 동기화 및 무결성 (Integrity & Sync)

### 3.1 양방향 동기화
*   **[R-FR-008] 역방향 동기화 (Inverse Sync):**
    *   **Input:** GUI/Canvas에서 수정된 노드 좌표 또는 속성 변경 이벤트.
    *   **Process:** 변경 사항을 원본 DSL 텍스트에 문법 구조를 유지하며 역직렬화(Deserialize).
    *   **Output:** 업데이트된 `.fhd` 소스 코드.

### 3.2 장애 복구 및 상태 관리
*   **[R-FR-009] 저널 기반 상태 복구:**
    *   **Input:** 비정상 종료 후 재기동 시 남겨진 저널 파일(`.journal`).
    *   **Process:** 마지막 성공 상태(Checkpoint) 이후의 변경 이력을 순차 재실행(Redo).
    *   **Output:** 사고 직전의 데이터 상태 복원.
*   **[R-FR-010] 원자적 저장 (Atomic Save):**
    *   **Input:** 프로젝트 저장 요청.
    *   **Process:** 임시 파일에 쓰기 완료 후 원본과 교체(Rename)하여 파일 손상 방지.
    *   **Output:** 무결성이 보장된 프로젝트 파일(`.fhproj`).

## 4. 진단 및 리포팅
*   **[R-FR-011] NPSHa 및 캐비테이션 진단:**
    *   **Input:** 펌프 흡입측 노드 압력, 유체 증기압, 고도.
    *   **Process:** $NPSHa$ 계산 및 $NPSHr$(요구수두)와의 비교를 통한 캐비테이션 위험 판정.
    *   **Output:** `WRN003` 경고 및 안전 마진 정보.
*   **[R-FR-012] 설계 결과 리포트 생성:**
    *   **Input:** 계산 완료된 시스템 모델 및 Provenance 데이터.
    *   **Process:** 요약 보고서 및 구간별 상세 데이터 테이블 생성.
    *   **Output:** CSV/PDF/JSON 형식의 리포트 파일.

---
[목차로 돌아가기](./INDEX.md)
