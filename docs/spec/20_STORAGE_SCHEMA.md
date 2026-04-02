# 20. 저장소 스키마 및 직렬화 명세 (C01)

FHDL 시스템의 영속성 계층(`Storage Layer`)에서 사용하는 데이터베이스 스키마와 데이터 매핑 규칙을 정의합니다.

## 1. SQLite 데이터베이스 스키마 (`state.db`)

계산 결과의 빠른 조회와 GUI 상태 유지를 위해 다음 테이블을 사용합니다.

### 1.1 `nodes_result` (노드 해석 결과)
```sql
CREATE TABLE nodes_result (
    node_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    z REAL NOT NULL,
    head REAL,
    pressure REAL,
    flow_in REAL,
    flow_out REAL,
    diagnostic_code TEXT
);
```

### 1.2 `pipes_result` (배관 해석 결과)
```sql
CREATE TABLE pipes_result (
    pipe_id TEXT PRIMARY KEY,
    start_node TEXT NOT NULL,
    end_node TEXT NOT NULL,
    diameter REAL NOT NULL,
    velocity REAL,
    head_loss REAL,
    status TEXT -- 'OK', 'WARNING', 'ERROR'
);
```

### 1.3 `project_meta` (프로젝트 메타데이터)
```sql
CREATE TABLE project_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 2. 객체 직렬화 (Serialization) 명세

### 2.1 `FluidSystem` JSON 저장 구조
프로젝트 설정 및 캐시는 `project.meta.json`에 다음 형식으로 직렬화됩니다.
*   **Version:** 데이터 구조 버전 (Schema Version).
*   **Settings:** 유체 종류, 온도, 마찰 모델 등.
*   **Timestamp:** 마지막 저장 시간 및 체크섬.

### 2.2 바이너리 직렬화 (Optional)
대규모 그래프 데이터의 경우 성능을 위해 `pickle` 또는 `msgpack` 형식을 사용할 수 있으나, 최종 결과물은 항상 SQL 또는 JSON으로 역직렬화가 가능해야 합니다.

---
[목차로 돌아가기](./INDEX.md)
