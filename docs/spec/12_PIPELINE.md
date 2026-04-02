# 13. 파이프라인 및 인터페이스 (Pipeline & Interfaces) 명세

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL 시스템은 파일, 메모리(그래프), 데이터베이스 간의 무결성을 유지하며, 다양한 단위계와 규격을 통합 관리하는 파이프라인을 가집니다.

## 1. 프로젝트 관리 및 데이터 파이프라인

### 1.1 [S-PIP-001] 정규화 계층 (Normalization Layer)
파서가 생성한 AST를 계산 엔진용 엔티티로 변환하는 과정에서 다음 검증 및 보완 작업을 수행한다.
*   **Default Injection:** DSL에서 생략된 속성에 대해 `APPENDIX_A`의 표준 기본값을 주입한다.
*   **Unit Normalization:** 모든 수치 데이터를 내부 표준 단위(SI)로 일괄 변환한다.
*   **Reference Resolution:** `connect` 문에 정의된 ID를 실제 엔티티 객체의 포인터(참조)로 바인딩한다.

### 1.2 [S-PIP-002] 데이터 출처 추적 (Provenance Tracking)
시스템은 모든 계산 결과값($V, P, h_f$ 등)에 대해 역추적을 위한 메타데이터를 유지한다.
*   **Source Binding:** 결과값이 유도된 원본 DSL의 라인 번호와 식별자를 연결한다.
*   **Formula Binding:** 계산에 사용된 공식 ID(`FOR-DW-001` 등)를 기록한다.
*   **Assumption Log:** 계산 중 적용된 기본값(Default)이나 가정 사항을 별도 로그로 유지하여 리포트에 반영한다.

### 1.3 [S-PIP-003] 저널 기반 장애 복구 (Journal Recovery)
비정상 종료 후 재기동 시 다음 절차에 따라 데이터를 자동 복구한다.
1.  **Detection:** `project_meta` 테이블의 `journal_status`가 `DIRTY`인 경우 복구 모드로 진입한다.
2.  **Redo Process:** 마지막 체크섬 저장 이후 `.journal` 파일에 기록된 모든 변경 이벤트를 순차적으로 재실행한다.
3.  **Consistency Check:** 복구된 메모리 모델과 `state.db` 간의 무결성을 검증하고, 불일치 시 `state.db`를 폐기하고 원문 재파싱을 트리거한다.

## 2. 양방향 동기화 (Inverse Synchronization Protocol)

### 2.1 [S-PIP-004] 스마트 패치 알고리즘 (Smart Patching)
GUI 수정 사항을 DSL 텍스트에 반영할 때 소스 코드의 서식을 보존하기 위해 다음 규칙을 따른다.
*   **Line-based Replace:** 수정된 속성이 위치한 줄(Line)만 특정하여 값을 치환하고, 주석(`//`)이나 빈 줄은 보존한다.
*   **Atomic Buffer:** 패치된 텍스트를 임시 버퍼에 먼저 생성하고, 문법 검증(`Validating`) 통과 시에만 최종 파일에 덮어쓴다.

## 3. 라이브러리 및 규격 관리 (`LibraryManager`)

### 3.1 [S-PIP-005] 자동 피팅 손실 계산 (Auto-Fitting)
네트워크 구성 시 배관 간의 연결 각도를 분석하여 국부 손실 계수($K$)를 자동 산출한다.
*   **Angle Calculation:** $\vec{V}_{in}$과 $\vec{V}_{out}$의 내적을 통해 꺾임각($\theta$)을 도출한다.
*   **K-factor Selection:** $\theta \approx 90^\circ$ 인 경우 엘보(Elbow), 분기 시에는 티(Tee) 계수를 라이브러리에서 조회하여 `loss_k`에 합산한다.

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
*   **대응:** DB 쓰기 실패 시 즉시 'Memory-only' 운영 모드로 전이하며 `WRN006 (Cache DB Failed)` 경고를 발생시킨다. 이 모드에서는 GUI의 실시간 부분 동기화(Inverse Sync)가 차단되고, 전체 저장 시 원본 `.fhd` 파일만 덮어쓴다. 메모리의 산출물은 1회성 리포트 출력에만 허용되며, 애플리케이션 종료 시 모두 폐기된다.

### 6.3 PySide6 (GUI 엔진) 장애
*   **장애 유형:** 캔버스 렌더링 오류, 위젯 충돌.
*   **대응:** 그래픽 뷰어(NetworkViewer)를 비활성화하고 텍스트 기반 로그 및 결과 리포트(CSV)로만 정보를 제공하는 'Safe Mode'로 전환합니다.

---
[목차로 돌아가기](./INDEX.md)
