# 10. 계산식 및 판정 규칙 명세

**Status:** Active | **Version:** v4.0 | **Last Revised:** 2026-04-02 | **Supersedes:** v1.5


FHDL 시스템의 모든 수치 해석은 본 문서에 정의된 물리 공식과 엔지니어링 판정 규칙을 따릅니다.

## 1. 단위 및 물리 상수

### 1.1 내부 표준 단위 (SI)
모든 내부 연산은 다음 단위를 기준으로 수행됩니다.
*   **길이/수두:** m
*   **유량:** m³/s
*   **압력:** Pa
*   **유속:** m/s
*   **중력가속도($g$):** 9.80665 m/s² (ISO 표준값)

### 1.2 유체 물성 (Equation of State)
물(Water)의 밀도($\rho$)와 점도($\mu$)는 온도($T$)에 따라 동적으로 계산됩니다.
*   **밀도($\rho$):** $\rho(T) = 999.84 + 0.0678 \cdot T - 0.009 \cdot T^2$ ($kg/m^3$ 근사식)
*   **기본값:** 별도 지정 없을 시 $20^{\circ}C$ 기준 $\rho = 998.2 \, kg/m^3$ 적용.

### 1.2 수두-압력 환산식
$$H = \frac{P}{\rho g}$$
*   $H$: 수두(m), $P$: 압력(Pa)

## 2. 유량 및 유속 계산식

### 2.1 말단 요구조건 환산
1.  **유량 직접 입력:** $Q_{terminal} = Q_{input}$
2.  **분사 높이 입력 (분수):** $H_{terminal} = h_{jet} / C_d$
    *   $C_d$: 공기 저항 계수 (표준 노즐 기본값: 0.98).
3.  **요구 압력 입력 (스프링클러):** $H_{terminal} = \frac{P_{required}}{\rho g}$

### 2.2 구간 및 총 유량 집계
*   **구간 유량:** $Q_{segment} = \sum Q_{downstream}$
*   **시스템 총유량:** $Q_{total} = \sum Q_{all\_terminals}$

### 2.3 유속 및 관경 산정
*   **[FOR-V-001] 유속 계산:** $V = \frac{4Q}{\pi D^2}$
*   **최소 관경 도출:** $D_{min} = \sqrt{\frac{4Q}{\pi V_{max}}}$
    *   시스템은 $D \ge D_{min}$을 만족하는 최소 표준 관경을 라이브러리에서 선정합니다.

## 3. 손실수두 계산식 (Head Loss Formulas)

FHDL 시스템은 설정된 마찰 모델(`friction_model`)에 따라 다음 공식을 사용하여 손실수두를 산정한다.

### 3.1 [FOR-DW-001] 마찰 손실 (Darcy-Weisbach)
가장 정밀한 마찰 손실 계산식으로, 모든 유동 조건에서 기본 적용된다.
$$h_f = f \cdot \frac{L}{D} \cdot \frac{V^2}{2g}$$
*   **[FOR-DW-002] 마찰계수 ($f$):** 
    *   Laminar ($Re < 2000$): $f = 64/Re$
    *   Turbulent ($Re \ge 2000$): Colebrook-White 식을 통한 반복 계산 또는 Swamee-Jain 근사식 적용.

### 3.2 [S-FOR-003] [FOR-HW-001] 마찰 손실 (Hazen-Williams)
소방 설비 및 상수도망 해석 시 관례적으로 사용하며, 물(Water) 전용 공식이다.
$$h_f = 10.67 \cdot L \cdot Q^{1.85} \cdot C^{-1.85} \cdot D^{-4.87}$$
*   **입력 단위 규범:** $L(m)$, $Q(m^3/s)$, $D(m)$.
*   **[FOR-HW-002] C-계수 ($C$):** 배관 재질에 따른 마찰계수 (기본값: Steel=120, PVC=140).
*   **제한:** 물 이외의 유체나 고온 유체에는 적용을 권장하지 않으며, 이 경우 시스템은 경고를 발생시킨다.

### 3.3 [FOR-LOC-001] 국부 손실 (Minor Loss)
$$h_k = K \cdot \frac{V^2}{2g}$$
*   $K$: 피팅/밸브의 저항 계수 (LibraryManager 자동 산출 또는 수동 입력).

## 4. 총 요구양정 및 최불리 경로

### 4.1 [FOR-PTH-001] 경로별 요구양정 ($H_{req, path}$)
$$H_{req, path} = (z_{terminal} - z_{source}) + \sum (h_f + h_k) + H_{terminal}$$
*   $z$: 고도(m), $\sum (h_f + h_k)$: 경로 내 누적 손실수두.

### 4.2 [FOR-PTH-002] 시스템 총 요구양정
$$H_{req, total} = \max(H_{req, path, 1}, H_{req, path, 2}, \dots, H_{req, path, n})$$
*   가장 큰 값을 가지는 경로를 **최불리 경로(Worst-case Path)**로 특정한다.

## 5. 자동 선정 및 판정 규칙

### 5.1 펌프 및 탱크 사양 (Sizing)
*   **권장 펌프 유량:** $Q_{pump} = Q_{total} \times SF_Q$ (기본 $SF_Q$: 1.0)
*   **권장 펌프 양정:** $H_{pump} = H_{req, total} \times SF_H$ (기본 $SF_H$: 1.1)
*   **권장 탱크 용량:** $V_{tank} = Q_{total} \times T_{target} / u$
    *   $T_{target}$: 목표 운전 시간, $u$: 사용률(Usable ratio)

### 5.2 설계 적합성 판정 (Pass/Fail)
*   **유속 검토:** $V_{min} \le V \le V_{max}$ (범위 이탈 시 과속/저속 경고)
*   **압력 검토:** $P_{actual} \ge P_{required}$ (말단 요구압 만족 여부)
*   **펌프 검토:** $H_{manual} \ge H_{pump}$ (수동 지정 펌프의 양정 부족 여부)

## 6. NPSHa 및 캐비테이션 판정 규칙

### 6.1 [FOR-NPSH-001] 유효흡입수두 (NPSHa) 계산
펌프 흡입측에서 유체가 기화되지 않고 유지될 수 있는 여유 수두를 다음과 같이 계산한다.
$$NPSHa = H_{atm} - H_{v} + H_{s} - h_{fs}$$
*   $H_{atm}$: 절대 대기압 수두 (기본 10.33 m).
*   $H_{v}$: 온도에 따른 유체 포화증기압 수두 (m).
*   $H_{s}$: 펌프 중심선 대비 흡입 수조의 수위 (m, 흡입 상향일 경우 양수, 하향일 경우 음수).
*   $h_{fs}$: 흡입 배관 경로에서 발생하는 총 마찰 및 국부 손실 수두 (m).

### 6.2 [FOR-NPSH-002] 캐비테이션 발생 조건 (NPSHa 판정)
*   **판정식:** $NPSHa < NPSHr \times SF_{npsh}$
*   $NPSHr$: 펌프 제조사가 요구하는 필요유효흡입수두 (기본값: 수동 입력).
*   $SF_{npsh}$: 안전 여유율 (Safety Margin, 기본 1.1).
*   해당 조건 발생 시 시스템은 캐비테이션 위험 경고(`WRN003`)를 발생시켜야 한다.

---
[목차로 돌아가기](./INDEX.md)
