# FHDL 명세서 품질 보정 To-do List (v4.0)

## 1. 우선순위: Critical (즉시 조치)

### 1.1 DB 스키마 및 직렬화 명세 추가 (C01) - [진행 중]
*   **파일:** `20_STORAGE_SCHEMA.md` 신설 및 `INDEX.md` 반영.
*   **내용:** SQLite DDL 및 JSON 직렬화 구조 정의.

### 1.2 비동기 통신 및 쓰레드 안정성 명세 (C02)
*   **파일:** `04_ARCHITECTURE.md`
*   **내용:** GUI-Solver 간 Async Messaging Contract (Signal/Slot) 추가.

## 2. 우선순위: Major (기반 보강)

### 2.1 저장 장애 복구(Journaling) 전략 (M01)
*   **파일:** `19_OPERATIONS.md`
*   **내용:** `.bak` 파일 및 원자적 저장 실패 시 롤백 절차 상세화.

### 2.2 증분 업데이트(Incremental Sync) 정책 (M02)
*   **파일:** `05_EXECUTION_FLOW.md`
*   **내용:** 전체 재파싱 대신 변경된 블록만 반영하는 전략 수립.

## 3. 우선순위: Trivial (문서 정비)

### 3.1 전수 링크 및 번호 동기화 (T01)
*   **파일:** 전 파일
*   **내용:** INDEX.md와 모든 파일의 내부 헤더 번호 및 상호 참조 링크 일치화.
