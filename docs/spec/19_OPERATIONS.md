# 19. 운영 및 배포 (Operations & Deployment) 명세 (A14)

FHDL 시스템의 안정적인 실행과 유지보수를 위한 환경 설정 및 운영 절차를 정의합니다.

## 1. 시스템 요구사항 및 설치

### 1.1 하드웨어 요구사항
*   **CPU:** 듀얼 코어 이상 (i5급 권장)
*   **RAM:** 4GB 이상 (8GB 권장)
*   **Disk:** 최소 100MB 이상의 여유 공간

### 1.2 소프트웨어 환경 (Stack)
*   **Runtime:** Python 3.10 이상
*   **GUI Framework:** PySide6 (Qt for Python)
*   **Graph Engine:** NetworkX 3.0+
*   **Database:** SQLite 3.x (내장형)

## 2. 환경 설정 및 로그 관리

### 2.1 환경 변수
*   `FHDL_HOME`: 프로젝트 데이터 및 라이브러리가 저장되는 루트 디렉토리.
*   `FHDL_LOG_LEVEL`: 로그 출력 수준 (DEBUG, INFO, WARNING, ERROR). 기본값: INFO.

### 2.2 로그 정책
*   **포맷:** `[Timestamp] [Level] [Module] Message`
*   **파일 관리:** `logs/fhdl.log`에 순환 저장 (최대 10MB, 백업 5개 유지).

## 3. 배포 및 업데이트 절차

### 3.1 배포 패키징
*   `PyInstaller` 또는 `Nuitka`를 사용하여 독립 실행형 실행 파일(.exe, .app)로 패키징합니다.
*   배포 파일에는 `STANDARD_MATERIALS` 라이브러리 파일이 반드시 포함되어야 합니다.

### 3.2 버전 관리 정책 (SemVer)
*   **MAJOR:** DSL 문법의 파괴적 변경 또는 아키텍처 재설계 시.
*   **MINOR:** 새로운 물리 공식 추가 또는 기능 확장 시.
*   **PATCH:** 버그 수정 및 성능 최적화 시.
## 4. 상세 운영 절차 (Runbook)

### 4.1 [S-OPS-001] 시스템 기동 및 초기화 (Startup)
1.  **Environment Check:** `FHDL_HOME` 및 필수 라이브러리(`PySide6`, `NetworkX`) 로드 확인.
2.  **Journal Check:** `.journal` 파일 존재 여부 확인. 존재 시 `Journal Recovery` 모드 자동 진입.
3.  **Cache Sync:** `state.db`의 최종 업데이트 시간과 `.fhd` 소스 파일의 수정 시간을 대조하여 불일치 시 백그라운드 재파싱 트리거.

### 4.2 [S-OPS-002] 정상 종료 및 상태 저장 (Shutdown)
1.  **State Save:** 현재 작업 중인 모든 프로젝트의 `Dirty` 상태를 확인하고 사용자에게 저장 여부 확인.
2.  **Resource Release:** SQLite 연결 해제, 비동기 솔버 쓰레드 안전 종료(Join), 임시 저널 파일 삭제.
3.  **Exit Flag:** `project_meta`의 `journal_status`를 `CLEAN`으로 업데이트 후 프로세스 종료.

### 4.3 [S-OPS-003] 장애 복구 및 캐시 재빌드 (Recovery)
*   **저널 자동 복구:** 비정상 종료 감지 시 `.journal` 내의 `LogRecord`를 순차 실행하여 마지막 성공 트랜잭션까지 메모리 모델을 복원한다.
*   **수동 캐시 초기화:** `state.db` 손상이나 원문 불일치 발생 시 다음 절차를 따른다.
    1.  애플리케이션 종료.
    2.  `cache/state.db` 파일 수동 삭제.
    3.  애플리케이션 재기동 시 `.fhd` 원문을 처음부터 재파싱하여 `state.db` 및 그래프 모델 강제 재생성.

### 4.4 [S-OPS-004] 안전 모드 (Safe Mode) 전환
*   **진입 조건:** GUI 렌더링 엔진 실패 또는 연속적인 `SyncError` 발생 시.
*   **동작:** 캔버스 시각화를 비활성화하고, 텍스트 에디터와 CLI 로그 기반의 최소 기능 모드로 운영을 지속하여 데이터 손실을 방지한다.

---
[목차로 돌아가기](./INDEX.md)
