# Fluid-HDL: Fluid Hardware Description Language (v1.4)

## 1. 물리 정수 및 수리 공식 (Physical Constants & Formulas)

### 1.1 유체 물성 (Fluid Properties) - Water 기준
*   **밀도 ($\rho$):** $\rho(T) = 1000 \cdot [1 - \frac{(T - 4)^2}{119000}]$ ($kg/m^3$)
*   **증기압 ($P_{vap}$):** $\log_{10}(P_{vap}) = 8.07131 - \frac{1730.63}{233.426 + T}$ (mmHg, Antoine eq)
*   **대기압 ($P_{atm}$):** $P_{atm} = 101.325 \cdot (1 - 2.25577 \cdot 10^{-5} \cdot Altitude)^{5.25588}$ (kPa)

### 1.2 손실 공식 (Loss Formulas)
*   **Hazen-Williams (마찰 손실):**
    $$h_f = 10.666 \cdot C^{-1.852} \cdot D^{-4.87} \cdot L \cdot Q^{1.852}$$
    *   $L$ (Pipe Length)은 노드간 3D 거리로 자동 계산: $L = \sqrt{\Delta x^2 + \Delta y^2 + \Delta z^2}$
*   **부속류 국부 손실 ($h_m$):** $h_m = \sum K \cdot \frac{v^2}{2g}$ (m)
*   **펌프 커브 보간:** 선형 보간(Linear Interpolation) 사용. $Q > Q_{max}$ 일 경우 경고 후 기울기 유지하여 외삽(Extrapolation).

---

## 2. DSL 구문 및 파싱 규칙 (Syntax & Parsing Rules)

### 2.1 일반 규칙 (General Rules)
*   **대소문자:** 키워드(`node`, `pipe` 등)는 대소문자 무관. ID(`N1`, `P1`)는 대소문자 구분.
*   **주석:** `//` (Line) 및 `/* ... */` (Block) 지원.
*   **인코딩:** UTF-8.

### 2.2 에러 리포팅 (Error Reporting Format)
*   형식: `[ERROR_CODE] File "path", line L, col C: <Description>`
*   예: `[FHDL_UNDEFINED_REF] File "main.fhd", line 12, col 5: Node 'N99' is not defined.`

---

## 3. 솔버 로직 및 경계 조건 (Solver & Boundary Cases)

### 3.1 Pass 1: 설계 역산 (Synthesis)
*   **Terminal 없는 Junction:** 하류에 `TERMINAL`이 연결되지 않은 `JUNCTION`은 유량이 0인 것으로 간주(Dead-end pruning).
*   **NPSHa (가용 흡입수두):** $NPSHa = \frac{P_{atm} + P_{gauge} - P_{vap}}{\rho g} \geq NPSHr$ (NPSHr은 펌프 사양에 의함).

### 3.2 Pass 2: 동적 검증 (Verification)
*   **Newton-Raphson:** 전 관망의 에너지 평형점 산출.
*   **체크 밸브:** 역류 감지 시 해당 배관의 저항 계수를 매우 큰 값($10^9$)으로 치환하여 유동 차단 시뮬레이션.

---

## 4. 확장 에러 테이블 (FHDL Error Codes)

| 코드 | 구분 | 설명 |
| :--- | :--- | :--- |
| `FHDL_ID_DUPLICATE` | Syntax | 중복된 ID 정의. |
| `FHDL_UNDEFINED_REF` | Syntax | 정의되지 않은 ID 참조. |
| `FHDL_NEG_DIMENSION` | Syntax | 음수 관경/길이/좌표 등. |
| `FHDL_CYCLIC_SYN` | Logic | Pass 1(역산) 중 루프(Loop) 발견. |
| `FHDL_UNSTABLE_SOL` | Hydraulic | Newton-Raphson 수렴 실패. |
| `FHDL_CAVITATION` | Hydraulic | NPSHa < NPSHr 또는 압력이 증기압 이하. |
| `FHDL_BURST_PIPE` | Safety | 압력이 관의 MaxPressure 초과. |

---

## 5. 결과 리포트 명세 (Output Schema)
*   **Nodes_Report.csv:** `Node_ID, x, y, z, Head(m), Pressure(MPa), Flow_In(L/min), Flow_Out(L/min)`
*   **Pipes_Report.csv:** `Pipe_ID, From, To, Length(m), Diameter(mm), Velocity(m/s), HeadLoss(m), Status(Open/Closed)`