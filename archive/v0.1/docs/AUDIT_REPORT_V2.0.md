# Fluid-HDL v2.0 Deep Audit Report (2nd Round)

## 📋 2차 결함 체크리스트 (Critical Defect List)

### 1. 물리/수리 로직 (Physics & Solver)
- [ ] **[BLOCKER] Pump Curve Ignored:** Solver ignores `Node.curve`. PUMP acts as a fixed head source. (Physical invalidity)
- [ ] **[MAJOR] Density Mismatch:** `ReportGenerator` uses `1000` while `Solver` uses temperature-dependent `rho`. (Data inconsistency)
- [ ] **[MAJOR] Jacobian Singularity:** Derivative `dq_dh` explodes at low pressure drops. (Numerical instability)
- [ ] **[MINOR] Elevation Reference:** Atmospheric pressure is fixed at the start; ignores per-node Z-level effects on $P_{atm}$.

### 2. 데이터 및 직렬화 (Data & Serialization)
- [ ] **[CRITICAL] Nominal Size Loss:** Serializer writes actual diameters instead of nominal size IDs (50A, etc.). (Information degradation)
- [ ] **[MAJOR] Partial Syntax Failure:** Comments inside command parentheses `node N1(0,0,0 /* comment */)` cause parser crash.
- [ ] **[MAJOR] CRUD Overwrite Risk:** UI-driven modifications (delete_node) overwrite un-saved editor content. (UX/Data loss risk)

### 3. GUI 및 시스템 (GUI & Stability)
- [ ] **[MAJOR] Non-cancellable Thread:** No way to stop the analysis thread if it hangs.
- [ ] **[MAJOR] Error Navigation Gap:** No auto-scroll or highlighting for error lines in the editor.
- [ ] **[MINOR] Linter lag:** Regex-based validation is too heavy for large files on the main thread.

## 🛠️ 2차 수정 우선순위 (Urgent Fixes)
1.  **순위 1:** **Serializer/Parser 보강** (Nominal Size 유지 및 괄호 내 주석 허용).
2.  **순위 2:** **펌프 커브 로직 삽입** (Pass 2에서 펌프 성능 반영).
3.  **순위 3:** **밀도 정합성 통일** (ReportGenerator와 Solver 간의 rho 공유).
4.  **순위 4:** **수치 가드 보강** (Derivations at low flow).
