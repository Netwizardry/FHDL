# 진단 코드

> 실제 발생 코드는 `core/parser.py`·`semantic.py`·`solver.py`·`pipeline.py` 기준.
> 심각도: ERROR/FATAL → 차단(상태 FAILED 또는 PARTIAL), WARNING → 비차단.

## 구문 (SYN) — parser
| 코드 | 의미 |
|---|---|
| `SYN001` | 문법 오류(예: connect 노드 부족, 빈 코드, 잘못된 토큰) |

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
| `CAL005` | 유속 제약을 만족하는 표준 관경 없음(Auto-sizing 실패) |

## 설계 경고 (WRN) — solver (모두 WARNING)
| 코드 | 의미 |
|---|---|
| `WRN001` | 유속이 velocity_min/max 범위 위반 |
| `WRN002` | 말단(terminal) 미정의 → 요구 유량 0 |
| `WRN003` | NPSHa < NPSHr × 안전율 (캐비테이션 위험) |
| `WRN004` | 수충격 위험 지수 > 0.8 |
| `WRN005` | 압력이 진공 한계(해당 노드 대기압의 음수) 도달 |

## 상태(status) 판정 (`pipeline`)

- FATAL 진단 → `FAILED`
- 차단(ERROR) 진단 존재 → `PARTIAL` (결과는 반환하되 일부 무효)
- 그 외 → `OK`
