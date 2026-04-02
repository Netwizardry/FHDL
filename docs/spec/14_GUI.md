# 15. 사용자 인터페이스 (GUI & Visualization) 명세

FHDL GUI는 텍스트 기반 설계를 지원하는 통합 개발 환경(IDE)으로, 실시간 설계 검증과 비동기 해석 엔진을 제공합니다.

## 1. 메인 레이아웃 및 구성 요소

| 구성 요소 | 역할 | 상세 기능 |
| :--- | :--- | :--- |
| **FHDL Editor** | 코드 작성 | 구문 강조, 비동기 린팅, 에러 하이라이팅 |
| **Result Viewer** | 결과 시각화 | 계산 결과의 테이블 표시 및 캔버스 상의 경고 시각화 |
| **System Log** | 상태 모니터링 | 해석 진행 상황, 경고(Vacuum, Cavitation) 및 에러 로그 출력 |
| **Dictionary** | 도움말 | FHDL 주요 문법 및 키워드에 대한 빠른 참조 패널 |

## 2. 반응성 및 동기화 전략 (UX & Sync - C02)

### 2.1 비동기 린팅 (Async Linter)
대규모 문서 편집 시 타이핑 반응성을 보장하기 위해 다음 전략을 적용합니다.
*   **Worker Thread:** 린팅 엔진(`FHDLLinter`)은 메인 UI 쓰레드와 분리된 워커 쓰레드에서 비동기적으로 동작합니다.
*   **Debounce:** 사용자가 타이핑을 멈춘 후 **300ms**가 경과했을 때만 린팅 프로세스를 시작하여 불필요한 계산을 방지합니다.
*   **Interruptible:** 새로운 타이핑 이벤트 발생 시 진행 중인 린팅 작업을 즉시 취소하고 대기 상태로 전환합니다.

### 2.2 진단 시각화 및 스타일 가이드 (Visualization - T01)
네트워크 캔버스에서 각 진단 항목은 다음과 같은 시각적 스타일로 설계자에게 고지됩니다.

| 상태 | 시각적 표현 | 비고 |
| :--- | :--- | :--- |
| **Normal** | Blue/Gray Line | 정상 작동 배관 |
| **Warning (Velocity)** | Orange Thicker Line | 유속 초과 (WRN001) |
| **Warning (Vacuum)** | Purple Blinking Node | 진공/캐비테이션 위험 (WRN003) |
| **Error (Disconnected)** | Red Dashed Line | 연결 단절 (NET001) |
| **Calculated Flow** | Moving Arrows | 유량 방향 및 상대적 크기 표시 |

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
