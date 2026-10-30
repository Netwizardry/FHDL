# EHDL 언어 레퍼런스

> 단일 진실원: `src/ehdl/language.py` (블록·속성·단위 종류·쉬운 설명). GUI 의 문법 참조·추가 대화상자도 여기서 생성된다.
> 예제: `projects/ehdl_demo/main.ehd`

## 형식

```c
<종류> <ID> { 속성 = 값; ... }
```

- 값: 수치+단위 `37kW` `22.9kV` `95mm2` `0.08mohm/m` `30C`, 비율 `0.85` 또는 `85%`, 문자열 `"…"`, 목록 `[A, B]`, 이름 `Cu`.
- 주석: `//` 행, `/* */` 블록. 단위 없이 숫자만 쓰면 속성별 기본 단위(전력 kW, 길이 m, 단면적 ㎟ …).
- **모르는 값은 쓰지 않는다** — 0 이 아니라 '미입력'이 되고 그 값이 필요한 판정은 UNKNOWN 으로 보류된다(SPEC 9.2).

## 연결과 포함

| 표기 | 의미 |
|---|---|
| `cable C { from = A; to = B; ... }` | A → B 배선 (길이·굵기 등 도체 속성을 가진 엣지) |
| `feed = A;` | 배선 없이 A 에 직결 |
| `parent = PNL;` | 반(배전반·분전반) 안의 설비 — 그 반의 모선에 직결, 그래프에서 접기/펼치기 단위 |

노드의 전원 측 = 들어오는 배선의 `from` → `feed` → `parent` 순. Phase 1 은 **단일 전원 방사형**만(배선이 둘 들어오면 ENET003).

## 블록

### 설비 (노드)

| 종류 | 이름 | 입력(조건) | 실제 규격(검산 대상) |
|---|---|---|---|
| `source` | 전원 | `voltage`(선간) `phases` `frequency` · 단락: `sc_mva` `sc_mva_min` `rx` `tolerance`(6%/10%) | `limit_kw` `limit_kva` (사용 가능한 전력 한도) |
| `transformer` | 변압기 | `primary` `secondary` | `rated` (kVA) `uk` `ur` (%임피던스·%저항) |
| `switchboard` | 배전반 | | `rated_current` |
| `panel` | 분전반 | | `rated_current` |
| `bus` | 모선 | | `rated_current` |
| `breaker` | 차단기 | | `rated_current`(In) `breaking_capacity` `poles` `standard`(IEC60898 주택용 / IEC60947-2 산업용) `curve`(B/C/D) `instantaneous`(× In) `trip_time`(단락 시 동작시간) `start_trip_multiple`(δ) `let_through_i2t` `sensitivity`(RCBO) |
| `rcd` | 누전보호장치 | | `rated_current` `sensitivity`(IΔn) |
| `spd` | 서지보호장치 | | `uc` `up` |
| `earth` | 접지(주접지단자·접지극·계통외도전부) | `kind`(main_terminal / electrode / extraneous) | `resistance` (Ω) |
| `load` | 부하 | 아래 | |

공통: `name`(표시 이름), `parent`, `feed`, `justification`(요구보다 큰 규격을 고른 이유 — 있으면 '근거 확인'이 PASS),
`stage`(`existing` 기존 — 기본 / `new` 신규 추가 → 혼합 모드, 배선에도 쓸 수 있음).

차단기 설정(SPEC 3.4): `ir_setting`(장시간 Ir = 설정 × In — 과부하·보호협조에 사용) · `short_time`(Isd × Ir) ·
`short_time_delay`(tsd — 단시간 영역 동작시간, trip_time 이 없으면 열적 내량에도 사용) · `ics`(정격사용단락차단용량, Icu 와 별도) ·
`rated_voltage`(Ue) · `rcd_type`(누전 `fast` 고속형 / `delayed` 시연형 / `inverse` 반한시형 — 누전차단기에도).

### 부하 `load`

| 속성 | 뜻 |
|---|---|
| `kind` | `motor` `lighting` `receptacle` `heater` `general` — 전압강하 허용치(조명/기타) 구분 |
| `rating` | 정격 `kW` 또는 `kVA` |
| `basis` | `output`(기계적 출력) / `input`(전기 입력). **kW 면 필수**(조명·콘센트·히터는 정의상 input). output 이면 `efficiency` 필수 |
| `pf` | 역률 — kW 정격이면 필수. kVA 정격이면 없어도 보수적 산술합으로 판정(추정·질문) |
| `phases` | `1` / `3` (필수) |
| `phase` | 단상 부하의 접속 상 `L1` `L2` `L3`(상-중성) · `L1L2` `L2L3` `L3L1`(선간). 없으면 상별 전류는 평형 가정 추정, 불평형 판정 UNKNOWN |
| `state` | 정상 운전 상태 `on`/`off` (미지정 = on) |
| `group` | 동시운전 그룹 ID |
| `start_multiplier` `start_time` `start_pf` | 전동기 기동: 기동전류 배수 β · 기동시간 tm · 기동 시 역률 |
| `start_method` `start_tap` `start_limit` | 기동 방식 `dol`(전전압, 미입력 시 보수적 기본) · `star_delta`(C 0.33) · `reactor`(C = `start_tap`) · `soft_starter`·`inverter`(기동전류 = `start_limit` × 정격 — 원문 참고 범위 3.5∼5 · 1∼2.0, 값은 입력) — 검사·점검 기준 240.3.1 |
| `socket_rating` `general_use` | 콘센트 정격 · 일반인 사용(yes 기본) — 20 A 이하면 누전차단기 추가적 보호 대상 |

### 배선 `cable`

| 속성 | 뜻 |
|---|---|
| `from` `to` | 전원 측 · 부하 측 설비 |
| `length` | 길이. `length_basis = estimate`(기본) / `measured` / `cad` — estimate 면 전압강하 결과가 '추정' |
| `material` `size` `parallel` | 도체 재질(Cu/Al)·단면적(㎟)·병렬 회선 수 — 전압강하에 필수 |
| `insulation` | PVC / XLPE / EPR |
| `x` | 리액턴스(m 당). 없으면 기준 기본값 0.08 mΩ/m (KS C IEC 60364-5-52 부속서 G) |
| `ampacity` | 허용전류 IZ (보정 반영 값) — 직접 입력 |
| `install_method` `ambient` `grouping` | 공사방법(A1~D2)·주변 온도·집합 회로 수 → `ampacity` 없이 지식 DB 표 + 보정계수로 산정 |
| `arrangement` `spacing` `soil_resistivity` | 집합 배치 항(B.52.17 1~5) · 지중 간격(B.52.18) · 토양 열저항률(B.52.16) |
| `pe_size` `pe_separate` | 보호도체 단면적(미입력 시 표 142.3-1 최소 가정 → 추정) · 케이블 밖 별도 포설 |
| `circuit` | `final`(분기회로, 기본) / `distribution`(간선) — 자동차단 허용 시간 구분 |

### 본딩 `bond`

```c
bond B_W { from = MET; to = WATER; kind = main; material = Cu; size = 10mm2; }
```

`kind` = `main`(주 보호등전위본딩 — 단면적 판정) / `supplementary`(보조) / `earthing`(접지도체). 전력 흐름에는 쓰이지 않는다.
반의 `demand_factor` = 그 반 부하설비의 수용률(식 230-6 변압기 용량 산정, 사용자 근거).

### 그룹·시나리오·시스템

```c
group PUMPS { max_on = 2; }                         // 동시 운전 대수 제약 → 'max_demand' 시나리오
scenario summer_peak { on = [P1, P2, HT1]; }        // on 에 설비·그룹·반(그 아래 부하 전부)·all
scenario night { off = [PNL_A]; }                   // on 생략 = 정상 운전 상태에서 off 만 제외
system plant { frequency = 60Hz; rules = kec_lv; review_below = 80%; }
```

`review_below`: 사용률이 이보다 낮고 선정 근거가 없으면 '선정 근거' REVIEW (프로그램 설정, 규정 아님 — 기본 80%).
`motor_start_vd_limit`: 기동 중 허용 전압강하(기기 요구값). KEC 는 기동 중 더 큰 강하를 허용하되 수치가 없다 — 없으면 값과 질문.

접지·수전(Phase 3) `system` 속성:

| 속성 | 뜻 |
|---|---|
| `earthing` | `TN-S` `TN-C` `TN-C-S` `TT` `IT` — 없으면 고장보호 판정 UNKNOWN |
| `ra` `rb` | TT/IT 설비 측 접지저항 합 RA · TT 전원 측 RB (Ω) |
| `id_first_fault` `insulation_monitor` | IT 1차 고장전류 · 절연감시장치 유무 |
| `contract_kw` | 계약전력 (최대수요전력·변압기 정격과 따로 비교) |
| `diversity` `capacity_margin` | 부등률 · 변압기 여유계수 α (식 230-6) |
