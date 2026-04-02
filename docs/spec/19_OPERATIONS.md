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
## 4. 장애 복구 및 데이터 관리 (A14/M01)

### 4.1 원자적 저장 및 저널링 (Atomic Save with Journaling)
파일 저장(`Save`) 요청 시 시스템은 다음의 4단계 저널링을 수행합니다.
1.  **Stage 1 (Write Temp):** 신규 데이터를 `main.fhd.tmp` 파일에 기록.
2.  **Stage 2 (Verify Temp):** `tmp` 파일의 크기와 체크섬이 정상인지 검증.
3.  **Stage 3 (Backup Old):** 기존 `main.fhd`를 `main.fhd.bak`으로 이름 변경.
4.  **Stage 4 (Commit):** `main.fhd.tmp`를 `main.fhd`로 최종 변경.

*   **실패 시 복구 (Recovery):**
    *   Stage 1/2 실패 시: 사용자에게 오류 알림 후 현재 문서 유지.
    *   Stage 3/4 실패 시: `.bak` 파일을 원본으로 복구(Rollback)하여 마지막 정상 상태 유지.

### 4.2 캐시 초기화 및 재생성
...
*   시스템 불일치(SyncError) 발생 시 `cache/state.db` 파일을 삭제하면 다음 실행 시 모든 설계 데이터가 원문으로부터 재생성됩니다.

---
[목차로 돌아가기](./INDEX.md)
