# Fluid-HDL v17.0 Engineering & Architectural Audit Report

## 📋 17차 결함 체크리스트 (The Next Leap)

### 1. 물리 시뮬레이션 고도화 (Advanced Simulation)
- [ ] **[BLOCKER] Inverse Flow NPSH Error:** PUMP가 역류 상황(상태 평형 중 일시적 역류 포함)일 때 NPSHa가 비정상적으로 계산되거나 물리적 불연속성이 발생하는 문제.
- [ ] **[MAJOR] Pump Efficiency Map:** 유량에 따른 펌프 효율(Efficiency %) 반영 및 소요 동력(kW) 산출 로직 누락.

### 2. 예외 처리 및 안정성 (Robustness)
- [ ] **[CRITICAL] Unconnected Network Crash:** Topology가 두 개 이상의 독립된(Islands) 네트워크로 구성된 경우 솔버 수렴 실패 및 매트릭스 특이점 오류 대응.
- [ ] **[MAJOR] Convergence Oscillations:** 특정 밸브 폐쇄 루프가 포함된 복잡한 Mesh망에서 수렴 속도가 기하급수적으로 느려지는 현상 보정 (Damping Factor 자동 조절 도입).

### 3. 보고서 및 결과물 (Outputs)
- [ ] **[MAJOR] Unit Accuracy (Metric/Imperial):** `ReportGenerator`에서 유저가 설정한 Units(IMPERIAL 등)이 결과 CSV에 반영되지 않고 SI 단위로만 고정 출력되는 문제.

## 🛠️ 17차 수정 로드맵
1. **순위 1:** **다중 네트워크(Island) 지원** 및 그래프 분할 분석 로직 추가.
2. **순위 2:** **단위 시스템(Units) 결과 반영** 및 `ReportGenerator` 정밀화.
3. **순위 3:** **역류(Backflow) 상황의 NPSHa 안전 수치 가드** 구현.
4. **순위 4:** **펌프 효율 및 동력(kW)** 연산 모듈 추가.
