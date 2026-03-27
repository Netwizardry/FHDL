# 17. 용어 정의 및 명명 규칙 (Terminology & Naming)

FHDL 시스템은 문서, 코드, 테스트, UI 전반에서 일관된 용어와 명명 규칙을 사용하여 소통의 효율성을 높이고 해석의 오류를 최소화합니다.

## 1. 핵심 용어 정의

### 1.1 시스템 및 구조 관련
*   **시스템 (System):** FHDL 문서에서 `system` 블록으로 선언되는 최상위 설계 및 계산 단위.
*   **구성요소 (Component):** `tank`, `pump`, `pipe` 등 FHDL 문법상 독립적으로 선언되는 모든 설비 요소.
*   **엔티티 (Entity):** 구성요소가 시스템 내부(Semantic 레이어)에서 정규화된 데이터 객체.
*   **말단 장치 (Terminal):** 유량 요구 또는 수두를 발생시키는 시스템의 최종 지점(`nozzle`, `sprinkler` 등).
*   **분기점 (Junction):** 배관의 흐름이 나뉘거나 합쳐지는 구조적 지점.

### 1.2 네트워크 및 계산 관련
*   **최불리 경로 (Worst-Case Path):** 전체 경로 중 `정수두 + 마찰손실 + 말단 요구수두`의 합이 가장 커서 펌프 선정의 기준이 되는 경로.
*   **총 요구양정 (Total Required Head):** 최불리 경로를 기준으로 산출된 시스템 전체의 필요 양정.
*   **자동선정 (Auto-Sizing):** 시스템이 설계 제약에 맞춰 관경, 펌프 등을 자동으로 결정하는 프로세스.
*   **수동 지정 (Manual Override):** 자동 산정 대신 사용자가 고정한 특정 값.

## 2. 한/영 표준 용어 대응표

| 한국어 표준 용어 | 영문 대응 (Internal/Code) | 비고 |
| :--- | :--- | :--- |
| **시스템** | System | - |
| **최불리 경로** | WorstCasePath | `worst_case_path_id` |
| **총 요구양정** | TotalRequiredHead | `total_required_head` |
| **손실수두** | HeadLoss | `head_loss` |
| **마찰손실** | FrictionLoss | `friction_loss` |
| **국부손실** | LocalLoss | `local_loss` |
| **정수두** | StaticHead | `static_head` |
| **자동선정 결과** | AutoSizingResult | `auto` 키워드 대응 |

## 3. 명명 규칙 (Naming Conventions)

### 3.1 FHDL 문법 요소
*   **키워드:** 항상 영문 소문자를 사용합니다. (예: `system`, `pipe`, `connect`)
*   **식별자 (ID):** 소문자, 숫자, 밑줄을 조합한 `snake_case`를 권장합니다. (예: `main_pipe_1`, `tank_a`)
*   **속성명:** 영문 소문자 `snake_case`를 사용합니다. (예: `unit_flow`, `jet_height`)

### 3.2 내부 코드 및 객체
*   **클래스/타입:** `PascalCase`를 사용합니다. (예: `FluidSystem`, `PipeEntity`)
*   **필드/변수:** `snake_case`를 사용합니다. (예: `selected_diameter`, `is_dirty`)
*   **진단 코드:** `접두어+3자리숫자` 형식을 유지합니다. (예: `SYN001`, `CAL005`)

### 3.3 예제 및 테스트 파일
*   **예제:** `EX-<번호>_<이름>.fhd` (예: `EX-001_single_nozzle.fhd`)
*   **테스트:** `T-<분류>-<번호>` (예: `T-CAL-006`)

---
[목차로 돌아가기](./INDEX.md)
