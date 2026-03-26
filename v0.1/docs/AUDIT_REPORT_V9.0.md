# Fluid-HDL v9.0 Deep Audit Report (The Last Integrity Check)

## 📋 9차 결함 체크리스트 (The "No Lies" List)

### 1. 수리 연산 및 물리 기만 (Physics & Math)
- [ ] **[BLOCKER] Terminal Physics Fraud:** Treats sprinklers as fixed demands ($Q_{req}$) instead of $Q = K \sqrt{P}$. Simulation results are invalid for variable pressure.
- [ ] **[CRITICAL] NPSH Altitude Ignore:** $P_{atm}$ formula is implemented but never factored into the actual pressure/head solver loops.
- [ ] **[MAJOR] Viscosity Paradox:** Claims temperature compensation but uses Hazen-Williams (viscosity-independent formula).

### 2. 데이터 보존 및 사용자 존중 (User Data Integrity)
- [ ] **[BLOCKER] Comment Killer:** UI-driven saves (CRUD) destroy all manual comments and formatting in the `.fhd` file. (Fatal UX debt)
- [ ] **[MAJOR] Relative Line Error:** Parser reports line numbers relative to the block, not the absolute file line. (Misleading error info)

### 3. 아키텍처 및 성능 (System Stability)
- [ ] **[CRITICAL] Destructive DB Sync:** `update_node` triggers a full DELETE/INSERT of the entire project DB. (Extremely inefficient)
- [ ] **[MAJOR] Fake Async Abort:** Worker waits for `solver.run()` to finish entirely before processing the interruption request.

## 🛠️ 9차 수정 우선순위 (The "Zero-Deception" Mission)
1.  **순위 1:** **터미널 K-Factor 로직 실구현** (가변 유량 시뮬레이션).
2.  **순위 2:** **주석 보존형 Serializer** 연구 또는 CRUD 시 **Partial Update** 전략 도입.
3.  **순위 3:** **절대 줄 번호(Absolute Line Number)** 추적 파서로 개선.
4.  **순위 4:** **NPSHa 고도 보정** 연산 반영.
