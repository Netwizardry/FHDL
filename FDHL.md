[최종 사양서] Fluid-HDL: 텍스트 기반 유체 관망 설계 및 검증 시스템
1. 시스템 아키텍처 (System Architecture)
Input: .fhd (가칭: Fluid Hardware Description) 확장자의 텍스트 파일.

Compiler: 텍스트 구문을 해석하여 노드와 엣지의 인접 행렬(Adjacency Matrix) 생성.

Solver: 2-Pass 수리 연산 엔진 (EPANET 라이브러리 활용 권장).

Output: 노드별 수리계산서(CSV), 설계 적합성 리포트(DRC).

2. 언어 구조 (Language Definition)
2.1 선언부 (Declarations)
사용할 배관의 재질과 부속류의 특성을 미리 정의합니다.

MATERIAL: 거칠기 계수(C) 및 표준 규격 리스트 정의.

PRESET: 특정 유량/압력을 가진 노즐이나 헤드의 데이터 세트.

2.2 연결부 (Netlist)
좌표를 가진 노드를 생성하고 이들 사이의 관계를 기술합니다.

node: ID (x, y, z, type)

pipe: ID (From_Node, To_Node, Diameter, Material)

valve: ID (Node_A, Node_B, Initial_Status)

2.3 제어부 (Control Sequence)
시간에 따른 시스템의 상태 변화를 정의합니다.

step: 시간 간격 정의.

event: 밸브 개폐 또는 펌프 가동 타이밍 지정.

3. 핵심 로직 및 검증 (Logic & DRC)
3.1 2-Pass 연산 로직
Pass 1 (Back-propagation): 말단 제약 조건을 충족하기 위한 상류의 최소 수두 역산.

Pass 2 (Forward-propagation): 실제 가용한 펌프 성능 인가 시의 유량 분배 및 유향(Flow Direction) 확정.

3.2 설계 규칙 검사 (Design Rule Check)
Pressure Slack: 말단 압력 부족 여부.

Velocity Slack: 관내 유속 과다(3.0m/s 이상) 여부.

Connectivity: 플로팅 노드(연결 안 된 지점) 탐지.

Backflow: 설계 의도와 반대 방향으로 물이 흐르는 구간 탐지.

4. 환경 변수 및 예외 (Environment & Exceptions)
Temperature: 기온에 따른 물성(점도) 보정.

Altitude: 해발 고도에 따른 대기압 보정.

Water Hammer: 밸브 조작 시퀀스에 따른 압력 서지 위험 구간 식별.

5. 기대 효과 (Business Value)
조경 회사: 고가의 소프트웨어 도입 없이도 기술적 근거가 확실한 설계 도서 작성 가능.

설계자: 주먹구구식 엑셀 계산에서 벗어나 밸브 조작 시나리오별 동적 시뮬레이션 가능.

현장 대응: 현장 상황 변경 시 텍스트 수정만으로 재설계 결과 즉시 확인.

[명세서] 유체 관망 설계 및 동적 검증 엔진 (Fluid-HDL v1.0)1. 개요 (Introduction)목적: 3차원 좌표 기반의 노드-엣지 네트워크를 구축하여, 사용자가 정의한 말단 제약 조건으로부터 시스템 제원을 역산(Synthesis)하고, 시간축에 따른 동적 흐름을 검증(Verification)함.대상: 스프링클러 소방 설비, 경관 분수 시스템, 일반 산업용 배관망.핵심 원칙: 비압축성 유체(물) 가정, 정밀 CFD(나비에-스톡스) 대신 공학적 실험식(Hazen-Williams, Darcy-Weisbach) 기반의 네트워크 해석.2. 데이터 모델 (Data Schema)2.1 노드(Node) 객체정적 데이터: ID, Coordinate(x, y, z), Type(Tank, Pump, Junction, Terminal).제약 조건(Terminal 전용): Required_Q (L/min), Required_P (MPa), K-Factor.연산 결과: Head(H), Actual_P, Actual_Q.2.2 엣지(Edge/Pipe) 객체정적 데이터: Start_Node, End_Node, Material_ID, Diameter(D).부속류(Fitting): 해당 엣지에 포함된 엘보, 티, 밸브의 개수 및 K-factor 합계.물성: C-Value (조도), Roughness.2.3 환경 및 전역 변수 (Global Context)Ambient_Temp: 동작 기온 (점도/밀도 자동 보정).Reference_Altitude: 해발 고도 (대기압 및 NPSH 계산).3. 알고리즘 명세 (Algorithm Workflow)[Pass 1] Upstream Synthesis (설계 역산)말단 정의: 모든 Terminal 노드의 최소 압력/유량을 경계 조건으로 설정.재귀 탐색: 하류에서 상류(펌프 방향)로 그래프 탐색.손실 누적: * 배관 마찰 손실($h_f$)과 부속류 국부 손실($h_m$)을 상류 방향으로 합산.$z$ 좌표 차이에 의한 위치 수두 변화 반영.최종 출력: 시스템 전체를 감당하기 위한 펌프의 정격 양정(Head) 및 정격 유량(Flow) 결정.[Pass 2] Downstream Verification (동적 검증)소스 입력: Pass 1에서 결정된 펌프 성능(또는 실제 펌프 커브)을 소스에 인가.유량 분배(Balancing): 각 분기점(Junction)에서 분기 경로의 저항값에 따라 유량을 배분.반복 수렴: 하디-크로스(Hardy Cross) 또는 뉴턴-랩슨 방식을 사용하여 전 관망의 압력 평형점 산출.가변 유향성: 양단 수두 차($\Delta H$)에 따라 엣지별 유동 방향($\pm Q$)을 동적으로 결정.4. 동적 제어 및 시퀀스 (Timing & Dynamics)4.1 밸브 타이밍 (Valve Timing)사용자는 시간축($t$)에 따른 밸브의 개폐 상태(Open/Close)를 정의함.밸브 폐쇄 시 해당 엣지의 저항을 $\infty$로 처리하여 네트워크 토폴로지를 실시간 재구성.4.2 과도 응답 예외 처리Water Hammer: 밸브 급폐쇄 시 발생하는 압력 서지($\Delta P = \rho a \Delta v$)를 계산하여 배관 내압 한계치와 비교.Flow Reversal: 밸브 조작에 의해 동일 엣지 내 흐름 방향이 바뀌는 시점과 유속 변화 모니터링.5. 설계 규칙 검사 (DRC: Design Rule Check)Pressure Violation: 말단 노드의 실제 압력이 사용자가 설정한 최소 압력 미만일 때.Velocity Warning: 배관 내 유속($v$)이 설계 권장치(예: $3.0m/s$)를 초과할 때.Cavitation Risk: 펌프 흡입측 압력이 유체의 증기압($P_{vap}$) 이하로 떨어질 때.Dead-Head Warning: 모든 배출구가 닫힌 상태에서 펌프가 가동될 때.6. 인터페이스 명세 (Conceptual Language)VHDL// Example Code (Conceptual)
System_Setup {
    Temp = 20.0;
    Altitude = 50.0;
}

Component_Library {
    Head_A = Preset(Terminal, Q=80, P=0.1, K=80);
    Pipe_Steel = Material(Steel, C=120);
}

Topology {
    node N1(0,0,10, Source);
    node N2(10,0,5, Junction);
    node N3(20,5,5, Head_A);
    
    pipe P1(N1, N2, 50A, Pipe_Steel);
    pipe P2(N2, N3, 25A, Pipe_Steel);
    valve V1(N2, N3, Gate);
}

Sequence {
    t=0s: V1.Open;
    t=5s: Pump.Start;
}
7. 구현 난이도 및 기대 효과난이도: 중간(Moderate). 선형 대수와 그래프 이론을 활용한 결정론적 모델.효과: * 복잡한 3차원 관망의 수리계산 자동화.밸브 조작 시나리오에 따른 실제 유동성 변화 사전 검증.CAD 없이 텍스트 기반으로 신속한 설계 변경 및 최적화 가능.