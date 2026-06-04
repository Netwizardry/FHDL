# FHDL — Fluid Hardware Description Language

유체 설비 설계 의도를 DSL(Domain-Specific Language)로 입력받아 **정상상태 수리(水理) 계산을 자동화**하는 Python/PySide6 기반 데스크톱 시스템입니다.

> 현재 버전: **v0.2 (MVP)** — 정상상태 해석, Auto-sizing, 펌프/탱크 사양 선정, 5패널 GUI

---

## 주요 기능 (v0.2 MVP)

- **정상상태 수리해석** (2-Pass: 유량 역산 → Newton-Raphson 수압 평형)
- **Auto-sizing** — 유속 제약을 만족하는 표준 관경(KS) 자동 선정
- **마찰 모델** — Darcy-Weisbach(Swamee-Jain) / Hazen-Williams
- **펌프·탱크 기본 사양 선정** (안전율 적용)
- **NPSHa 계산 및 캐비테이션 경고**, 수충격 위험 지수·진공 한계 진단
- **DSL 에디터** (구문 하이라이팅, 실시간 린팅) + **토폴로지 뷰어**
- **프로젝트별 SQLite 저장** + 전역 부품 라이브러리 DB
- CSV/JSON 리포트 생성 (provenance 포함)

> 수충격 정밀 해석, 복합 루프망(Hardy-Cross), CAD/BIM 연동은 v0.2+ 로드맵.

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

tank reservoir { elevation = 10m; volume = 50m3; level_max = 1.5m; }
junction j1     { elevation = 5m; }
terminal sprinkler_A { elevation = 3m; required_q = 80lpm; required_p = 0.1MPa; }
terminal nozzle_B    { elevation = 2m; required_q = 60lpm; required_p = 0.08MPa; }

pipe main_pipe { start = reservoir; end = j1;          length = 60m; diameter = auto; material = Steel; }
pipe branch_A  { start = j1;        end = sprinkler_A; length = 35m; diameter = auto; material = Steel; }
pipe branch_B  { start = j1;        end = nozzle_B;    length = 40m; diameter = auto; material = Steel; }

connect reservoir -> j1;
connect j1 -> sprinkler_A;
connect j1 -> nozzle_B;
```

**지원 블록 키워드:** `system`, `constraint`, `tank`, `pump`, `junction`, `terminal`, `pipe`, `connect`

`diameter = auto` 로 두면 솔버가 유속 제약을 만족하는 표준 관경을 자동 선정합니다.

---

## GUI 5패널 구조

| 패널 | 역할 |
| :--- | :--- |
| Project | 프로젝트 생성/열기/저장, 최근 목록 |
| DSL Editor | FHDL 코드 편집 (하이라이팅, 실시간 린팅, Ctrl+Enter 실행) |
| Topology Viewer | 배관망 그래프 시각화 (타입별 도형/상태별 색상) |
| Results Viewer | 노드/배관 결과 테이블, 요약 카드, CSV 내보내기 |
| Diagnostics | 오류/경고 트리, 더블클릭 시 에디터 해당 줄 이동 |

테마: `resources/styles/dark_theme.qss` (전역 다크 테마, 단일 진실원)

---

## 프로젝트 구조

```
FHDL/
├── main.py                 # 애플리케이션 진입점
├── pyproject.toml          # 의존성 단일 진실원
├── requirements*.txt       # pip 편의 미러본
├── src/fhdl/
│   ├── core/               # 엔진: parser, semantic, solver, pipeline, report
│   ├── db/                 # library_db (전역 부품), project_db (프로젝트별)
│   └── gui/                # main_window + panels/ (5패널) + worker
├── resources/styles/       # dark_theme.qss
├── data/library.db         # 전역 부품 라이브러리 (자동 생성)
├── projects/               # 프로젝트별 작업 공간 (state.db, *.fhd)
├── tests/                  # pytest 단위 테스트
└── docs/spec/              # 공식 명세서 (진실원)
```

---

## 테스트

```bash
pytest -q
```

핵심 수리 로직(유량 분배·마찰손실·Auto-sizing·NPSHa)에 대한 단위/회귀 테스트를 포함합니다.

---

## 내부 단위 규약

내부 계산은 **SI 기본단위**(유량 m³/s, 압력 Pa, 수두·길이·관경 m)로 수행하며,
표시 단위(L/min, MPa, mm 등)는 GUI 계층에서 변환합니다. 상세는 `CLAUDE.md` 참조.

---

## 라이선스 / 문서

- 공식 명세: `docs/spec/`
- 설계 문서: `design/PROGRAM_DESIGN.md`, `design/TODO_IMPLEMENTATION.md`
