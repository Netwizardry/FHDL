# FHDL — Fluid Hardware Description Language

유체 설비 설계 의도를 DSL(Domain-Specific Language)로 입력받아 **정상상태 수리(水理) 계산을 자동화**하는 Python/PySide6 기반 데스크톱 시스템입니다.

> 현재 버전: **v0.2 (MVP)** — 정상상태 해석, Auto-sizing, 펌프/탱크 사양 선정, 5패널 GUI

---

## 주요 기능

- **정상상태 수리해석** (2-Pass: 유량 합성 → Newton-Raphson 수압 평형)
- **Auto-sizing** — 유속 제약을 만족하는 표준 관경(KS) 자동 선정
- **마찰 모델** — Darcy-Weisbach(Swamee-Jain) / Hazen-Williams, 재질별 물성 자동 적용
- **부속(밸브·엘보·티·레듀서) 국부손실** + 꺾임각 자동 엘보 K (배관 경유점 `via` 포함)
- **배관 도면 자동 생성** — ISO 아이소메트릭(ISO 6412-2 스타일)·평면도·정면도·계통도(P&ID), 기호표 DXF 에서 이식한 ISO 기호·회사 도면 양식(표제란·BOM), 치수·단관 절단 길이, **PDF·DXF·SVG·PNG** 내보내기 (선택: SolidCraft 로 STEP 3D)
- **펌프 양정 주입**(실제 에너지원) 및 탱크/펌프 사양 선정(안전율)
- **해발 datum**: 노드 z는 기준 해발 상대값, 해발·온도로 대기압·물성 산정
- **NPSHa·캐비테이션·수충격·진공 한계** 진단, 네트워크 무결성(NET) 검사
- **5패널 GUI** + **아이소메트릭 2.5D 토폴로지** + 그래프 직접 편집(Inverse Sync)
- **하단 명령 콘솔(TUI)** — 명령어로 모델 편집·해석 (GUI와 동작 공유)
- **프로젝트 저장/로드/복원**(체크섬 캐시) + **부품 라이브러리 CRUD**
- 단위계 METRIC/IMPERIAL 표시, CSV/JSON 리포트(provenance)

> 수충격 정밀 해석, 복합 루프망(Hardy-Cross), CAD/BIM 양방향 연동(도면 가져오기)은 로드맵.

### EHDL — 전력계통 설계·검산 (`--domain ehdl`)

- 노드(전원·변압기·배전반·분전반·차단기·부하)와 배선으로 계통을 DSL(`main.ehd`)·그래프로 구성
- 부하 P·Q·S 상향 집계, 상별 전류·불평형, 동시운전 그룹·시나리오(최대 부하 제약 탐색), 경로 전압강하(KS C IEC 60364-5-52 부속서 G)
- 요구조건(Required) vs 실제 규격(Installed) 판정 PASS/FAIL/REVIEW/UNKNOWN, 병목 경로, **"왜 이 규격인가"** 설명·확인 질문
- 판정 근거에 **KEC 원문 조항·쪽**(지식 DB — `python -m ehdl.kb.build`), 계통 구성도(단선결선도)·검산 보고서(B~F)
- Phase 2: 단락전류(KS C IEC 60909-0)·차단용량·도체 열적 내량·보호협조·전동기 기동·누전차단기·SPD·허용전류 보정계수
- Phase 3: 계통접지(TN-S/TN-C/TN-C-S/TT/IT)·고장보호(전원 자동차단, 고장루프 임피던스)·PE·등전위본딩·수전 종합(설비용량·최대수요·계약전력·변압기)·설계 변경 영향
- 기본설계: 전선 규격 후보(허용전류·보호협조·전압강하·열적 내량 동시 만족), 최소 단락전류 순시 동작·차단 범위, 혼합 모드(기존/신규), 기동 방식, 차단기 설정(Ir·Isd·tsd·Ics), 변경 이력
- 문서: [docs/ehdl/](docs/ehdl/GUI.md)

전체 문서: [docs/INDEX.md](docs/INDEX.md)

---

## 설치

```bash
# 1) 가상환경 (권장)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2) 런타임 의존성
pip install -r requirements.txt

# 개발/테스트까지
pip install -r requirements-dev.txt
```

요구 사항: **Python 3.10+**, PySide6 6.6+, NetworkX 3.2+, NumPy 1.26+

---

## 실행

```bash
python main.py                  # 시작 화면에서 설계 분야 선택 (FHDL 유체 / EHDL 전기)
python main.py --domain fhdl    # 시작 화면 없이 바로 FHDL
python main.py --select         # "다음부터 바로 시작"으로 기억된 선택을 무시하고 시작 화면 표시
```

최초 실행 시 `data/library.db`(부품 라이브러리)가 자동 생성됩니다. 실행 중에는 파일 → 설계 분야 전환으로 시작 화면에 돌아갑니다.

---

## DSL 예시

`projects/demo_project/main.fhd` 와 같은 모델을 한 줄 형식으로 줄인 것 (`z` 는 `elevation` 과 같은 키):

```c
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    altitude = 0m;
    friction_model = DW;     // DW | HW
}

constraint {
    velocity_min = 0.3m;
    velocity_max = 2.5m;
    safety_factor_head = 1.1;
}

tank reservoir       { z = 10m; volume = 50m3; level_max = 1.5m; x = 0;   y = 0; }
pump p1              { z = 8m;  x = 5;   y = 0; }      // 양정 auto → 사양 선정 대상
junction j1          { z = 5m;  x = 50;  y = 0; }
terminal sprinkler_A { z = 3m;  required_q = 80lpm; required_p = 0.1MPa;  x = 100; y = 30; }
terminal nozzle_B    { z = 2m;  required_q = 60lpm; required_p = 0.08MPa; x = 100; y = -30; }

// via = 경유점 (x, y, z) m → 꺾임마다 엘보 K, length 생략 시 경로 길이 / 부속 위치 name@거리
pipe suction   { start = reservoir; end = p1; via = [(0, 0, 8)];
                 diameter = auto; material = Steel; fittings = [valve_gate@1m, strainer_y@4m]; }
pipe main_pipe { start = p1; end = j1; via = [(45, 0, 8), (45, 0, 5)];
                 diameter = auto; material = Steel;
                 fittings = [valve_check@3m, valve_gate@6m, pressure_gauge@10m]; }
pipe branch_A  { start = j1; end = sprinkler_A; via = [(50, 30, 5), (100, 30, 5)];
                 diameter = auto; material = Steel; fittings = [valve_ball@2m, flow_meter@50%]; }
pipe branch_B  { start = j1; end = nozzle_B; via = [(50, -30, 5), (100, -30, 5)];
                 diameter = auto; material = Steel; fittings = [valve_globe@2m]; }

connect reservoir -> p1 -> j1;
connect j1 -> sprinkler_A;
connect j1 -> nozzle_B;
```

이 모델의 도면(아이소메트릭·평면·정면·P&ID)은 GUI 「도면」 탭 또는 `dwg export demo.pdf` 로 얻는다 — [docs/DRAWING.md](docs/DRAWING.md).

**지원 블록 키워드:** `system`, `constraint`, `tank`, `pump`, `junction`, `terminal`, `pipe`, `connect`
`z` 는 `system.altitude`(기준 해발) 상대 고도이며, `diameter = auto` 로 두면 표준 관경이 자동 선정됩니다.
전체 문법은 [docs/LANGUAGE.md](docs/LANGUAGE.md).

---

## GUI 구조 (5패널 + 하단 명령 콘솔)

| 영역 | 역할 |
| :--- | :--- |
| Project | 프로젝트 생성(해발·온도)/열기/저장/삭제, 최근 목록 |
| DSL Editor | FHDL 코드 편집 (하이라이팅, 실시간 린팅, 노드 추가/문법 도움말) |
| Topology Viewer | **아이소메트릭 2.5D** 시각화, 더블클릭 편집·드래그 연결 |
| Results Viewer | 노드/배관 결과(단위계 환산), 요약 카드, CSV 내보내기 |
| Diagnostics | 오류/경고 트리, 더블클릭 시 에디터 해당 줄 이동 |
| **명령 콘솔(하단)** | 로그 출력 + 명령어 입력(TUI) — [docs/COMMANDS.md](docs/COMMANDS.md) |

상세·단축키: [docs/GUI.md](docs/GUI.md). 테마: `resources/styles/dark_theme.qss`.

---

## 프로젝트 구조

```
FHDL/
├── main.py                 # 애플리케이션 진입점
├── pyproject.toml          # 의존성 단일 진실원
├── requirements*.txt       # pip 편의 미러본
├── src/fhdl/
│   ├── core/               # 엔진: parser·semantic·solver·pipeline·report
│   │                       #   + language·fittings·materials·pipe_sizes·units (단일 진실원)
│   │                       #   + geometry (경로·엘보 테이크오프)
│   │                       #   + dsl_editor·command·project_io
│   ├── db/                 # library_db (전역 부품 CRUD), project_db (프로젝트별)
│   ├── drawing/            # 도면 생성: ISO·평면·정면·P&ID → SVG·PDF·DXF(·STEP)
│   └── gui/                # main_window + panels/ (5패널) + log_console + library_dialog
├── resources/styles/       # dark_theme.qss
├── data/library.db         # 전역 부품 라이브러리 (자동 생성)
├── projects/               # 프로젝트별 작업공간 (main.fhd, state.db, project.fhproj)
├── tests/                  # pytest (280개)
├── docs/                   # 코드 기준 문서 (INDEX·LANGUAGE·SOLVER·…)
└── archive/                # 구 명세·감사·v0.1 보관
```

---

## 테스트

```bash
pytest -q     # 280개 (파서·솔버·네트워크·재질·부속·경로·도면·DXF 이식·DB·프로젝트IO·명령콘솔 등)
```

---

## 내부 단위 규약

내부 계산은 **SI 기본단위**(유량 m³/s, 압력 Pa, 수두·길이·관경 m)로 수행하며,
표시 단위(L/min↔GPM, MPa↔psi, m↔ft, mm↔in)는 GUI 계층(`core/units.py`)에서 변환합니다.

---

## 문서

- 문서 색인: [docs/INDEX.md](docs/INDEX.md)
  — ARCHITECTURE · LANGUAGE · SOLVER · DATA_MODEL · GUI · COMMANDS · DIAGNOSTICS
- 구 명세·설계·감사 문서(구현 이전): `archive/`
