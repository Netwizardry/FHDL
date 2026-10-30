# 진단 코드

> 실제 발생 코드는 `core/parser.py`·`semantic.py`·`solver.py`·`pipeline.py` 기준.
> 심각도: ERROR/FATAL → 차단(상태 FAILED 또는 PARTIAL), WARNING → 비차단.

## 구문 (SYN) — parser
| 코드 | 의미 |
|---|---|
| `SYN001` | 문법 오류(예: connect 노드 부족, 빈 코드, 잘못된 토큰) |
| `SYN002` | 알 수 없는 블록 키워드(예: `nozzle {}`) — 조용히 버리지 않음 |
| `SYN003` | 중괄호 짝이 맞지 않음(닫히지 않은 블록이 다음 블록 속성을 삼키는 것 방지) |
| `INT001` | 내부 오류(FATAL) — 해석기는 예외를 던지지 않고 이 진단으로 돌려준다 |

## 의미 (SEM) — semantic
| 코드 | 의미 | 심각도 |
|---|---|---|
| `SEM001` | 중복 ID | ERROR |
| `SEM002` | 정의되지 않은 ID 참조(배관 start/end, connect) | ERROR |
| `SEM003` | 배관 start/end 누락(connect 체인 추론 후에도) | ERROR |
| `SEM004` | 라이브러리에 없는 재질 → 기본(Steel) 물성 사용 | WARNING |
| `SEM005` | 노드 절대 해발(datum+z)이 범위(−500~10000m) 초과 | WARNING |
| `SEM006` | 유체 온도 범위(0~100°C) 초과 | WARNING |
| `SEM007` | 배관 길이 ≤ 0 | ERROR |
| `SEM008` | 양 끝점 x/y 명시 + `length` < 경로 길이(via 경로 또는 끝점 3D 직선거리, 물리적으로 불가능) | WARNING |
| `SEM009` | `length` 생략(좌표 추정)인데 끝점 x/y 미지정 | WARNING |
| `SEM010` | `via` 항목이 `(x, y, z)` 형식이 아님 / 끝점 x/y 가 없어 via 무시 | WARNING |
| `SEM011` | 부속 위치(`@`)가 배관 길이를 벗어남 | WARNING |
| `SEM012` | 알 수 없는 단위 / 속성 차원과 다른 단위(유량에 압력 단위 등) / 수치가 아닌 값. 모르는 단위를 1배로 가정하지 않는다. 유속의 `m` 은 하위호환으로 m/s 로 읽고 WARNING | ERROR |
| `SEM013` | 그 블록에 없는 속성 (무시) | WARNING |
| `SEM014` | 선택지 밖의 값(`friction_model`·`unit_system`·`pump_type` → ERROR, `fluid` 물 이외 → 물 물성 사용 WARNING) / 통상 범위 밖 수치(efficiency·c_factor·안전율 → WARNING) | ERROR/WARNING |
| `SEM015` | 부속 라이브러리에 없는 부속 이름 → K=0 | WARNING |
| `SEM016` | `pipe_standard` 의 관경이 부품 라이브러리에 없음 → KS 관경으로 Auto-sizing | WARNING |

## 기본값 (DEF) — semantic
| 코드 | 의미 | 심각도 |
|---|---|---|
| `DEF001` | 입력이 없어 기본값 적용(재질 Steel·펌프 효율 0.75·NPSHr 0.5 m·최고 수위 2 m·유속 제약·안전율·국부 손실 K=0 등) — 항목별 대상 목록 | INFO |

속성 목록·차원·허용 단위·선택지·범위는 `core/language.py` 의 `BLOCK_ATTRS`·`DIMENSION_UNITS`·`ENUM_VALUES`·`VALUE_RANGES` 가 단일 진실원.

## 네트워크 (NET) — solver
| 코드 | 의미 | 심각도 |
|---|---|---|
| `NET001` | 고립 노드(진입·진출 차수 0) | ERROR |
| `NET002` | 노드 없음 / 공급원(tank·pump) 없음 | ERROR |
| `NET003` | 공급원에서 도달 불가 | ERROR |
| `NET004` | 복합 루프(공급원과 연결된 순환) — v0.1 미지원 경고 | WARNING |
| `NET005` | Dead Loop(공급원 없는 순환 루프) | ERROR |
| `NET006` | connect↔배관 불일치(배관 없는 connect / 역방향) | WARNING |

## 계산 (CAL) — solver
| 코드 | 의미 |
|---|---|
| `CAL002` | Newton-Raphson 수압 평형 미수렴(최대 100회) |
| `CAL003` | 리포트 저장 실패 등 연산 오류 |
| `CAL004` | 사용자가 해석을 중단 — 상태 `CANCELLED`, 부분 결과는 표시·캐시·리포트하지 않음 |
| `CAL005` | 유속 제약을 만족하는 표준 관경 없음(Auto-sizing 실패) |

## 설계 경고 (WRN) — solver (모두 WARNING)
| 코드 | 의미 |
|---|---|
| `WRN001` | 유속이 velocity_min/max 범위 위반 |
| `WRN002` | 말단(terminal) 미정의 → 요구 유량 0 |
| `WRN003` | NPSHa < NPSHr × 안전율 (캐비테이션 위험) |
| `WRN004` | 수충격 위험 지수 > 0.8 |
| `WRN005` | 계산 압력이 진공(증기압) 한계 아래 — 표시 압력은 `−대기압 + 증기압` 으로 제한 |
| `WRN006` | 말단 압력이 `required_p` 에 미달 |

> WRN005·WRN006 은 AUTO 펌프(양정 auto·커브 없음) **하류** 노드에는 내지 않는다. 그 구간은 양정이 0 으로 주입된 사양 선정 전 상태이고, 부족분은 권장 펌프 양정(`recommended_pump_head`)으로 산정된다.

## 상태(status) 판정 (`pipeline`)

- FATAL 진단 → `FAILED`
- 차단(ERROR) 진단 존재 → `PARTIAL` (결과는 반환하되 일부 무효)
- 사용자 중단 → `CANCELLED` (결과 폐기, 편집 상태로 복귀)
- 그 외 → `OK`

수렴 여부·반복 횟수·잔차(`summary.converged`·`solve_iterations`·`residual`)는 실제 반복 계산 결과를 기록한다
(Simulation_Summary.json 에도 출력).
