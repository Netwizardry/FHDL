# Fluid-HDL v6.0 Ultimate Audit Report (Exhaustive & Destructive)

## 📋 6차 결함 체크리스트 (The Final Reckoning)

### 1. 수리 연산 및 물리 (Hydraulic & Physics)
- [ ] **[BLOCKER] Mesh Demand Loop:** `_get_downstream_demand_sum` causes infinite recursion or double-counting in looped networks. (Math failure)
- [ ] **[CRITICAL] Viscosity Neglect:** Hazen-Williams formula ignores viscosity changes at different temperatures. (Incomplete temp-compensation)
- [ ] **[MAJOR] Negative Head Extrapolation:** Pump curve extrapolation can return negative head at high flow rates. (Physics violation)

### 2. 명세 및 단위계 (Spec & Units)
- [ ] **[BLOCKER] Imperial System Fraud:** `Units = IMPERIAL` is parsed but ignored by Solver/Library logic. (Lying spec)
- [ ] **[MAJOR] Hardcoded Constants:** Physical constants like `g=9.80665` are hardcoded; fails if simulation is for non-Earth gravity or different precision.

### 3. 데이터 무결성 (Integrity & References)
- [ ] **[CRITICAL] Graph-Model Desync:** Deleting a node removes it from `system.pipes` but leaves orphan edges in `system.graph`. (Reference error)
- [ ] **[MAJOR] Duplicate ID Context:** Error message doesn't show the first definition line of the duplicate ID.

### 4. 리포트 및 성능 (Output & Performance)
- [ ] **[MAJOR] Precision Erasure:** 4-decimal rounding in CSV loses data for high-precision micro-flow analysis.
- [ ] **[MINOR] Transactionless DB Sync:** Large network sync to SQLite still lacks explicit BEGIN/COMMIT blocks.

## 🛠️ 6차 수정 우선순위
1.  **순위 1:** **루프 관망 유량 합산 로직 폐기** 및 **Tree-based Synthesis** 강제 (또는 루프 분담 비율 도입).
2.  **순위 2:** **임페리얼 단위계 실구현** (UnitConverter 내 상수 스위칭).
3.  **순위 3:** **그래프-모델 동기화 무결성** 확보 (`delete_node` 시 graph edge 동시 삭제).
4.  **순위 4:** **펌프 커브 하한 가드** 및 **리포트 지수 표기법** 적용.
