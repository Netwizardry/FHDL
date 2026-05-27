# FHDL 프로그램 설계 문서

**버전:** v1.0  
**작성일:** 2026-05-27  
**기반 명세:** docs/spec (v4.0)  
**상태:** Active

---

## 1. 설계 개요

FHDL은 유체 설비 설계자가 DSL(Domain-Specific Language)로 배관망을 선언하면, 자동으로 수리 계산을 수행하여 관경, 펌프 양정, 탱크 용량 등의 설계 사양을 산정하는 Python 기반 데스크톱 애플리케이션이다.

### 1.1 핵심 설계 목표

1. **계층 분리:** UI ↔ 엔진 분리, 단방향 데이터 흐름
2. **비동기 처리:** 계산 중 UI 프리징 방지
3. **프로젝트별 저장:** 각 프로젝트는 독립 SQLite DB
4. **재사용 가능 부품 DB:** 관 규격, 재질, 피팅 K-factor 등의 전역 라이브러리

---

## 2. 디렉토리 구조

```
FHDL/
├── CLAUDE.md                      # 프로젝트 메타 문서
├── main.py                        # 진입점
├── src/
│   └── fhdl/
│       ├── __init__.py
│       ├── core/                  # 핵심 계산 엔진 (GUI 무관)
│       │   ├── __init__.py
│       │   ├── models.py          # 데이터 모델 (AST, Entity, Diagnostic)
│       │   ├── parser.py          # DSL 렉서/파서
│       │   ├── semantic.py        # 의미 분석 + 단위 정규화
│       │   ├── network_builder.py # Entity → NetworkX 그래프
│       │   ├── solver.py          # 2-Pass 수리 해석 (Newton-Raphson)
│       │   ├── report_generator.py# 결과 → CSV/JSON 출력
│       │   └── pipeline.py        # 파이프라인 오케스트레이터
│       ├── db/
│       │   ├── __init__.py
│       │   ├── project_db.py      # 프로젝트별 SQLite DB (state.db)
│       │   └── library_db.py      # 전역 부품 라이브러리 DB
│       └── gui/
│           ├── __init__.py
│           ├── main_window.py     # 5패널 메인 윈도우
│           ├── panels/
│           │   ├── project_panel.py    # 좌: 프로젝트 선택
│           │   ├── editor_panel.py     # 중좌: DSL 에디터
│           │   ├── viewer_panel.py     # 중우: 토폴로지 뷰어
│           │   ├── results_panel.py    # 하좌: 결과 대시보드
│           │   └── diagnostics_panel.py # 하우: 진단 패널
│           ├── highlighter.py     # DSL 구문 하이라이터
│           └── worker.py          # QThread 기반 백그라운드 워커
├── data/
│   └── library.db                 # 전역 부품 라이브러리 (SQLite)
├── tests/
│   ├── test_parser.py
│   ├── test_semantic.py
│   ├── test_solver.py
│   ├── test_pipeline.py
│   └── benchmarks/
│       └── scale_test_generator.py
└── resources/
    └── styles/
        └── dark_theme.qss
```

---

## 3. 핵심 모듈 설계

### 3.1 `models.py` - 데이터 모델

```python
# --- Layer 1: AST Models ---
@dataclass
class SystemNode:     # system { ... }
@dataclass
class ComponentNode:  # tank/pump/pipe/junction/terminal
@dataclass
class ConnectNode:    # connect A -> B -> C

# --- Layer 2: Entity Models (정규화 완료) ---
@dataclass
class FluidConfig:    # 유체 설정 (온도, 종류, 단위계)
@dataclass
class TankEntity:     # 탱크 (elevation, volume, level_max)
@dataclass
class PumpEntity:     # 펌프 (elevation, flow, head, curve_id, npshr)
@dataclass
class PipeEntity:     # 배관 (length, diameter, material, c_factor)
@dataclass
class JunctionEntity: # 분기점 (elevation)
@dataclass
class TerminalEntity: # 말단 (elevation, required_q, required_p, k_factor)

# --- Layer 3: SizingState ---
@dataclass
class SizingState:
    mode: Literal["MANUAL", "AUTO", "DERIVED"]
    value: float        # SI 단위 수치
    source_id: str = "" # 선정 근거 ID

# --- Layer 4: Diagnostic ---
@dataclass
class DiagnosticItem:
    code: str
    severity: Literal["INFO", "WARNING", "ERROR", "FATAL"]
    message: str
    source_span: dict   # {line, col}
    related_id: str = ""
    suggested_action: str = ""

# --- Layer 5: Result Objects ---
@dataclass
class NodeResult:
    node_id: str
    head_total: float
    p_gauge: float
    flow_out: float
    npsha: float
    sizing_mode: str

@dataclass
class PipeResult:
    pipe_id: str
    flow: float
    velocity: float
    h_loss_f: float
    h_loss_k: float
    diameter: float
    surge_index: float
    status: str
    formula_id: str     # 사용된 공식 ID

@dataclass
class AnalysisResult:
    status: Literal["OK", "FAILED", "PARTIAL"]
    node_results: list[NodeResult]
    pipe_results: list[PipeResult]
    system_summary: dict
    diagnostics: list[DiagnosticItem]
    provenance_map: dict  # {result_id: {formula_id, inputs}}
```

### 3.2 `parser.py` - DSL 파서

**입력:** FHDL DSL 텍스트 문자열  
**출력:** `List[SystemNode | ComponentNode | ConnectNode]` (AST)

```
토큰화 (Lexer)
  ↓
구문 분석 (Parser) → AST
  ↓
SyntaxDiagnostics
```

지원 키워드:
- `system`, `tank`, `pump`, `pipe`, `junction`, `terminal`
- `connect`, `constraint`
- `friction_model`, `unit_system`
- 속성: `elevation`, `flow`, `head`, `length`, `diameter`, `material`, `c_factor`

### 3.3 `semantic.py` - 의미 분석기

**입력:** AST  
**출력:** `(EntityMap, SemanticDiagnostics)`

처리 단계:
1. 중복 ID 검사 → SEM001
2. 참조 무결성 검사 (`connect`의 ID 실존 여부) → SEM002
3. 필수 속성 검사 → SEM003
4. 단위 정규화 (모든 값 → SI)
5. 기본값 주입 (APPENDIX_A)
6. `SizingState` 생성 (auto/manual 구분)
7. 가드 검사 (고도 범위, 온도 범위 등) → SEM005~007

### 3.4 `network_builder.py` - 네트워크 빌더

**입력:** EntityMap  
**출력:** `(NetworkGraph, TopologyDiagnostics)`

처리 단계:
1. Entity → NetworkX DiGraph 노드/엣지 변환
2. 고립 노드 검사 → NET001
3. 공급원 부재 검사 → NET002
4. 루프 탐지 → NET004 (v0.1 경고)
5. 순환 루프 검사 → NET005
6. 피팅 K-factor 자동 계산 (꺾임각 기반)

### 3.5 `solver.py` - 수리 해석 엔진

**입력:** NetworkGraph  
**출력:** `(CalculationStates, HydraulicDiagnostics)`

**Pass 1 - Flow Synthesis (역산):**
1. 터미널 노드에서 소스 방향 역방향 탐색 (BFS)
2. 각 엣지에 `q_design` 할당
3. `diameter = AUTO`인 경우 관경 자동 선정 (CAL005)

**Pass 2 - Hydraulic Balancing (Newton-Raphson):**
1. 초기값 설정 (Pass 1 결과 기반)
2. 잔차 함수 F(H, Q) = 0 구성
3. 자코비안 J 희소 행렬 구성
4. ΔH = -J⁻¹F 갱신 (Damping=0.5)
5. 수렴 판정: |ΔH| < 1e-4m (최대 100회)
6. NPSHa 계산 및 WRN003 발생
7. 수충격 위험 지수 계산 및 WRN004 발생
8. 펌프/탱크 사양 확정

**마찰 모델 선택:**
- `friction_model = DW` → Darcy-Weisbach (기본)
- `friction_model = HW` → Hazen-Williams

### 3.6 `pipeline.py` - 파이프라인 오케스트레이터

```python
class AnalysisPipeline:
    def run(self, source_code: str, options: dict) -> AnalysisResult:
        # 1. Parse
        ast, syn_diags = parser.parse(source_code)
        if has_fatal(syn_diags): return FAILED(syn_diags)
        
        # 2. Semantic
        entities, sem_diags = semantic.analyze(ast)
        if has_error(sem_diags): return FAILED(sem_diags)
        
        # 3. Network Build
        graph, net_diags = network_builder.build(entities)
        if has_error(net_diags): return FAILED(net_diags)
        
        # 4. Solve
        results, cal_diags = solver.solve(graph, entities)
        
        # 5. Report
        report = report_generator.generate(results)
        
        all_diags = syn_diags + sem_diags + net_diags + cal_diags
        return AnalysisResult(...)
```

---

## 4. 데이터베이스 설계

### 4.1 프로젝트 DB (`projects/{name}/state.db`)

```sql
-- 노드 계산 결과
CREATE TABLE nodes_result (
    node_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    x REAL DEFAULT 0, y REAL DEFAULT 0, z REAL NOT NULL,
    head_total REAL, p_gauge REAL,
    flow_req REAL, flow_actual REAL,
    npsha REAL,
    sizing_mode TEXT DEFAULT 'MANUAL',
    provenance_formula TEXT,
    diagnostic_code TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 배관 계산 결과
CREATE TABLE pipes_result (
    pipe_id TEXT PRIMARY KEY,
    start_node TEXT NOT NULL,
    end_node TEXT NOT NULL,
    length REAL NOT NULL,
    diameter REAL NOT NULL,
    velocity REAL, flow REAL,
    h_loss_f REAL, h_loss_k REAL,
    surge_index REAL,
    status TEXT DEFAULT 'OK',
    sizing_mode TEXT DEFAULT 'MANUAL',
    formula_id TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 시스템 요약
CREATE TABLE system_summary (
    run_id TEXT PRIMARY KEY,
    total_flow REAL,
    total_head REAL,
    worst_path TEXT,
    pump_flow REAL, pump_head REAL,
    tank_volume REAL,
    run_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 진단 이력
CREATE TABLE diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT,
    related_id TEXT,
    source_line INTEGER,
    source_col INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 프로젝트 메타데이터
CREATE TABLE project_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT,
    journal_status TEXT DEFAULT 'CLEAN'
);
```

### 4.2 전역 라이브러리 DB (`data/library.db`)

```sql
-- 표준 관경 테이블 (KS/JIS/ANSI)
CREATE TABLE pipe_sizes (
    standard TEXT,         -- 'KS', 'JIS', 'ANSI'
    nominal_size TEXT,     -- '50A', '65A', '2inch'
    inner_diameter REAL,   -- 내경 (m)
    outer_diameter REAL,   -- 외경 (m)
    wall_thickness REAL    -- 두께 (m)
);

-- 관 재질 테이블
CREATE TABLE pipe_materials (
    material_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    roughness REAL,        -- 조도 (mm, DW용)
    c_factor_hw REAL,      -- C계수 (HW용)
    max_pressure REAL,     -- 최대 허용 압력 (Pa)
    wave_velocity REAL     -- 압력파 속도 (m/s)
);

-- 피팅 K-factor 테이블
CREATE TABLE fitting_kfactors (
    fitting_type TEXT,     -- 'ELBOW90', 'TEE_BRANCH', 'GATE_VALVE'
    nominal_size TEXT,
    k_factor REAL,
    description TEXT
);

-- 펌프 커브 라이브러리
CREATE TABLE pump_curves (
    curve_id TEXT PRIMARY KEY,
    manufacturer TEXT,
    model TEXT,
    rated_flow REAL,       -- 정격 유량 (m3/s)
    rated_head REAL,       -- 정격 양정 (m)
    npshr REAL             -- 필요 흡입수두 (m)
);

CREATE TABLE pump_curve_points (
    curve_id TEXT,
    flow REAL,             -- (m3/s)
    head REAL,             -- (m)
    efficiency REAL        -- 효율 (0~1)
);

-- 유체 물성 테이블
CREATE TABLE fluid_properties (
    fluid_type TEXT,
    temperature REAL,      -- (°C)
    density REAL,          -- (kg/m³)
    viscosity REAL,        -- (Pa·s)
    vapor_pressure REAL    -- (Pa)
);
```

---

## 5. GUI 설계

### 5.1 5패널 레이아웃

```
+---------------------------+---------------------------------------+
|  Project Panel (240px)    |         Toolbar                       |
+---------------------------+------------------+--------------------+
|                           |                  |                    |
| [최근 프로젝트 목록]       |   DSL Editor     | Topology Viewer    |
| project_A.fhproj          |   (Center-Left)  | (Center-Right)     |
| sample_test.fhd            |                  |                    |
|                           | - 줄번호 거터     | - QGraphicsView    |
| [새 프로젝트]              | - 구문 하이라이팅 | - 노드/엣지 렌더링  |
| [열기]                    | - 에러 마커      | - 드래그/줌/패닝    |
| [저장]                    |                  |                    |
| [설정]                    |                  |                    |
+---------------------------+------------------+--------------------+
|   Results Dashboard (Bottom-Left)            | Diagnostics (BR)   |
+----------------------------------------------+--------------------+
| [요약] [상세]             | 배관 목록 테이블   | [코드][심각도][위치]|
| Q=150 m³/h               | p1: 2.0m/s 0.1m  | SEM001 ERROR L10   |
| H=45 m (권장)             | p2: 1.8m/s 0.3m  | WRN001 WARN p2     |
+---------------------------+------------------+--------------------+
```

### 5.2 패널별 클래스 설계

```python
class MainWindow(QMainWindow):
    # 레이아웃: QSplitter 기반 5패널
    # 신호: analysis_requested, project_opened, project_saved

class ProjectPanel(QWidget):
    # QListView + 버튼 그룹
    # 신호: project_selected(path), new_project_requested

class EditorPanel(QWidget):
    # QPlainTextEdit + FHDLHighlighter + EditorGutter
    # 신호: text_changed(code), run_requested

class TopologyViewer(QWidget):
    # QGraphicsView + QGraphicsScene
    # 노드: 타입별 색상 (Tank=Blue, Pump=Green, Terminal=Red)
    # 엣지: 상태별 색상/두께 (WRN001=Orange, NET001=Red)
    # 신호: entity_selected(id), entity_moved(id, x, y)

class ResultsPanel(QWidget):
    # QTabWidget (Summary / Details)
    # Summary: 총유량, 총양정, 권장 사양
    # Details: QTableView (배관/노드 결과 테이블)

class DiagnosticsPanel(QWidget):
    # QTreeWidget (심각도별 분류)
    # 더블클릭 → 에디터 해당 라인 이동
    # 신호: diagnostic_selected(code, line)
```

### 5.3 비동기 워커

```python
class AnalysisWorker(QRunnable):
    # QThreadPool 활용
    # 신호: status_update(stage, msg)
    # 신호: finished(AnalysisResult)
    # 신호: error(str)
    
    def run(self):
        pipeline = AnalysisPipeline()
        result = pipeline.run(self.source_code, self.options)
        self.signals.finished.emit(result)
```

---

## 6. 상태 기계 (FSM)

| 상태 | 설명 | 진입 이벤트 | 허용 전이 |
|------|------|------------|---------|
| `Idle` | 초기 상태, 편집 가능 | 앱 시작, 프로젝트 열기 | Dirty |
| `Dirty` | 미저장 변경 있음 | 텍스트 변경 | Idle(Undo), Validating |
| `Validating` | 문법/의미 검사 중 | Run 클릭 | Solved, ValidationFailed |
| `Solving` | 수리 해석 중 | 검증 통과 | Solved, CalcFailed, Aborted |
| `Solved` | 해석 완료 | 계산 성공 | Dirty, Saving |
| `ValidationFailed` | 검증 실패 | 검증 에러 | Dirty |
| `CalcFailed` | 계산 실패 | 계산 에러 | Dirty |
| `Saving` | 저장 중 | Save 요청 | Saved, Dirty(실패) |
| `Saved` | 저장 완료 | 저장 성공 | Dirty, Idle |
| `Aborted` | 계산 취소 | Abort 이벤트 | Dirty |

**금지 전이:**
- `Idle` → `Saving` (저장할 변경 없음)
- `Solving` → `Saving` (계산 중 저장 불가)
- `ValidationFailed` → `Solving` (검증 통과 없이 계산 불가)

---

## 7. 오류 처리 원칙

1. 모든 계산 오류는 `AnalysisResult(status='FAILED')` 반환 (예외 throw 금지)
2. GUI는 `AnalysisResult`의 `diagnostics`를 DiagnosticsPanel에 표시
3. FATAL 오류(메모리, I/O)만 예외로 허용
4. 장애 모드: SQLite 장애 → Memory-only 모드 + WRN006, NetworkX 장애 → Fallback 재귀 알고리즘

---

## 8. 프로젝트 파일 구조

```
projects/
└── my_project/
    ├── main.fhd           # 주 DSL 소스 파일
    ├── config.fhproj      # 프로젝트 설정 JSON
    ├── state.db           # 계산 결과 및 메타데이터 SQLite
    ├── .journal           # 저널 파일 (장애 복구용)
    └── outputs/
        └── run_YYYYMMDD_HHMMSS/
            ├── Nodes_Report.csv
            ├── Pipes_Report.csv
            └── Simulation_Summary.json
```

### `config.fhproj` 구조

```json
{
  "schema_version": "1.0.0",
  "project_name": "my_project",
  "created_at": "2026-05-27T10:00:00",
  "settings": {
    "friction_model": "DW",
    "unit_system": "METRIC",
    "fluid_type": "water",
    "fluid_temp": 20.0
  },
  "last_save": {
    "timestamp": "2026-05-27T10:30:00",
    "checksum": "sha256:...",
    "journal_seq": 42
  }
}
```
