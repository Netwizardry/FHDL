# 20. 저장소 스키마 및 직렬화 명세 (C01)

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL 시스템의 영속성 계층(`Storage Layer`)에서 사용하는 데이터베이스 스키마와 데이터 매핑 규칙을 정의합니다.

## 1. SQLite 데이터베이스 스키마 (`state.db`)

계산 결과의 빠른 조회와 GUI 상태 유지를 위해 다음 테이블을 사용한다.

### 1.1 [S-STO-001] `nodes_result` (노드 해석 결과)
```sql
CREATE TABLE nodes_result (
    node_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    x REAL, y REAL, z REAL NOT NULL, -- 공간 좌표 반영
    head_total REAL,                 -- 총수두 (m)
    p_gauge REAL,                    -- 게이지 압력 (Pa)
    flow_req REAL,                   -- 요구 유량 (m3/s)
    sizing_mode TEXT,                -- 'MANUAL', 'AUTO', 'DERIVED'
    provenance_formula TEXT,         -- 적용 계산식 ID
    diagnostic_code TEXT             -- 발생 오류/경고 코드
);
```

### 1.2 [S-STO-002] `pipes_result` (배관 해석 결과)
```sql
CREATE TABLE pipes_result (
    pipe_id TEXT PRIMARY KEY,
    start_node TEXT NOT NULL,
    end_node TEXT NOT NULL,
    diameter REAL NOT NULL,
    velocity REAL,
    h_loss_total REAL,               -- 마찰+국부 손실 수두 (m)
    surge_index REAL,                -- 수충격 위험 지수 (v0.1 간이 지표)
    status TEXT,                     -- 'OK', 'WARNING', 'ERROR'
    sizing_mode TEXT                 -- 'MANUAL', 'AUTO'
);
```

### 1.3 [S-STO-003] `project_meta` (프로젝트 메타데이터)
```sql
CREATE TABLE project_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT,                   -- 파일 무결성 검증용 SHA-256
    journal_status TEXT              -- 'CLEAN', 'DIRTY', 'RECOVERING'
);
```

## 2. 객체 직렬화 (Serialization) 명세

### 2.1 [S-STO-004] 프로젝트 JSON 구조 및 체크섬
프로젝트 설정 및 캐시는 `project.meta.json`에 다음 형식으로 직렬화된다.
*   **Schema Version:** 데이터 구조 버전 (예: `1.0.0`).
*   **Global Settings:** 유체 종류, 온도, 전역 마찰 모델(`DW/HW`).
*   **Atomic Info:** 마지막 성공 저장 시점의 파일 체크섬 및 저널 시퀀스 번호.

### 2.2 바이너리 직렬화 (Optional)
대규모 그래프 데이터의 경우 성능을 위해 `pickle` 또는 `msgpack` 형식을 사용할 수 있으나, 최종 결과물은 항상 SQL 또는 JSON으로 역직렬화가 가능해야 합니다.

---
[목차로 돌아가기](./INDEX.md)
