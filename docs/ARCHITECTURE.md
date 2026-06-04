# FHDL 아키텍처

> 본 문서는 **현재 소스코드(`src/fhdl/`) 기준**으로 작성된다. 구 명세는 `archive/`.

## 계층 구조

```
사용자 입력 (DSL 텍스트 / GUI 편집 / 명령 콘솔)
        │
        ▼
   core (해석 엔진, GUI 비의존)
   ├─ parser.py        FHDL 텍스트 → AST
   ├─ semantic.py      AST → EntityMap (단위 정규화·기본값·참조검사·재질물성)
   ├─ solver.py        EntityMap → 수리 해석 결과 (2-Pass)
   ├─ pipeline.py      Parse→Semantic→Solve→Report 오케스트레이션
   ├─ report_generator.py  결과 → CSV/JSON
   ├─ models.py        데이터 모델 (Entity·결과·진단)
   ├─ language.py      언어 정의 단일 진실원 (키워드·노드타입·단위)
   ├─ fittings.py      부속 K-factor 단일 진실원
   ├─ materials.py     배관 재질 물성 단일 진실원
   ├─ units.py         표시 단위 변환 (METRIC/IMPERIAL)
   ├─ dsl_editor.py    DSL 텍스트 인플레이스 편집 (Inverse Sync)
   ├─ command.py       콘솔 명령 인터프리터
   └─ project_io.py    프로젝트 저장/로드/복원
        │
        ▼
   db (영속성)
   ├─ project_db.py    프로젝트별 state.db (결과 캐시 + 저널)
   └─ library_db.py    전역 부품 라이브러리 data/library.db (CRUD)
        │
        ▼
   gui (PySide6)
   ├─ main_window.py   5패널 + 하단 콘솔 + 메뉴/단축키 + FSM
   ├─ panels/          project · editor · viewer(2.5D) · results · diagnostics
   ├─ log_console.py   로그 + 명령 입력 콘솔(TUI)
   ├─ library_dialog.py 부품 라이브러리 CRUD 다이얼로그
   └─ highlighter.py   DSL 구문 강조
```

## 핵심 원칙

1. **단일 진실원(SSOT)**: 입력은 `main.fhd`(DSL 텍스트). 언어 키워드·부속·재질은 `core/language.py`·`core/fittings.py`·`core/materials.py` 한 곳에서만 정의하고 parser·highlighter·GUI·DB가 모두 참조한다.
2. **엔진/표시 단위 분리**: 내부 계산은 SI(유량 m³/s, 압력 Pa, 길이·수두·관경 m). 표시는 `units.py`가 `unit_system`에 따라 변환.
3. **엣지의 진실원은 배관**: `pipe.start_id→end_id` 가 토폴로지를 정의. `connect` 는 정합성 검증용(`NET006`).
4. **결과 캐시**: `state.db` 는 재계산으로 재생성 가능한 파생 캐시. 코드(`main.fhd`)와 체크섬으로 연결.
5. **GUI ↔ 명령 공유**: 메뉴/그래프 편집과 콘솔 명령이 동일한 `dsl_editor` 동작을 공유.

## 해석 파이프라인 (`pipeline.AnalysisPipeline.run`)

```
Parse ──(SYN)──▶ Semantic ──(SEM)──▶ Solve ──(NET/CAL/WRN)──▶ Report
```
- 각 단계에서 차단(ERROR/FATAL) 진단 발생 시 즉시 반환.
- 반환값 `AnalysisResult`: `entity_map`, `node_results`, `pipe_results`, `summary`, `diagnostics`, `status`(OK/PARTIAL/FAILED).

## GUI 비동기

해석은 `gui/worker.py`(QRunnable)에서 백그라운드 실행. `status_update`/`finished`/`error` 시그널로 UI 갱신. 상태 기계(AppState): IDLE/DIRTY/VALIDATING/SOLVING/SOLVED/SAVED/… .

관련 문서: [LANGUAGE](LANGUAGE.md) · [SOLVER](SOLVER.md) · [DATA_MODEL](DATA_MODEL.md) · [GUI](GUI.md) · [DIAGNOSTICS](DIAGNOSTICS.md)
