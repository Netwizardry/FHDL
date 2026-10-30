# 도면 생성 (DRAWING)

> 코드 기준: `src/fhdl/drawing/`, `src/fhdl/core/geometry.py`, `src/fhdl/core/pipe_sizes.py`,
> GUI `src/fhdl/gui/panels/drawing_panel.py`. 원본 자료: `archive/dxf/` — ISO 보는 요령 PDF(규약),
> **아이소메트릭 기호표 DXF·도면 양식 DXF(기호·양식 데이터로 이식, 아래 「원본 DXF 이식」)**.

도면은 **DSL(`main.fhd`)에서 자동 생성되는 출력물**이다. 진실원은 계속 DSL이고, 도면에서
편집하면(GUI) DSL 이 고쳐진 뒤 재해석·재생성된다(Inverse Sync).

## 도면 종류

| view | 이름 | 내용 |
|---|---|---|
| `iso` | 아이소메트릭 (ISO 6412-2 스타일) | 단선 배관, 경유점 꺾임, 부속 기호, 구간 치수(mm), 흐름 화살표, 방위 |
| `plan` | 평면도 | 위에서 본 x–y. 수직관은 UP(원+점)/DN(원+X) 표시와 높이차(mm) |
| `elevation` | 정면도 | 남쪽에서 북쪽을 본 x–z. 남북 방향 관은 원 표시 |
| `pid` | 계통도 P&ID (ISO 10628 배치 · ISO 14617 스타일 기호) | 연결 관계 기준 배치(좌→우 흐름), 장비·라인 목록 |

모든 시트는 A3 가로(420×297mm)다. 배관 도면(iso·plan·elevation)은 기본으로 **회사 도면 양식**
(도면 양식 DXF 에서 이식)을 쓴다: BILL OF MATERIAL(CODE·SIZE·Q'TY·CLASS·DESCRIPTION 29행 — 자재
+ 단관 절단 길이), 표제란(LINE NO.·COMMODITY·JOB NO.·SHT.NO.·REV.), 개정란(NO.·DATE·DESCRIPTION·
DRAWN), 조건표 OPERATION PRESS(kg/cm², 노드 최대 게이지압)·TEMP(°C, 유체 온도), AREA·UNIT, NOTES.
나머지 칸(PT·WPS·INSULATION·결재란 등)은 빈 칸으로 남는다. `build_drawing(..., form="simple")` 이면
간이 양식(오른쪽 표 + 아래 표제란). 계통도(P&ID)는 간이 양식.

## 좌표·투영 규약

- 모델 좌표: `x` = 동(E), `y` = 북(N), `z` = 상(Up), 단위 m. `z` 는 datum 상대 고도.
- 아이소메트릭: **북 = 오른쪽 위 30°, 동 = 오른쪽 아래 30°, 상 = 수직** (참고 "ISO 보는 요령"의
  방위 규약). 방위 표시(N)는 도면 영역 오른쪽 위.
- 축척 없음(NTS): 도면 영역에 맞춰 균등 축척한다. 치수 숫자는 실제 길이(mm)다.
- 좌표(x/y)가 없는 노드는 흐름 깊이 기준으로 **자동 배치**되고 NOTES 에 표시된다.

## 배관 경로와 부속 위치 (DSL)

```c
pipe main_pipe {
    start = p1; end = j1;
    via = [(45, 0, 8), (45, 0, 5)];          // 경유점 (x, y, z) m — 꺾이는 곳마다 엘보
    fittings = [valve_check@3m, valve_gate@6m, pressure_gauge@10m, flow_meter@50%];
}
```

- `via` 가 있으면 경로 = [시작 노드, via…, 끝 노드]. `length` 생략 시 경로 길이로 채운다.
  경로 꺾임마다 엘보 K 가 `auto_k` 에 가산된다([SOLVER](SOLVER.md)).
- 부속 위치 `name@2m` / `@1500mm` / `@50%` 는 배관 시작점 기준. 위치가 없으면 배관을 따라
  **균등 배치**(개략 위치, NOTES 표시). 위치는 K 계산에 영향이 없다.
- 진단: `SEM008`(length < 경로 길이), `SEM010`(via 형식 오류/끝점 좌표 없음), `SEM011`(위치가 길이 밖).

## 원본 DXF 이식

| 원본 (`archive/dxf/`) | 추출기 | 데이터 (패키지 포함) |
|---|---|---|
| `Piping_admin_65hoiqch_Isometric-Piping.dxf` (기호 42종·360변형) | `python -m fhdl.drawing.dxf_symbols <dxf>` | `drawing/data/iso_symbols.json` |
| `도면FORM 및 SYMBOL 1 (3).dxf` (A3 배관 ISO 양식) | `python -m fhdl.drawing.dxf_form <dxf>` | `drawing/data/iso_form.json` |

- **기호**: FHDL 부속과 대응하는 15종(게이트·글로브·볼·플러그·니들·버터플라이·다이어프램·체크 밸브,
  신축이음·유니온·오리피스·동심/편심 리듀서·사이트글라스·흐름 화살표). 칸마다 등각 축과 나란한
  평행선(끝 막대) → 평면 축, 두 막대 중점 방향 → 배관 축, 화살촉 → 방향을 판정한다(막대가 없으면
  같은 선 위 배관 토막·화살촉 밑변). 기호표는 비대칭 부분(니들 스템·체크 사선 등)을 변형마다
  월드 기준 같은 쪽에 그리므로 **방향 변형을 그대로 저장**하고(`variants`, 키 `E/U` = 배관 축 E·평면 U,
  방향성 기호는 `+E/U`), 수직 평면 변형 하나를 로컬 형상(`local`)으로도 저장한다. 단위 = 게이트 밸브 반길이.
- **양식**: 레이어 TITLE·TB·TBOX 의 선·글자를 그대로 쓴다. 제외: BOM 샘플 값(DEM MTEXT), 회사 로고
  (SR02 해치), 고정 방위 표시(FHDL 이 도면 방향대로 그림), 표제란 샘플 값(`DS-생-017`·`J.con`·`2011` 등
  → 채움 칸 `fields`).
- 원본 DXF·PDF 는 저장소에 올리지 않는다(로컬 `archive/dxf/` 에만 보관). 이식된 데이터는 `drawing/data/` 에 있다.
- 저장된 JSON 은 원본 DXF 에서 그대로 재생성됨을 테스트로 고정한다(`tests/test_dxf_import.py`, 원본이 없으면 해당 2개는 skip).
  기호표·양식이 바뀌면 위 명령으로 다시 만들면 모든 도면에 반영된다.

## 기호

1차 출처는 위 **기호표 추출 데이터**다. 아이소메트릭에서 배관이 좌표축 방향이면 배관 축·평면 축이 맞는
기호표 변형을 그대로 그리고(방향성 기호가 반대 방향이면 배관 축으로 반사), 사선 배관·평면도·정면도·
계통도에서는 로컬 형상을 쓴다. 데이터에 없는 기호(스트레이너·계기 태그·PRV/솔레노이드 구동부 등)만
아래 내장 정의를 쓴다.

내장 기호는 **배관 방향 기준 로컬 좌표 (a, b)** 로 한 번만 정의한다(`drawing/symbols.py`).
a = 배관 진행 방향, b = 배관이 놓인 평면의 수직 방향. 투영 시 b 는 수평관이면 수직(Up) 평면을
우선한다. 그래서 같은 정의가 참고 기호표의 6가지 방향(진행 축 × 평면)과 평면·정면·P&ID 에
모두 쓰이고, 로컬 원은 아이소메트릭에서 타원이 된다.

| 기호 ID | 모양 | 부속 키(`core/fittings.py` `FITTING_SYMBOLS`) |
|---|---|---|
| 출처 | 기호 ID | 부속 키 |
|---|---|---|
| 기호표 | `valve_gate` `valve_globe` `valve_ball` `valve_plug` `valve_needle` `valve_butterfly` `valve_diaphragm` `valve_check` | valve_gate·valve_drain, valve_globe, valve_ball, valve_plug, valve_needle·sample_valve, valve_butterfly, valve_diaphragm, valve_check·valve_foot |
| 기호표 | `expansion_joint` `union` `orifice` `reducer` `reducer_ecc` `sight_glass` `flow_arrow` | expansion_joint·flexible_joint, union, (기호만), reducer, reducer_ecc, sight_glass, (흐름 방향) |

내장 정의(기호표에 없는 것 + 기호표 데이터가 없을 때의 대체):

| 기호 ID | 모양 | 부속 키 |
|---|---|---|
| `valve_gate` | 나비넥타이 | valve_gate, valve_drain |
| `valve_globe` | 나비넥타이 + 채운 원 | valve_globe |
| `valve_ball` | 나비넥타이 + 빈 원 | valve_ball |
| `valve_needle` | 나비넥타이 + 수직선 | valve_needle, sample_valve |
| `valve_butterfly` | 양끝 막대 + 원 | valve_butterfly |
| `valve_check` | 양끝 막대 + 사선 + 화살촉 | valve_check, valve_foot |
| `valve_relief` | 직각 앵글 밸브 + 스프링 | valve_relief |
| `valve_prv` / `valve_solenoid` | 나비넥타이 + 구동부(사각/S) | valve_prv / valve_solenoid |
| `valve_air` | 삼각 + 원 | valve_air |
| `reducer` | 사다리꼴 | reducer |
| `union` / `coupling` / `flange` | 짧은 평행선 3/2/2 | union / coupling / flange_joint, insul_flange |
| `expansion_joint` | 양끝 막대 + 물결 | expansion_joint, flexible_joint |
| `strainer` | 사각 + 사선 다리 | strainer_y, strainer_basket |
| `inst_pi` / `inst_fe` / `inst_ti` | 원형 태그(PI/FE/TI) | pressure_gauge / flow_meter / thermometer |
| `sight_glass`, `cap` | 사각+원 / 반원 | sight_glass / cap_plug |

엘보·티는 기호 대신 **경로에서 자동 표시**한다: 꺾임점·분기점 양쪽의 **용접점(검은 점)**.
장비: 탱크 = 세로 원통, 펌프 = 원 + 토출 방향 삼각형, 말단 = 노즐 삼각형, 흐름 = 빨간 채운 삼각형.

## 자재표(BOM)와 단관 절단 길이

- BOM: 배관(재질·호칭경별 총길이), `ELBOW 90° LR`/`45° LR`(경유점 꺾임 수), `TEE`(3개 이상
  배관이 만나는 junction), 밸브·부속(fittings 개수). 호칭경은 `core/pipe_sizes.py`(KS, A·inch).
- 절단 길이(경유점이 있는 배관): **구간 C-C − 롱 엘보 테이크오프**,
  테이크오프 = 1.5 × 호칭경(inch) × 25.4 × tan(θ/2) (90° → 1.5D, KS/JIS).
  예: 100A 500 → UP 400 → 800 이면 A=347.6, B=95.2, C=647.6 (참고 자료 예제, 테스트로 고정).
  노드에서의 꺾임(티·장비 접속부) 테이크오프는 차감하지 않는다.

## 내보내기

| 형식 | 내용 | 구현 |
|---|---|---|
| PDF | 시트당 1페이지(기본 4장), A3 벡터 | `render_qt.save_pdf` (PySide6 QPdfWriter) |
| DXF | 여러 장은 한 파일에 가로로 나란히. 레이어 PIPE·VALVE·FITTING·EQPT·INSTR·FLOW·DIM·TEXT·NORTH·BORDER, 단위 mm | `export_dxf` (ezdxf) |
| SVG | 시트당 1파일, 레이어 = `<g id>`, 요소에 `data-ref` | `export_svg` |
| PNG | 시트당 1파일 | `render_qt.save_png` |
| STEP (선택) | 실제 관경 3D 배관 솔리드 | `export_step` — 외부 SolidCraft CLI |

```python
from fhdl.drawing import build_drawing, export_drawing
export_drawing(result, "plant.pdf", project="demo")            # ISO·평면·정면·P&ID 4장
export_drawing(result, "plant.dxf", views=["iso", "pid"])
sheet = build_drawing(result, "plan")                          # Sheet (요소 목록)
```

### STEP (선택 기능, SolidCraft)

`solidcraft-cli` 를 인자 → 환경변수 `SOLIDCRAFT_CLI` → `PATH` 순으로 찾는다. 없으면 명령
스크립트(`*.solidcraft.json`)만 저장한다. SolidCraft 커널 한계(실험 확인)를 우회한다:
h/r ≳ 600 원통은 끝 캡을 잃으므로 h/r ≤ 200 구간으로 나누고, 기울어진 축 원통이 값에 따라
단면 생성에 실패하면 실패 단계를 0.01mm 옮겨 재시도한다. via 로 만든 직교 배관은 안정적이다.

## GUI · 명령

- 중앙 우측 **「도면」 탭**: 도면 종류 선택, 맞춤, 내보내기…(`Ctrl+Shift+E`, 파일 메뉴).
- 클릭 = 선택 강조(주황), 더블클릭 = 노드/배관 속성 편집(토폴로지와 같은 대화상자).
- **평면도·정면도에서 노드 드래그** → DSL 의 `x, y`(평면) 또는 `x, z`(정면, `elevation` 별칭
  블록이면 그 줄)를 고치고 재해석. 아이소메트릭은 깊이를 정할 수 없어 드래그하지 않는다.
  드래그는 노드만 옮기며 via 경유점은 그대로다.
- 콘솔: `dwg <iso|plan|elevation|pid>` 보기 전환, `dwg export <파일> [views=iso,plan]`
  (상대 경로는 프로젝트 폴더 기준). [COMMANDS](COMMANDS.md).

## 한계

- 도면은 NTS 개략도이며 배관 지지·단열·용접 번호·스풀 분할은 표현하지 않는다.
- 같은 투영 위치에 겹치는 배관(정면도의 나란한 관 등)은 선이 겹친다(주석만 밀어낸다).
- 기호표에 없는 기호(스트레이너·계기 태그·구동부)는 내장 정의다. 기호표·양식 DXF 를 고치고
  추출기를 다시 돌리면 모든 도면에 반영된다. 회사 로고는 이식하지 않는다(양식 데이터에서 제외).
