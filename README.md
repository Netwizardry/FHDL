# FHDL — Fluid Hardware Description Language

유체 설비 설계 의도를 DSL(Domain-Specific Language)로 입력받아 **정상상태 수리(水理) 계산을 자동화**하는 Python/PySide6 기반 데스크톱 시스템입니다.

> 현재 버전: **v0.2 (MVP)** — 정상상태 해석, Auto-sizing, 펌프/탱크 사양 선정, 5패널 GUI

---

## 주요 기능

- **정상상태 수리해석** (2-Pass: 유량 합성 → Newton-Raphson 수압 평형)
- **Auto-sizing** — 유속 제약을 만족하는 표준 관경(KS) 자동 선정
- **마찰 모델** — Darcy-Weisbach(Swamee-Jain) / Hazen-Williams, 재질별 물성 자동 적용
- **부속(밸브·엘보·티·레듀서) 국부손실** + 꺾임각 자동 엘보 K
- **펌프 양정 주입**(실제 에너지원) 및 탱크/펌프 사양 선정(안전율)
- **해발 datum**: 노드 z는 기준 해발 상대값, 해발·온도로 대기압·물성 산정
- **NPSHa·캐비테이션·수충격·진공 한계** 진단, 네트워크 무결성(NET) 검사
- **5패널 GUI** + **아이소메트릭 2.5D 토폴로지** + 그래프 직접 편집(Inverse Sync)
- **하단 명령 콘솔(TUI)** — 명령어로 모델 편집·해석 (GUI와 동작 공유)
- **프로젝트 저장/로드/복원**(체크섬 캐시) + **부품 라이브러리 CRUD**
- 단위계 METRIC/IMPERIAL 표시, CSV/JSON 리포트(provenance)

> 수충격 정밀 해석, 복합 루프망(Hardy-Cross), 펌프 커브 운전점, CAD/BIM 연동은 로드맵.

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
python main.py
```

최초 실행 시 `data/library.db`(부품 라이브러리)가 자동 생성됩니다.

---

## DSL 예시

`projects/demo_project/main.fhd` 발췌:

```c
system main {
    unit_system = METRIC;
    fluid = water;
    temp = 20;
    friction_model = DW;     // DW | HW
}

constraint {
    velocity_max = 2.5m;
    safety_factor_head = 1.1;
}

tank reservoir { z = 10m; volume = 50m3; level_max = 1.5m; }
junction j1     { z = 5m; }
terminal sprinkler_A { z = 3m; required_q = 80lpm; required_p = 0.1MPa; }
terminal nozzle_B    { z = 2m; required_q = 60lpm; required_p = 0.08MPa; }

pipe main_pipe { start = reservoir; end = j1;          length = 60m; diameter = auto; material = Steel; }
pipe branch_A  { start = j1;        end = sprinkler_A; length = 35m; diameter = auto; material = PVC;
                 fittings = [elbow_90, valve_gate]; }
pipe branch_B  { start = j1;        end = nozzle_B;    length = 40m; diameter = auto; material = Steel; }

connect reservoir -> j1 -> sprinkler_A;
connect j1 -> nozzle_B;
```

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
│   │                       #   + language·fittings·materials·units (단일 진실원)
│   │                       #   + dsl_editor·command·project_io
│   ├── db/                 # library_db (전역 부품 CRUD), project_db (프로젝트별)
│   └── gui/                # main_window + panels/ (5패널) + log_console + library_dialog
├── resources/styles/       # dark_theme.qss
├── data/library.db         # 전역 부품 라이브러리 (자동 생성)
├── projects/               # 프로젝트별 작업공간 (main.fhd, state.db, project.fhproj)
├── tests/                  # pytest (102개)
├── docs/                   # 코드 기준 문서 (INDEX·LANGUAGE·SOLVER·…)
└── archive/                # 구 명세·감사·v0.1 보관
```

---

## 테스트

```bash
pytest -q     # 102개 (파서·솔버·네트워크·재질·부속·DB·프로젝트IO·명령콘솔 등)
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
