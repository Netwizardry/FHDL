# 06. 사용자 인터페이스 (GUI & Visualization) 명세

FHDL GUI는 텍스트 기반 설계를 지원하는 통합 개발 환경(IDE)으로, 실시간 설계 검증과 비동기 해석 엔진을 제공합니다.

## 1. 메인 레이아웃 및 구성 요소

| 구성 요소 | 역할 | 상세 기능 |
| :--- | :--- | :--- |
| **FHDL Editor** | 코드 작성 | 구문 강조(Syntax Highlighting), 실시간 린팅, 에러 줄 표시 |
| **Result Viewer** | 결과 시각화 | 시뮬레이션 완료 후 노드/배관 데이터의 테이블 및 그래픽 표시 |
| **System Log** | 상태 모니터링 | 해석 진행 상황, 경고(Vacuum, Cavitation) 및 에러 로그 출력 |
| **Dictionary** | 도움말 | FHDL 주요 문법 및 키워드에 대한 빠른 참조 패널 |

## 2. 핵심 워크플로우

### 2.1 비동기 해석 프로세스 (Analysis Pipeline)
사용자가 `Run` 버튼을 클릭하면 해석 스레드(`AnalysisWorker`)가 생성되어 UI 프리징 없이 백그라운드에서 다음 과정을 수행합니다.
1.  **Linter Check:** 에디터 내 텍스트의 구문 오류 선행 검사.
2.  **Parsing & Synthesis:** DSL을 메모리 모델로 변환 및 Pass 1 해석.
3.  **Solver Execution:** Newton-Raphson 반복법을 통한 Pass 2 해석.
4.  **Reporting:** 결과를 `outputs/` 폴더에 파일로 저장.
5.  **UI Update:** 결과를 `ResultViewer`에 주입하여 사용자에게 표시.

### 2.2 실시간 피드백 및 에러 처리
*   **실시간 린팅:** 사용자가 타이핑을 멈춘 후 500ms가 지나면 `FHDLLinter`가 실행되어 문법 오류를 상태바에 표시합니다.
*   **에러 트래킹:** 해석 중 에러 발생 시 로그 창에 상세 메시지를 출력하고, 에디터의 해당 줄을 빨간색으로 하이라이트합니다.

## 3. 조작 인터페이스

*   **툴바:** 프로젝트 생성, 열기, 저장 및 해석 실행/중단(`Run`, `Stop`) 버튼 제공.
*   **상태바:** 현재 시스템 상태(Ready, Analysis Complete), 단위계 및 마지막 저장 상태 표시.
*   **팝업 가이드:** 중요한 환경 설정 변경이나 저장되지 않은 변경 사항이 있을 때 확인 다이얼로그 출력.

## 4. 시각화 기술 스택
*   **Framework:** PySide6 (Qt for Python).
*   **Editor:** `QTextEdit` 기반의 커스텀 하이라이터 적용.
*   **Viewer:** `QTableWidget` 또는 전용 시각화 위젯(3D 뷰어 포함 가능 구조).

---
[목차로 돌아가기](./INDEX.md)
