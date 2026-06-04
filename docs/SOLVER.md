# 수리 해석 (SOLVER)

> 구현: `core/solver.py`. 입력 `EntityMap` → `(node_results, pipe_results, summary)`.

## 토폴로지 구성

- 엣지의 단일 진실원은 **배관**(`pipe.start_id → end_id`). `connect` 는 정합성 검증용.
- `networkx` 로 인접/역인접 그래프 구성, 무결성 검사(NET001~006) 수행.
- 좌표가 있으면 인접 배관 방향의 **꺾임각으로 엘보 K(auto_k)** 자동 산정.

## 2-Pass 해석

### Pass 1 — 유량 합성 (`_pass1_flow_synthesis`)
- 말단(terminal) 요구 유량을 **역방향 BFS**로 상류에 누적.
- 배관 통과 유량 = **말단(end 노드) 누적 수요** ÷ 진입 배관 수. (분기 정확 분배, 질량 보존)
- `diameter = auto` 배관은 `velocity_max` 를 만족하는 최소 표준 관경(KS) 자동 선정. 불가 시 `CAL005`.

### Pass 2 — 수압 평형 (`_pass2_hydraulic_balance`)
- 소스(탱크/펌프)에서 **순방향 BFS**로 수두 전파, 감쇠(0.5)·반복(최대 100, tol 1e-4). 미수렴 시 `CAL002`.
- 노드 초기 수두: 탱크=고도+수위, **펌프=흡입수두+양정(MANUAL head)**, 기타=고도.
- 배관 손실 = 마찰손실 + 국부손실:
  - **Darcy-Weisbach**: `h_f = f·(L/D)·v²/2g`, f는 Swamee-Jain(Colebrook 근사), 층류/천이/난류 처리.
  - **Hazen-Williams**: `h_f = 10.67·L·Q^1.852 / (C^1.852·D^4.87)`.
  - **국부손실**: `h_k = K·v²/2g`, `K = manual_k(직접+부속) + auto_k`.

## 펌프

- `head` 가 MANUAL 이면 **실제 에너지원**으로 주입: 공급수두 = 흡입수두(상류 탱크 수면 또는 펌프 고도) + 양정.
- `head` 가 auto 이면 고정수두 노드로 두고, 요약에서 권장 양정을 산정(사양 선정).

## NPSHa (펌프 노드)

```
NPSHa = 대기압수두 + 흡입정수두 − 증기압수두
```
- 대기압은 **펌프 실제 해발(datum + z)** 로 산정 → 해발↑ 시 NPSHa↓.
- 증기압은 온도로 결정 → 온도↑ 시 NPSHa↓.
- `NPSHa < NPSHr × SF` 시 `WRN003`(캐비테이션 경고).

## 설계 진단 (Rules)

- `WRN001` 유속 범위(velocity_min/max) 위반
- `WRN002` 말단 없음(요구 유량 0)
- `WRN004` 수충격 위험 지수 `ρ·a·v / P_allow > 0.8`
- `WRN005` 진공 한계: 게이지압 ≤ −(해당 노드 대기압)

## 사양 산정 요약 (`SystemSummary`)

총 유량, **최불리 경로**(정적 요구수두 + 경로 마찰손실 최대), 권장 펌프 유량·양정(×SF), 권장 탱크 용량, provenance_map.

## 물성 (`FluidConfig`)

- 밀도/점도/증기압: 온도 함수.
- 대기압: 절대 해발의 ISA 표준 기압식 `atm_pressure_at(h)`.
