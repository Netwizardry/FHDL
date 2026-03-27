# 05. 리포트 및 출력 (Reporting & Output) 명세

FHDL 시스템은 시뮬레이션 결과를 구조화된 파일 형식으로 출력하여 외부 도구와의 연동 및 설계 검증을 지원합니다.

## 1. 출력 디렉토리 구조

모든 시뮬레이션 결과는 프로젝트의 `outputs/` 폴더 내에 실행 시간별로 생성됩니다.
```text
outputs/
└── run_YYYYMMDD_HHMMSS/       # 시뮬레이션 실행별 고유 폴더
    ├── Nodes_Report.csv      # 노드 상세 결과
    ├── Pipes_Report.csv      # 배관 상세 결과
    └── Simulation_Summary.json # 실행 요약 정보
```

## 2. CSV 리포트 스키마

### 2.1 Nodes_Report.csv
각 노드의 위치, 수두, 압력 및 설계 요구 유량을 기록합니다.

| 컬럼명 | 단위 (Metric) | 단위 (Imperial) | 설명 |
| :--- | :--- | :--- | :--- |
| `Node_ID` | - | - | 노드 식별자 |
| `Type` | - | - | NodeType (TANK, PUMP, JUNCTION 등) |
| `X, Y, Z` | m | ft | 3D 좌표 |
| `Head` | m | ft | 계산된 총 수두 |
| `Pressure` | MPa | PSI | 노드에서의 정수압 |
| `Surge` | MPa | PSI | 수충격으로 인한 추가 압력 |
| `Req Q` | L/min | GPM | 설계 시 설정된 요구 유량 |

### 2.2 Pipes_Report.csv
각 배관의 기하학적 정보와 유동 해석 결과를 기록합니다.

| 컬럼명 | 단위 (Metric) | 단위 (Imperial) | 설명 |
| :--- | :--- | :--- | :--- |
| `Pipe_ID` | - | - | 배관 식별자 |
| `From, To` | - | - | 연결 노드 ID |
| `Length` | m | ft | 계산된 배관 실길이 |
| `Diameter` | mm | in | 배관 내경 |
| `Velocity` | m/s | ft/s | 유속 |
| `HeadLoss` | m | ft | 마찰 및 국부 손실의 합 |
| `Flow` | L/min | GPM | 계산된 실제 유량 |

## 3. 요약 데이터 스키마 (Simulation_Summary.json)

시뮬레이션 전체의 메타데이터와 시스템 통계를 저장합니다.
*   **metadata:** 소스 파일 해시(`fhd_hash`), 사용 단위계(`units`), 계산에 사용된 유체 밀도(`actual_density`) 등.
*   **results:** 총 노드 수, 총 배관 수, 수렴 여부 등 요약 정보.

## 4. 데이터 표기 규칙

*   **인코딩:** Excel 호환성을 위해 `UTF-8-SIG` 사용.
*   **정밀도:** 기하학적 수치는 소수점 3~4자리, 압력 및 유동 수치는 정밀도 확보를 위해 지수 표기법(`1.2345e-01`) 사용.
*   **헤더:** 파일 최상단에 주석(` # `)으로 원본 파일 해시와 단위계 정보를 기록하여 데이터 추적성(Traceability) 보장.

---
[목차로 돌아가기](./INDEX.md)
