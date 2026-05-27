# FHDL 구현 실행 Todo-Checklist

**기준 문서:** PROGRAM_DESIGN.md + docs/spec (v4.0)  
**작성일:** 2026-05-27  
**상태:** 구현 진행 중

---

## Phase 1: 기반 환경 구성

- [ ] **1.1** `pyproject.toml` 생성 (의존성: PySide6, networkx, numpy, pytest)
- [ ] **1.2** `src/fhdl/__init__.py` 생성
- [ ] **1.3** `data/library.db` 초기화 스크립트 작성
- [ ] **1.4** 전역 부품 라이브러리 DB 기초 데이터 입력
  - [ ] 표준 관경 테이블 (KS 25A~300A, 7종)
  - [ ] 관 재질 테이블 (Steel, PVC, HDPE, CI, STS)
  - [ ] 피팅 K-factor 테이블 (ELBOW90, TEE, GATE, GLOBE, CHECK)
  - [ ] 유체 물성 테이블 (물, 20°C 기준값)
- [ ] **1.5** `resources/styles/dark_theme.qss` 작성
- [ ] **1.6** `main.py` 진입점 작성

---

## Phase 2: 핵심 엔진 구현 (core/)

### 2.1 models.py - 데이터 모델
- [ ] AST 모델 클래스 (`SystemNode`, `ComponentNode`, `ConnectNode`)
- [ ] Entity 모델 클래스 (`TankEntity`, `PumpEntity`, `PipeEntity`, `JunctionEntity`, `TerminalEntity`)
- [ ] `SizingState` 클래스 (mode, value, source_id)
- [ ] `DiagnosticItem` 클래스 (code, severity, message, source_span)
- [ ] `NodeResult`, `PipeResult` 결과 모델
- [ ] `AnalysisResult` 최종 반환 모델

### 2.2 parser.py - DSL 파서
- [ ] 렉서: 토큰 타입 정의 및 토큰화
- [ ] 파서: `system`, `tank`, `pump`, `pipe`, `junction`, `terminal` 블록
- [ ] 파서: `connect` 체인 (`A -> B -> C`)
- [ ] 파서: `constraint` 블록
- [ ] 에러 위치(line, col) 정확히 추적
- [ ] `SyntaxDiagnostics` 생성 (SYN001, SYN002)

### 2.3 semantic.py - 의미 분석기
- [ ] 중복 ID 검사 → SEM001
- [ ] 참조 무결성 검사 → SEM002
- [ ] 필수 속성 누락 검사 → SEM003
- [ ] 단위 정규화 (L/min→m³/s, mm→m, bar→Pa 등)
- [ ] 기본값 주입 (APPENDIX_A 참조)
- [ ] `SizingState` 생성 (`auto`/`manual` 구분)
- [ ] 가드 검사: 고도(SEM005), 온도(SEM006), 길이(SEM007)

### 2.4 network_builder.py - 네트워크 빌더
- [ ] Entity → NetworkX DiGraph 변환
- [ ] 고립 노드 검사 → NET001
- [ ] 공급원 부재 경로 검사 → NET002
- [ ] 도달 불가 노드 검사 → NET003
- [ ] 루프 탐지 (v0.1 경고) → NET004
- [ ] 순환 루프(Dead Loop) 검사 → NET005
- [ ] 꺾임각 기반 피팅 K-factor 자동 계산

### 2.5 solver.py - 수리 해석 엔진
- [ ] **Pass 1: Flow Synthesis**
  - [ ] 역방향 BFS (Terminal → Source)
  - [ ] 각 엣지 `q_design` 할당
  - [ ] `diameter=AUTO` 관경 자동 선정 (CAL005)
  
- [ ] **Pass 2: Newton-Raphson**
  - [ ] 잔차 함수 F(H, Q) 구성
  - [ ] 자코비안 J 희소 행렬 구성
  - [ ] 감쇠 계수(Damping=0.5) 적용 갱신
  - [ ] 수렴 판정: |ΔH| < 1e-4m
  - [ ] 최대 100회 반복 → CAL002 (미수렴)

- [ ] **마찰 모델**
  - [ ] Darcy-Weisbach (기본, FOR-DW-001)
    - [ ] Colebrook-White 반복 또는 Swamee-Jain 근사
  - [ ] Hazen-Williams (FOR-HW-001)
  - [ ] 국부 손실 (FOR-LOC-001)

- [ ] **사양 산정**
  - [ ] 최불리 경로 탐색 (FOR-PTH-001)
  - [ ] 펌프 양정 산정 (SF=1.1)
  - [ ] 탱크 용량 산정
  - [ ] NPSHa 계산 (FOR-NPSH-001) → WRN003
  - [ ] 수충격 위험 지수 계산 → WRN004
  - [ ] 유속 범위 검사 → WRN001
  - [ ] 말단 요구압 검사 → WRN002
  - [ ] 진공 한계 검사 → WRN005

### 2.6 report_generator.py - 리포트 생성기
- [ ] `Nodes_Report.csv` 생성 (node_id, x, y, z, head, pressure, flow_in, flow_out, npsha)
- [ ] `Pipes_Report.csv` 생성 (pipe_id, from, to, length, diameter, velocity, h_loss, surge_index, status)
- [ ] `Simulation_Summary.json` 생성 (총유량, 총양정, 최불리경로, 권장사양, provenance_map)

### 2.7 pipeline.py - 파이프라인 오케스트레이터
- [ ] `AnalysisPipeline.run()` 구현
- [ ] 단계별 FAIL 시 즉시 반환
- [ ] 전체 diagnostics 통합
- [ ] `AnalysisResult` 반환

---

## Phase 3: 데이터베이스 레이어 (db/)

### 3.1 project_db.py - 프로젝트 DB
- [ ] SQLite 연결 및 테이블 생성 (`CREATE TABLE IF NOT EXISTS`)
- [ ] `nodes_result` CRUD
- [ ] `pipes_result` CRUD
- [ ] `system_summary` CRUD
- [ ] `diagnostics` CRUD
- [ ] `project_meta` CRUD
- [ ] 원자적 저장 구현 (Stage → Verify → Swap)
- [ ] 저널링 구현 (DIRTY/CLEAN 상태 관리)
- [ ] 복구 프로세스 구현

### 3.2 library_db.py - 전역 라이브러리 DB
- [ ] `get_standard_sizes(standard)` → 관경 목록
- [ ] `get_material(material_id)` → 재질 물성
- [ ] `get_fitting_k(fitting_type, size)` → K-factor
- [ ] `get_pump_curve(curve_id)` → 펌프 커브 점
- [ ] `get_fluid_properties(fluid_type, temp)` → 유체 물성

---

## Phase 4: GUI 구현 (gui/)

### 4.1 main_window.py - 메인 윈도우
- [ ] `QSplitter` 기반 5패널 레이아웃 구현
- [ ] 상태 기계 (FSM) 구현
- [ ] 메뉴바: File, Edit, Run, View, Help
- [ ] 툴바: New, Open, Save, Run, Stop
- [ ] 상태바: 현재 FSM 상태 표시
- [ ] 패널 간 신호/슬롯 연결

### 4.2 panels/project_panel.py
- [ ] 최근 프로젝트 목록 (`QListView`)
- [ ] [새 프로젝트] 버튼 → 프로젝트명 입력 다이얼로그
- [ ] [열기] 버튼 → `QFileDialog`
- [ ] [저장] 버튼
- [ ] [환경설정] 버튼
- [ ] 프로젝트 선택 시 DSL 에디터에 파일 로드

### 4.3 panels/editor_panel.py
- [ ] `QPlainTextEdit` 기반 에디터
- [ ] `FHDLHighlighter` (QSyntaxHighlighter 서브클래스)
  - [ ] 키워드 색상 (tank, pump, pipe 등)
  - [ ] 숫자/단위 색상
  - [ ] 주석 색상
  - [ ] 문자열 색상
- [ ] `EditorGutter` (줄번호 + 에러 아이콘)
- [ ] 텍스트 변경 시 300ms debounce 후 린팅
- [ ] 에러 마커 표시
- [ ] Ctrl+Enter → 해석 실행

### 4.4 panels/viewer_panel.py
- [ ] `QGraphicsView` + `QGraphicsScene`
- [ ] 노드 렌더링 (타입별 도형 + 색상)
  - [ ] Tank: 파란 사각형
  - [ ] Pump: 녹색 원
  - [ ] Terminal: 빨간 삼각형
  - [ ] Junction: 회색 원
- [ ] 엣지 렌더링 (상태별 색상/두께)
  - [ ] Normal: 회색 실선
  - [ ] WRN001 (유속 초과): 주황 굵은선
  - [ ] WRN003 (캐비테이션): 보라 점선
  - [ ] NET001 (에러): 빨간 굵은 점선
- [ ] 마우스 휠 줌
- [ ] 드래그 패닝
- [ ] 노드 클릭 → 속성 편집 팝업
- [ ] 노드 드래그 이동 → Inverse Sync 신호
- [ ] 자동 레이아웃 (NetworkX spring_layout)

### 4.5 panels/results_panel.py
- [ ] `QTabWidget` (Summary / Details)
- [ ] Summary 탭: 총유량, 총양정, 권장 사양 카드 표시
- [ ] Details 탭:
  - [ ] 노드 결과 테이블 (sortable)
  - [ ] 배관 결과 테이블 (sortable)
- [ ] CSV 내보내기 버튼

### 4.6 panels/diagnostics_panel.py
- [ ] `QTreeWidget` (심각도별 트리)
- [ ] 아이콘: ERROR=빨간, WARNING=주황, INFO=파란
- [ ] 더블클릭 → 에디터 해당 줄 이동
- [ ] 필터: 심각도별 표시/숨김 토글

### 4.7 highlighter.py - 구문 하이라이터
- [ ] `QSyntaxHighlighter` 서브클래스
- [ ] 키워드 규칙: `tank`, `pump`, `pipe`, `junction`, `terminal`, `system`, `connect`, `constraint`
- [ ] 단위 규칙: `m`, `mm`, `LPM`, `MPa`, `kPa`
- [ ] 숫자 규칙: 정수/실수
- [ ] 주석 규칙: `//` 행 주석, `/* */` 블록 주석
- [ ] 중괄호 매칭 색상

### 4.8 worker.py - 백그라운드 워커
- [ ] `QRunnable` 기반 `AnalysisWorker`
- [ ] `WorkerSignals`: status_update, finished, error
- [ ] 스냅샷 격리 (deep copy of entity map)
- [ ] 진행률 업데이트 (0~100%)
- [ ] 취소 지원 (cancel_requested flag)

---

## Phase 5: 테스트 구현

- [ ] **T-CAL-001:** 정상상태 수압 평형 검증
- [ ] **T-ERR-005:** NPSHa 캐비테이션 진단
- [ ] **T-SYN-001:** Inverse Sync 검증
- [ ] **T-OPS-002:** 저널 기반 복구
- [ ] **T-NFR-001:** 원자적 저장
- [ ] **T-CAL-002:** Hazen-Williams 검증
- [ ] **T-REP-001:** Provenance 검증
- [ ] **T-AUTO-001:** Auto-Sizing 검증
- [ ] **T-UNIT-001:** 단위 변환 일관성
- [ ] **T-NFR-003:** 비동기 UI 검증
- [ ] **T-FLO-001:** 상태기계 흐름
- [ ] **T-ERR-001:** 진단 코드 정합성
- [ ] **T-NFR-004:** 대규모 네트워크 성능 (1000노드 < 1초)

---

## Phase 6: 통합 및 마무리

- [ ] End-to-End 테스트 (demo_project 실행)
- [ ] UI/UX 검토 및 개선
  - [ ] 다크 테마 적용
  - [ ] 아이콘 적용
  - [ ] 폰트 설정 (코드: Monospace, UI: 시스템 폰트)
- [ ] README.md 작성
- [ ] 의존성 설치 안내 (`pip install -r requirements.txt`)
- [ ] 샘플 프로젝트 데이터 (`demo_project/`) 생성

---

## 우선순위 순서

1. **P1:** Phase 1 (기반 환경) + Phase 2 (core/) - 엔진 먼저
2. **P2:** Phase 3 (db/) - 데이터 영속성
3. **P3:** Phase 4.1~4.2 (main_window + project_panel) - GUI 기본
4. **P4:** Phase 4.3~4.4 (editor + viewer) - 핵심 UI
5. **P5:** Phase 4.5~4.8 (results + diagnostics + worker) - UI 완성
6. **P6:** Phase 5 (테스트)
7. **P7:** Phase 6 (통합 마무리)
