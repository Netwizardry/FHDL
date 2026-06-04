# FHDL 언어 레퍼런스

> 정본: `core/language.py`(키워드·노드타입·단위), `core/fittings.py`(부속), `core/materials.py`(재질).
> 파서: `core/parser.py`, 의미분석: `core/semantic.py`.

## 블록 구조

```c
system <name> { ... }          // 전역 설정 (1개)
tank   <id>   { ... }          // 수원/저수조
pump   <id>   { ... }          // 펌프 (normal | submersible)
junction <id> { ... }          // 분기점
terminal <id> { ... }          // 말단 수요처
pipe   <id>   { ... }          // 배관 (엣지)
constraint    { ... }          // 설계 제약
connect A -> B -> C;           // 노드/배관 연결 (방향성)
```
주석: `//` 행 주석, `/* */` 블록 주석.

## 좌표와 datum

- `system.altitude` = 프로젝트 **기준 해발(datum)**.
- 노드의 **`z`** = datum 기준 **상대 고도**. 절대 해발 = `altitude + z`.
- `elevation` 은 `z` 의 하위호환 별칭(둘 다 인식).
- `x`, `y` = 평면 좌표(토폴로지 시각화·자동 길이 추정·꺾임각 auto_k 용).

## 블록별 속성

### system
| 키 | 의미 | 예 |
|---|---|---|
| `unit_system` | METRIC \| IMPERIAL (표시 단위) | `METRIC` |
| `fluid` | 유체 | `water` |
| `temp` | 온도 °C (0~100) — 밀도·점도·증기압 결정 | `20` |
| `altitude` | 기준 해발 m (−500~10000) — 대기압 결정 | `70m` |
| `friction_model` | DW(Darcy-Weisbach) \| HW(Hazen-Williams) | `DW` |

### tank
`z`, `volume`(생략 시 무한), `level_max`(최고 수위), `x`, `y`.

### pump
`z`, `flow`/`head`(MANUAL 지정 시 실제 양정 주입, 생략 시 auto=사양 선정 대상), `efficiency`, `npshr`, `x`, `y`.
수중펌프: `pump_type = submersible;`, `min_level`, `submerge_ref`.

### terminal
`z`, `required_q`(요구 유량), `required_p`(요구 압력), `x`, `y`.

### pipe
`start`, `end`(생략 시 connect 체인에서 추론), `length`(0 또는 생략 시 좌표 거리), `diameter`(`auto` 또는 값), `material`, `fittings`, `k_factor`, `roughness`/`c_factor`(명시 시 재질값 override).

### constraint
`velocity_min`, `velocity_max`, `safety_factor_head`, `safety_factor_npsh`.

## 재질 (`material`)

재질을 지정하면 조도·C계수가 **자동 적용**된다(명시 `roughness`/`c_factor` 가 우선).

| id | 조도(mm) | C(HW) | 별칭 |
|---|---|---|---|
| Steel | 0.045 | 120 | |
| Cast_Iron | 0.26 | 100 | CI |
| PVC | 0.0015 | 150 | |
| PE / HDPE | 0.007 | 145 | |
| SUS304 / SUS316 | 0.015 | 140 | STS |
| Copper | 0.0015 | 135 | |
| Double_Wall, Perforated | — | — | |

## 부속 (`fittings`)

리스트 문법, 개수 표기 `name*N`:
```c
pipe p { ...; fittings = [elbow_90*2, valve_gate, valve_check]; }
```
국부손실 `K = k_factor + Σ(부속 K)` 로 계산. 대표 K: `elbow_90`=0.9, `elbow_45`=0.4, `tee_branch`=1.8, `valve_gate`=0.2, `valve_globe`=10, `valve_check`=2.5, `reducer`=0.5 … (전체 34종은 `core/fittings.py`). 대문자 별칭(ELBOW90, GATE_VALVE 등) 호환.

또한 좌표가 있으면 **경로 꺾임각으로 엘보 K(auto_k)** 가 자동 가산된다.

## 단위

| 물리량 | 내부(SI) | METRIC | IMPERIAL |
|---|---|---|---|
| 유량 | m³/s | L/min | GPM |
| 압력 | Pa | MPa | psi |
| 수두·길이 | m | m | ft |
| 관경 | m | mm | inch |
| 유속 | m/s | m/s | m/s |

입력 단위 토큰: `m, mm, ft, inch, m3, lpm, gpm, ls, m3s, m3h, MPa, kPa, bar, psi, Pa` 등.

## 예시

```c
system main {
    unit_system = METRIC; fluid = water; temp = 20; altitude = 70m;
    friction_model = DW;
}
constraint { velocity_max = 2.5m; safety_factor_head = 1.1; }

tank reservoir { z = 10m; volume = 50m3; level_max = 1.5m; }
junction j1     { z = 5m; x = 50; y = 0; }
terminal sprinkler { z = 3m; required_q = 80lpm; required_p = 0.1MPa; x = 100; y = 30; }

pipe main_pipe { start = reservoir; end = j1; length = 60m; diameter = auto; material = Steel; }
pipe branch    { start = j1; end = sprinkler; length = 35m; diameter = auto; material = PVC;
                 fittings = [elbow_90, valve_gate]; }

connect reservoir -> j1 -> sprinkler;
```
