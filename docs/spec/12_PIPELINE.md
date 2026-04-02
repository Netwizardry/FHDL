# 13. 파이프라인 및 인터페이스 (Pipeline & Interfaces) 명세

FHDL 시스템은 파일, 메모리(그래프), 데이터베이스 간의 무결성을 유지하며, 다양한 단위계와 규격을 통합 관리하는 파이프라인을 가집니다.

## 1. 프로젝트 관리 및 동적 동기화

### 1.1 삼각 동기화 (Triple Synchronization)
시스템은 변경 사항 발생 시 다음의 세 레이어를 동시에 업데이트하여 데이터 일관성을 보장합니다.
1.  **메모리(Memory):** `FluidSystem` 객체 및 NetworkX 그래프 엔진. 실시간 계산용.
2.  **데이터베이스(Cache DB):** `state.db` (SQLite). 고성능 쿼리 및 UI 상태 유지용.
3.  **소스 파일(Source File):** `main.fhd`. 사용자의 설계 원본 데이터 (Atomic Save 적용).

## 1.3 양방향 동기화 (Inverse Synchronization Protocol - C01)
시스템은 캔버스의 그래픽 수정 사항을 텍스트 소스(.fhd)에 역으로 반영하기 위해 다음의 패치(Patch) 알고리즘을 사용합니다.

1.  **Graphic Event Capture:** 사용자가 노드 위치를 변경하거나 속성을 수정할 때 `ModificationEvent` 발생.
2.  **Source Mapping:** 해당 그래픽 객체의 ID와 소스 코드 내 `SourceSpan`(Line/Col) 정보를 매칭.
3.  **Smart Patching:** 원본 텍스트 전체를 덮어쓰지 않고, 해당 블록의 값만 정규식 또는 AST 기반으로 치환(Replace)하여 주석과 서식을 유지.
4.  **Conflict Resolution:** 텍스트 에디터와 캔버스가 동시에 수정될 경우, 텍스트 에디터의 `Source of Truth` 권한을 우선하며 캔버스는 '재로드 대기' 상태로 전환.

## 2. 단위 변환 및 물성 엔진 (`UnitConverter`)
...
모든 내부 연산은 **SI 표준 단위**를 사용하며, 입출력 시에만 설정된 단위계에 따라 변환합니다.

| 물리량 | 내부 표준 단위 (SI) | METRIC (사용자용) | IMPERIAL (사용자용) |
| :--- | :--- | :--- | :--- |
| 유량 | $m^3/s$ | L/min | GPM |
| 압력 | Pa | MPa | PSI |
| 길이/수두 | m | m | ft |
| 온도 | °C | °C | °F |

## 3. 라이브러리 및 규격 관리 (`LibraryManager`)

### 3.1 명칭 기반 내경 검색
배관 정의 시 `50A`, `2"` 등의 공칭 명칭(Nominal Size)을 입력하면, 라이브러리(`STANDARD_MATERIALS`)에서 해당 재질의 **실제 내경(Actual Diameter)**을 자동으로 찾아 할당합니다.

### 3.2 자동 피팅 손실 계산 (Auto-Fitting)
두 배관 노드의 벡터를 분석하여 꺾임각을 계산하고, 이에 적합한 K-factor(예: 90도 엘보 = 0.9)를 자동으로 산출하여 `Pipe.auto_fittings_k`에 반영합니다.

## 4. 모듈 간 데이터 계약 (Interface Contracts)

모듈 간 데이터 전달의 핵심인 `FluidSystem` 객체는 다음의 규격을 엄격히 준수해야 합니다.

### 4.1 `FluidSystem` (Top-level Object)
| 필드명 | 타입 | 필수 | 허용 범위 (SI) | 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `str` | Y | - | 프로젝트 고유 식별자 |
| `fluid_type` | `enum` | Y | water, brine | 유체 종류 |
| `temp` | `float` | Y | 0.0 ~ 100.0 | 유체 온도 (°C) |
| `nodes` | `dict` | Y | 1개 이상 | ID를 키로 하는 Node 객체 맵 |
| `pipes` | `dict` | Y | 0개 이상 | ID를 키로 하는 Pipe 객체 맵 |
| `materials` | `dict` | Y | 1개 이상 | ID를 키로 하는 Material 객체 맵 |

### 4.2 `Node` Entity Spec
| 필드명 | 타입 | 필수 | 허용 범위 (SI) | 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `str` | Y | - | 노드 고유 식별자 |
| `type` | `enum` | Y | TANK, PUMP, JUNCTION, TERMINAL | 노드 유형 |
| `z` | `float` | Y | -100 ~ 10000 | 고도 (m) |
| `required_q` | `float` | N | $\ge 0$ | 요구 유량 ($m^3/s$) |
| `required_p` | `float` | N | $\ge 0$ | 요구 압력 (Pa) |
| `head` | `float` | (Calc) | - | 계산된 총 수두 (m) |

### 4.3 `Pipe` Entity Spec
| 필드명 | 타입 | 필수 | 허용 범위 (SI) | 설명 |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `str` | Y | - | 배관 고유 식별자 |
| `start_node` | `str` | Y | - | 상류 노드 ID (참조 무결성) |
| `end_node` | `str` | Y | - | 하류 노드 ID (참조 무결성) |
| `length` | `float` | Y | $> 0$ | 배관 길이 (m) |
| `diameter` | `float` | Y | $> 0$ | 실제 내경 (m) |
| `material_id` | `str` | Y | - | 재질 ID (참조 무결성) |
| `velocity` | `float` | (Calc) | 0 ~ 5.0 | 계산된 유속 (m/s) |
| `head_loss` | `float` | (Calc) | $\ge 0$ | 계산된 손실수두 (m) |

## 5. 예외 반환 및 에러 구조 (A05/M01)

모든 모듈은 예외(Exception)를 직접 던지는 대신, 아래의 구조화된 `AnalysisResult` 객체를 반환하여 GUI에 진단 정보를 전달해야 합니다.

```python
class DiagnosticItem(NamedTuple):
    code: str         # 예: SEM004
    severity: str     # INFO, WARNING, ERROR, FATAL
    message: str      # 사용자 메시지
    source_span: dict # {line: int, col: int}

class AnalysisResult(NamedTuple):
    status: str       # OK, FAILED, PARTIAL
    data: Optional[Any]
    diagnostics: List[DiagnosticItem]
```

*   **강제 사항:** `Solver.solve()` 호출 시 예외 발생은 오직 시스템 치명적 오류(Memory, I/O)로 제한하며, 수리적 발산이나 데이터 오류는 반드시 `AnalysisResult(status='FAILED')`로 반환해야 합니다.

## 6. 외부 의존성 및 장애 대응 (A11)

FHDL 시스템은 외부 라이브러리 및 시스템 장애 시 다음의 대응 시나리오를 따릅니다.

### 6.1 NetworkX (그래프 엔진) 장애
*   **장애 유형:** 위상 구조 복잡도로 인한 변환 실패, 비정상적 루프 검출 불가 등.
*   **대응:** `NET` 계열 에러(예: NET002)를 발생시키고 해석을 중단합니다. 단순 트리 구조의 경우 내장 재귀 알고리즘으로 대체(Fallback) 시도를 수행합니다.

### 6.2 SQLite (Cache DB) 장애
*   **장애 유형:** 파일 권한 오류, DB 손상(Corrupted), 데이터 잠금(Locked).
*   **대응:** DB 쓰기에 실패하더라도 'Memory-only' 모드로 해석을 계속 진행합니다. 단, 사용자에게 "캐시 저장 실패" 경고를 표시하고 다음 세션 로드 시 원문 재파싱을 강제합니다.

### 6.3 PySide6 (GUI 엔진) 장애
*   **장애 유형:** 캔버스 렌더링 오류, 위젯 충돌.
*   **대응:** 그래픽 뷰어(NetworkViewer)를 비활성화하고 텍스트 기반 로그 및 결과 리포트(CSV)로만 정보를 제공하는 'Safe Mode'로 전환합니다.

---
[목차로 돌아가기](./INDEX.md)
