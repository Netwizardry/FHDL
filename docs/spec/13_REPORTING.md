# 14. 리포트 및 출력 (Reporting & Output) 명세

FHDL 시스템은 시뮬레이션 결과를 구조화된 파일 형식으로 출력하여 외부 도구와의 연동 및 설계 검증을 지원합니다.

## 1. 출력 구조 및 메타데이터 규범

### 1.1 [S-REP-001] 리포트 헤더 메타데이터 (Provenance Header)
모든 출력 파일 상단에는 재현성(Reproducibility) 확보를 위해 다음 메타데이터를 반드시 포함해야 한다.
*   **Engine:** FHDL Core v0.1 (Build 20260402)
*   **Friction Model:** `DW` (Darcy-Weisbach) 또는 `HW` (Hazen-Williams) 명시.
*   **Fluid Props:** Density ($\rho$), Viscosity ($\mu$) 또는 C-factor 적용값.
*   **Source Hash:** 입력 `.fhd` 파일의 SHA-256 체크섬.

## 2. [S-REP-002] 데이터 출처 및 컬럼 매핑 (Data Provenance Map)

리포트의 각 컬럼은 내부 모델 및 수식과 다음과 같이 매핑된다.

### 2.1 Nodes_Report.csv 매핑
| 컬럼명 | 내부 소스 필드 (Entity) | 적용 공식 / 로직 |
| :--- | :--- | :--- |
| `Node_ID` | `Node.id` | - |
| `X, Y, Z` | `Node.x, y, z` | DSL 입력값 또는 Default |
| `Head` | `NetworkNode.h_total` | Pass 2 수리 평형 결과 |
| `Pressure` | `NetworkNode.p_gauge` | [FOR-PTH-001] 수두-압력 환산 |
| `Req Q` | `Node.required_q` | DSL `flow` 속성 정규화값 |
| `Sizing` | `Node.sizing_mode` | `MANUAL`, `AUTO`, `DERIVED` |

### 2.2 Pipes_Report.csv 매핑
| 컬럼명 | 내부 소스 필드 (Entity) | 적용 공식 / 로직 |
| :--- | :--- | :--- |
| `Pipe_ID` | `Pipe.id` | - |
| `Diameter` | `Pipe.diameter` | `SizingMode`에 따른 확정치 |
| `Velocity` | `NetworkEdge.v_actual` | [FOR-V-001] 연속 방정식 ($Q/A$) |
| `HeadLoss` | `NetworkEdge.h_loss_total` | [FOR-DW-001] 또는 [FOR-HW-001] |
| `SurgeIdx` | `NetworkEdge.surge_index` | [S-SOL-005] 간이 수격 위험도 |
| `Formula` | `Provenance.formula_id` | 실제 계산에 적용된 공식 ID |

## 3. 요약 리포트 명세 (Simulation_Summary.json)

### 3.1 [S-REP-003] 시스템 통계 및 수렴 정보
*   **convergence:** 수렴 여부(`True/False`), 최종 잔차(Residual), 반복 횟수.
*   **worst_case:** 최불리 경로 ID, 해당 경로의 총 손실, 요구 펌프 양정.
*   **sizing_summary:** `auto`로 산정된 모든 부품의 이전/이후 사양 비교표.

## 4. 데이터 표기 규칙

*   **인코딩:** Excel 호환성을 위해 `UTF-8-SIG` 사용.
*   **정밀도:** 기하학적 수치는 소수점 3~4자리, 압력 및 유동 수치는 정밀도 확보를 위해 지수 표기법(`1.2345e-01`) 사용.

---
[목차로 돌아가기](./INDEX.md)
