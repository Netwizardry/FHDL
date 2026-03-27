# 04. 파이프라인 및 인터페이스 (Pipeline & Interfaces) 명세

FHDL 시스템은 파일, 메모리(그래프), 데이터베이스 간의 무결성을 유지하며, 다양한 단위계와 규격을 통합 관리하는 파이프라인을 가집니다.

## 1. 프로젝트 관리 및 동적 동기화

### 1.1 삼각 동기화 (Triple Synchronization)
시스템은 변경 사항 발생 시 다음의 세 레이어를 동시에 업데이트하여 데이터 일관성을 보장합니다.
1.  **메모리(Memory):** `FluidSystem` 객체 및 NetworkX 그래프 엔진. 실시간 계산용.
2.  **데이터베이스(Cache DB):** `state.db` (SQLite). 고성능 쿼리 및 UI 상태 유지용.
3.  **소스 파일(Source File):** `main.fhd`. 사용자의 설계 원본 데이터 (Atomic Save 적용).

### 1.2 원자적 저장 (Atomic Save)
`.fhd` 파일 저장 시 직접 덮어쓰지 않고 `.tmp` 파일을 생성한 후 `os.replace`를 사용하여 파일 오염을 방지합니다.

## 2. 단위 변환 및 물성 엔진 (`UnitConverter`)

모든 내부 연산은 **SI 표준 단위**를 사용하며, 입출력 시에만 설정된 단위계에 따라 변환합니다.

| 물리량 | 내부 표준 단위 (SI) | METRIC (사용자용) | IMPERIAL (사용자용) |
| :--- | :--- | :--- | :--- |
| 유량 | $m^3/s$ | L/min | GPM |
| 압력 | Pa | MPa | PSI |
| 길이/수두 | m | m | ft |
| 온도 | °C | °C | °F |

## 3. 라이브러리 및 규격 관리 (`LibraryManager`)

### 3.1 명칭 기반 내경 검색
배관 정의 시 `50A`, `2"` 등의 공칭 명칭(Nominal Size)을 입력하면, 라이브러리(`STANDARD_MATERIALS`)에서 해당 재질의 **실제 내경(Actual Diameter)**을 자동으로 찾아 할당합니다.

### 3.2 자동 피팅 손실 계산 (Auto-Fitting)
두 배관 노드의 벡터를 분석하여 꺾임각을 계산하고, 이에 적합한 K-factor(예: 90도 엘보 = 0.9)를 자동으로 산출하여 `Pipe.auto_fittings_k`에 반영합니다.

## 4. 모듈 간 인터페이스

*   **Compiler -> Solver:** `FluidSystem` 객체를 전달. 위상 구조와 물성 정보 포함.
*   **Solver -> Reporter:** 시뮬레이션 결과가 주입된 `FluidSystem` 객체 전달.
*   **ProjectManager -> GUI:** DB 쿼리 결과 및 실시간 에러 로그 전달.

---
[목차로 돌아가기](./INDEX.md)
