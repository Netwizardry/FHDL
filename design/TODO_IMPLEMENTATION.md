# FHDL 구현 실행 Todo-Checklist

**기준 문서:** PROGRAM_DESIGN.md + docs/spec (v4.0)  
**작성일:** 2026-05-27  
**최종 검수:** 2026-06-04  
**상태:** MVP(v0.2) 구현 완료 · 일부 항목 v0.2+ 이월

---

## 검수 현황 (2026-06-04) — 아래 체크박스보다 본 섹션이 우선

> 코드를 직접 실행해 확인한 결과. 본 요약이 단일 진실원이다.

| Phase | 상태 | 비고 |
| :--- | :--- | :--- |
| 1. 기반 환경 | ✅ 완료 | main.py, pyproject.toml, requirements*.txt, data/library.db, dark_theme.qss 모두 존재·동작 |
| 2. 핵심 엔진 (core) | ✅ 완료 | parser/semantic/solver/pipeline/report 구현. **NET001~005 전수 구현**(solver `_validate_network`, networkx 기반). network_builder는 solver에 통합 |
| 3. DB 레이어 | ✅ 완료 | project_db(WAL·journal DIRTY/CLEAN), library_db CRUD |
| 4. GUI (5패널) | ✅ 완료 | main_window FSM + 5패널 + worker, 외부 QSS 다크 테마 적용 |
| 5. 테스트 | 🔶 부분 | pytest **29개 통과**(파서/DB/솔버/유량 회귀 + 네트워크 진단·다중 토폴로지 10건). Phase 5의 13개 명명 시나리오는 일부만 충족 |
| 6. 통합·마무리 | 🔶 부분 | README·데모·테마 완료. 아이콘 리소스·일부 명명 테스트 미완 |

### 2026-06-04 세션 수정 사항
- 🐛 **solver 유량 분배 버그 수정**: 분기 배관이 분기점 전체 유량을 받던 문제 → 말단(end_id) 기준 분배로 정정 (`trunk=140, branch=80/60 lpm` 검증)
- 🐛 **Pass 2 마찰손실 미반영 수정**: 노드 맵에서 파이프 ID로 유량을 조회해 항상 0이던 문제 → `pipe_q` 맵 일관 전달
- 🐛 **최불리 경로 손실 과대계산 수정**: 전체 배관 손실 합산 → 실제 worst path만 합산
- ➕ 회귀 테스트 2건 추가(`test_branch_flow_split`, `test_friction_reflected_in_head`)
- ➕ `README.md`, `requirements.txt`, `requirements-dev.txt`, `resources/styles/dark_theme.qss` 신규

### 2026-06-04 (2차) 네트워크 진단 구현
- ➕ **NET001(고립)·NET003(도달 불가)·NET004(복합 루프 경고)·NET005(Dead Loop)** 전수 구현 (solver `_validate_network`, networkx SCC/도달성 기반)
- 🔧 NET001 오용(말단 없음 → NET001) 수정: 말단 없음은 WRN002로 재분류, NET001은 고립 노드 전용
- ➕ 테스트 `tests/test_network.py` 10건: NET 진단 4종 + 다중 분기·다중 급수·다중 출력·고도 변경

### 2026-06-04 (3차) 부품·수치해석 연동
- ➕ **펌프 양정 주입**: MANUAL `head` 펌프를 해석에서 실제 에너지원으로 (흡입수두+양정).
  AUTO 펌프는 사양 선정 대상으로 유지. (solver `_pump_supply_heads`)
- ➕ **명명 부속(fitting) 지원**: `pipe { fittings = [ELBOW90, GATE_VALVE, ELBOW90*2]; }`
  파싱 → 라이브러리 K 합산 → `manual_k` 연동. 단일 진실원 `core/fittings.py` 신설,
  `library_db` 도 이를 참조(중복 제거).
- ➕ **auto_k**: connect 경로 꺾임각(좌표·고도 기반)으로 엘보 K 자동 산정 (`_compute_auto_fitting_k`).
- ➕ 테스트 +9 (test_fittings 8 + 펌프양정/auto_k 2). 총 55개 통과.

### 2026-06-04 (4차) 해발고도 datum & 대기압 연동
- ➕ **프로젝트 기준 해발(datum)**: system `altitude` 를 기준점으로, 노드 `z` 는 datum 상대값.
  절대 해발 = altitude + z. SEM005 가드를 절대 해발 기준으로 검사.
- ➕ **해발+온도 → 대기압**: `FluidConfig.atm_pressure_at(절대해발)` 노출, solver 가 노드별
  실제 해발로 대기압 산정 (NPSHa, 진공 한계 WRN005에 반영).
- 🐛 **NPSHa 공식 버그 수정**: 기존 식은 대기압 항이 상쇄되어 해발 무반응이었음 →
  `NPSHa = 대기압수두 + 흡입정수두 − 증기압수두` 로 정정 (해발·온도 모두 반영).
- ➕ GUI 새 프로젝트 다이얼로그: 기준 해발고도·온도 입력 → 템플릿/`.fhproj` 반영.
- ➕ 테스트 +4 (대기압·해발/온도 NPSHa·datum 가드). 총 59개 통과.

### v0.2+ 이월 항목
- Phase 5 명명 테스트 전수(T-OPS-002 저널 복구, T-NFR-004 1000노드 성능 등)
- GUI 아이콘 리소스 세트
- 토폴로지 뷰어 NET003~005 엣지/노드 색상 구분 렌더링
- 펌프 커브(curve_id) 기반 운전점 해석 (현재는 고정 양정만)
- 흡입관 마찰손실을 반영한 펌프 흡입수두 정밀화

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
