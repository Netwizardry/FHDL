# 데이터 모델 · DB · 영속성

> 구현: `core/models.py`, `db/project_db.py`, `db/library_db.py`, `core/project_io.py`.

## 엔티티 모델 (`core/models.py`)

- `FluidConfig` — unit_system, fluid_type, temp, altitude, friction_model + 물성 property.
- `TankEntity` / `PumpEntity` / `JunctionEntity` / `TerminalEntity` — 공통 `entity_id, elevation(z), x, y, span`.
- `PipeEntity` — `start_id, end_id, length, diameter(SizingState), material, roughness, c_factor, manual_k, auto_k`; `total_k = manual_k + auto_k`.
- `ConstraintConfig` — velocity_min/max, safety_factor_head/npsh.
- `EntityMap` — 타입별 dict + `connections: List[(from,to)]`.
- 결과: `NodeCalcResult`(좌표·타입·수두·압력·NPSHa·절대해발·대기압), `PipeCalcResult`(start/end·유량·유속·손실·관경·K·수충격·상태), `SystemSummary`.
- 진단: `DiagnosticItem`(code, severity, message, source_span, related_id).

## 프로젝트 폴더 구조

```
projects/<name>/
├── main.fhd        # 입력 진실원 (DSL)
├── state.db        # 결과 캐시 + 저널 (재생성 가능)
├── project.fhproj  # 메타 (JSON: 이름·일시·last_analyzed·source_checksum)
└── outputs/        # 내보낸 리포트 (CSV/JSON)
```

## 프로젝트 DB (`state.db`)

| 테이블 | 내용 |
|---|---|
| `nodes_result` | node_id, type, x, y, z, head, p_gauge, flow_req/actual, npsha, abs_altitude, atm_pressure |
| `pipes_result` | pipe_id, **start_node, end_node**, diameter, velocity, flow, h_loss_total, surge_index, status, k_total, k_auto |
| `system_summary` | total_flow, total_head, worst_path, pump_flow/head, tank_volume, status |
| `diagnostics` | code, severity, message, related_id, source_line/col |
| `project_meta` | key/value (analyzed_checksum, 저널 상태 등) |

- **원자적 저장**: `atomic_save_fhd`(stage→verify(체크섬)→swap).
- **저널**: WAL + `journal_status`(DIRTY/CLEAN)로 중단 복구.
- 노드/배관 결과에 **타입·좌표·엣지(start/end)** 를 저장하므로 DB만으로 그래프 복원 가능.

## 전역 라이브러리 DB (`data/library.db`)

테이블: `pipe_sizes`, `pipe_materials`, `fitting_kfactors`, `pump_curves`, `pump_curve_points`, `fluid_properties`.
- 시드: 관경(KS), 재질(`core/materials`), 부속(`core/fittings`), 물성(물 0~100°C).
- **CRUD**: 각 테이블 `list_/upsert_/delete_` (GUI 부품 라이브러리 관리 다이얼로그에서 사용).

## 저장/로드/복원 (`core/project_io.py`)

- `save_project(dir, source, result=None, write_fhd=True)`:
  - `write_fhd=True`: `main.fhd` 원자적 저장 + `project.fhproj` 갱신.
  - `result` 있으면 `state.db` 캐시 + `analyzed_checksum` 기록.
  - 분석 직후엔 `write_fhd=False` 로 파일 보존, 결과만 캐시.
- `load_project(dir) -> ProjectLoad(source, result, meta, cache_valid)`:
  - `cache_valid = SHA256(main.fhd) == analyzed_checksum`.
  - 유효하면 **소스 파싱(entity_map) + DB 결과 로드**로 재계산 없이 복원.
  - 코드 변경(체크섬 불일치) 시 `result=None` → 재해석 유도.
