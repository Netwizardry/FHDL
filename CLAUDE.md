# FHDL 프로젝트 CLAUDE.md

**프로젝트:** FHDL (Fluid Hardware Description Language)  
**목적:** 유체 설비 설계 의도를 DSL로 입력받아 수리 계산을 자동화하는 Python 기반 GUI 시스템  
**언어:** Python (PySide6 GUI, SQLite DB)  
**현재 버전:** v0.2 (구현 완료, 문서는 코드 기준으로 유지)

---

## 프로젝트 구조

```
FHDL/
├── CLAUDE.md              # 이 파일
├── README.md             # 설치·빠른 시작
├── docs/                 # 코드 기준 문서 (INDEX·LANGUAGE·SOLVER·DATA_MODEL·GUI·DRAWING·COMMANDS·DIAGNOSTICS)
├── src/fhdl/
│   ├── core/             # 엔진 + 단일 진실원(language·fittings·materials·pipe_sizes·units) + geometry·dsl_editor·command·project_io
│   ├── db/               # project_db (프로젝트별), library_db (전역 부품 CRUD)
│   ├── drawing/          # 도면 생성 (ISO·평면·정면·P&ID → SVG·PDF·DXF·STEP)
│   ├── domains.py        # 설계 분야 레지스트리 (FHDL 유체 · EHDL 전기 — 시작 화면)
├── src/ehdl/             # EHDL 전기 설계·검산 엔진 (SPEC: docs/ehdl/) + rules/(원문 대조 규칙) + kb/(기준 원문 DB)
│   └── gui/              # start_dialog(분야 선택) + main_window + panels/ (5패널) + log_console + library_dialog
├── tests/                # pytest (280개)
├── resources/styles/     # dark_theme.qss
├── data/library.db       # 전역 부품 라이브러리
├── projects/             # 프로젝트별 작업공간
└── archive/              # 구 명세·감사·설계·v0.1 보관
```

---

## 핵심 기술 규범 (진실원 우선순위)

> 구 명세(`archive/spec_legacy/`)가 아니라 **코드와 코드 기준 문서**가 진실원이다.

1. 소스코드 `src/fhdl/` — 동작의 최종 진실원
2. `docs/LANGUAGE.md` / `docs/SOLVER.md` — 언어·계산 규범
3. `docs/ARCHITECTURE.md` / `docs/DATA_MODEL.md` — 구조·영속성 규범
4. `docs/DIAGNOSTICS.md` / `docs/GUI.md` / `docs/COMMANDS.md`
5. 단일 진실원 모듈: `core/language.py`(키워드), `core/fittings.py`(부속 K·도면 기호), `core/materials.py`(재질), `core/pipe_sizes.py`(관경)

---

## v0.1 MVP 포함 범위 (확정)

| 항목 | 포함 여부 |
| :--- | :--- |
| 정상상태 수리해석 (Steady-state) | ✅ 필수 |
| 트리형/단순 병렬 배관망 | ✅ 필수 |
| Auto-sizing (권장 관경 자동 산정) | ✅ 필수 |
| 기본 NPSHa 계산 및 캐비테이션 경고 | ✅ 필수 |
| Hazen-Williams / Darcy-Weisbach 마찰 모델 | ✅ 필수 |
| 펌프/탱크 기본 사양 선정 | ✅ 필수 |
| PySide6 GUI (5패널 구조) | ✅ 필수 |
| 프로젝트별 SQLite 저장 | ✅ 필수 |
| 부품 라이브러리 DB | ✅ 필수 |
| 수충격(Water Hammer) 정밀 해석 | ❌ v0.2 이후 |
| 복합 루프망 (Hardy-Cross) | ❌ v0.2 이후 |
| CAD/BIM 연동 | ❌ v0.3 이후 |

---

## 데이터베이스 구조

### 1. 프로젝트 DB (projects/{project_name}/state.db)
- 프로젝트별 독립 SQLite
- 노드, 배관, 펌프 커브, 계산 결과, 진단 기록 저장

### 2. 전역 부품 라이브러리 DB (data/library.db)
- 관경 표준 테이블 (KS/JIS/ANSI)
- 관 재질별 마찰계수 (C값, 조도)
- 표준 부속류 K-factor 테이블
- 펌프 커브 라이브러리
- 유체 물성 테이블

---

## GUI 5패널 구조

1. **Project Panel** - 프로젝트 생성/열기/저장
2. **Topology Viewer** - 배관망 그래프 시각화 (드래그 편집)
3. **DSL Editor** - FHDL 코드 편집기 (구문 하이라이팅)
4. **Results Viewer** - 계산 결과 테이블/차트
5. **Diagnostics Panel** - 오류/경고 목록 및 상세 설명

---

## 내부 단위 규약 (Internal Units - 진실원)

| 물리량 | 내부 단위 | 표시 단위 |
| :--- | :--- | :--- |
| 유량 (Flow) | m³/s | L/min (METRIC), GPM (IMPERIAL) |
| 압력 (Pressure) | Pa | MPa (METRIC), psi (IMPERIAL) |
| 수두 (Head) | m | m (METRIC), ft (IMPERIAL) |
| 관경 (Diameter) | m | mm (METRIC), inch (IMPERIAL) |
| 길이 (Length) | m | m (METRIC), ft (IMPERIAL) |
| 속도 (Velocity) | m/s | m/s |

---

## 작업 진행 상태

- [x] 명세 검토·감사 (→ `archive/`)
- [x] 핵심 엔진 구현 (parser·semantic·solver·pipeline)
- [x] 네트워크 진단(NET001~006), 재질·부속 물성 연동
- [x] DB 레이어 + 프로젝트 저장/로드/복원 + 라이브러리 CRUD
- [x] GUI 5패널 + 아이소메트릭 2.5D + 그래프 직접 편집(Inverse Sync)
- [x] 하단 명령 콘솔(TUI) + 단축키
- [x] 단일 진실원화(language·fittings·materials) + 코드 기준 문서 재작성
- [x] 성능 최적화(1000노드<1s)·저널 복구·정확도 벤치마크·패키징·아이콘
- [x] 기하 검증(SEM008~011)·배관 경유점 via·부속 위치(@)·숨은 엘보 K
- [x] 배관 도면 생성(ISO 6412-2 아이소메트릭·평면·정면·P&ID) + ISO 기호·BOM·절단표 + PDF·DXF·SVG·STEP(SolidCraft, 선택) — `docs/DRAWING.md`
- [x] 사용자 기호표·도면 양식 DXF(`archive/dxf/`) → 도면 기호·양식 데이터 이식(`drawing/data/`, 재현성 테스트)
- [x] 시작 화면 — 설계 분야 선택(FHDL / EHDL), 선택 기억, 실행 중 분야 전환
- [~] **EHDL 전기 설비 설계** — SPEC v0.1·검토(`docs/ehdl/`), 결정 D1~D4 확정
  - [x] 엔진 Phase 1 핵심: DSL·의미분석·부하/시나리오/상별 집계·전압강하(부속서 G)·판정·설명/질문·병목
  - [x] 기준 원문 9종 지식 DB(`python -m ehdl.kb.build archive/EHDL-Docs`, 로컬 전용) + 규칙 원문 대조
  - [x] GUI(시작 화면 활성화·DSL 에디터·단선결선도 그래프 에디터·노드 상세 7항목·결과·명령 콘솔)·보고서 B~F·계통 구성도
  - [x] Phase 2: 단락전류(IEC 60909)·차단용량·열적 내량·보호협조·전동기 기동·누전·SPD·보정계수 표(B.52.14~18)
  - [x] Phase 3: 접지계통(TN/TT/IT)·고장보호(자동차단)·PE·등전위본딩·수전 종합·설계 변경 영향
  - [x] SPEC 보완: 전선 규격 후보·최소 단락 순시 동작·혼합 모드·기동 방식·차단기 설정·변경 이력
- [x] FHDL 구 명세 점검 보완: 입력 검증·중단/수렴·미저장 확인·되돌리기·실시간 검사·기본값 기록·라이브러리 DB 연결(KS/JIS/ANSI)·계산 보고서 PDF
  - [ ] 이후: 아이소메트릭 CAD (기본형 완성 후 — 사용자 결정)
- [ ] **(차후 대형) 복합 루프망 Hardy-Cross** — `docs/ROADMAP.md` §1
- [ ] **(차후 대형) 수충격 MOC 정밀 해석** — `docs/ROADMAP.md` §2
- [ ] (로드맵) CAD/BIM 양방향 연동(도면→DSL 가져오기), 다국어(i18n)

---

## 개발 환경

- Python 3.10+
- PySide6 (GUI)
- NetworkX (그래프 해석)
- SQLite (데이터 저장)
- NumPy (수치 계산)
- pytest (테스트)

---

## 중요 원칙

1. **아카이브 관리:** 완료된 작업/이전 버전은 `archive/`로 이동
2. **단일 진실원:** 단위, 오류 코드 등은 이 파일 또는 명세서에서 한 곳에서만 정의
3. **UI/UX 우선:** 사용자 흐름과 시각적 완성도를 항상 고려
4. **테스트 커버리지:** 핵심 수리 계산 로직은 단위 테스트 필수
5. **부품 DB 호출 가능:** 라이브러리 DB는 외부에서 호출하여 재사용 가능한 형태로 유지
