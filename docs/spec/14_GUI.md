# 15. 사용자 인터페이스 (GUI & Visualization) 명세

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL GUI는 텍스트 기반 설계를 지원하는 통합 개발 환경(IDE)으로, 실시간 설계 검증과 비동기 해석 엔진을 제공합니다.

## 1. 메인 레이아웃 및 5대 핵심 패널 (Standard Layout)

FHDL GUI는 `03_UI_UX_REQ.md`에서 정의한 5대 패널 체제를 엄격히 준수하며, 각 패널은 독립적인 위젯 클래스로 구현된다.

| ID | 패널 명칭 (Panel Name) | 주요 역할 및 기능 |
| :--- | :--- | :--- |
| **S-GUI-001** | **Project Selection** | 파일 I/O, 최근 프로젝트 목록, 샘플 로드 (Sidebar 상단) |
| **S-GUI-002** | **FHDL Editor** | 구문 강조, 비동기 린팅, 에러 하이라이팅 (Center-Left) |
| **S-GUI-003** | **Topology Viewer** | 네트워크 그래프 시각화, 최불리 경로 강조 (Center-Right) |
| **S-GUI-004** | **Result Dashboard** | 수치 해석 결과 테이블, 선정 근거 툴팁 (Bottom-Left) |
| **S-GUI-005** | **Error/Warning Center** | 진단 메시지 통합 표시, 소스 점프 기능 (Bottom-Right) |

## 2. 반응성 및 성능 규범 (Performance & UX)

### 2.1 [S-GUI-006] 비동기 반응성 가이드
*   **Debounce:** 텍스트 입력 시 린팅 프로세스 시작 전 **300ms**의 대기 시간을 유지하여 입력 지연을 방지한다.
*   **Worker Threading:** 모든 I/O 및 솔버 계산은 메인 UI 쓰레드와 분리된 `QThread`에서 수행되어야 한다.

### 2.2 [S-GUI-007] 성능 측정 및 벤치마크 환경
비기능 요구사항(`R-NFR-009`) 검증을 위해 다음 도구와 환경을 사용한다.
*   **측정 도구:** Qt Test Framework, `timeit` 모듈 및 전용 프레임 프로파일러.
*   **기준 환경:** CPU 4-Core 2.5GHz, RAM 8GB 이상.
*   **데이터셋:** 1,000개 노드 이상의 복합 네트워크 데이터셋(`benchmarks/scale_test.fhd`).

### 2.3 [S-GUI-008] 진단 시각화 및 스타일 가이드

네트워크 캔버스에서 각 진단 항목은 다음의 시각적 스타일을 따른다.

| 상태 | 시각적 표현 | 대응 진단 코드 |
| :--- | :--- | :--- |
| **Normal** | Blue/Gray (Solid) | - |
| **Warning (Velocity)** | Orange (Thick Solid) | `WRN001` |
| **Warning (Cavitation)** | Purple (Blinking) | `WRN003` |
| **Warning (Surge)** | Yellow (Dashed) | `WRN004` |
| **Error (Topology)** | Red (Thick Dashed) | `NET001~005` |

## 3. 핵심 워크플로우

### 3.1 비동기 해석 프로세스 (Analysis Pipeline)
사용자가 `Run` 버튼을 클릭하면 해석 스레드(`AnalysisWorker`)가 생성되어 UI 프리징 없이 백그라운드에서 다음 과정을 수행합니다.
1.  **Linter Check:** 에디터 내 텍스트의 구문 오류 선행 검사.
2.  **Parsing & Synthesis:** DSL을 메모리 모델로 변환 및 Pass 1 해석.
3.  **Solver Execution:** Newton-Raphson 반복법을 통한 Pass 2 해석.
4.  **Reporting:** 결과를 `outputs/` 폴더에 파일로 저장.
5.  **UI Update:** 결과를 `ResultViewer`에 주입하여 사용자에게 표시.

## 4. 시각화 기술 스택
*   **Framework:** PySide6 (Qt for Python).
*   **Editor:** `QTextEdit` 기반의 커스텀 하이라이터 적용.
*   **Viewer:** `QTableWidget` 또는 전용 시각화 위젯(3D 뷰어 포함 가능 구조).

---
[목차로 돌아가기](./INDEX.md)
EX.md)
