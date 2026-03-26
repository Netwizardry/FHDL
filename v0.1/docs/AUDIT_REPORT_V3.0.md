# Fluid-HDL v3.0 Deep Audit Report (Final Integrity Check)

## 📋 3차 결함 체크리스트 (The "Hard Truth" List)

### 1. 기능 누락 및 기만 (Implementation Gaps)
- [ ] **[BLOCKER] Water Hammer Fraud:** Joukowsky equation is defined in spec but NOT implemented in code. No surge pressure analysis.
- [ ] **[BLOCKER] Auto-Fitting Dead-end:** `LibraryManager.calculate_angle_k` exists but is never called during parsing or solving.
- [ ] **[MAJOR] Check Valve Ignored:** Solver does not handle flow reversal logic for CHECK type valves.

### 2. 수리 해석 엔진 오류 (Solver Failures)
- [ ] **[CRITICAL] Multi-Source Conflict:** Pass 1 fails to balance energy between multiple pumps/tanks.
- [ ] **[MAJOR] Fixed Tolerance:** Uses absolute `1e-6` instead of relative tolerance, causing convergence failure in large networks.
- [ ] **[MINOR] Gravity Variance:** Ignores local gravity changes or fluid-specific density if fluid is not Water.

### 3. 아키텍처 및 정합성 (Structural Integrity)
- [ ] **[CRITICAL] Logic-GUI Coupling:** `AnalysisWorker` is coupled inside `main_window.py`.
- [ ] **[MAJOR] Overwrite Silence:** Parser overwrites duplicate Material/Pump IDs without warning the user.
- [ ] **[MAJOR] DB Transaction Risk:** `sync_system_to_db` lacks atomic transactions; vulnerable to data corruption on crash.

### 4. 사용자 인터페이스 결여 (UX Debts)
- [ ] **[MAJOR] Large Data Lag:** `ResultViewer` synchronously populates QTableWidget, causing lag for >1000 items.
- [ ] **[MINOR] Missing Units in CSV:** Output CSVs lack explicit unit headers in every column, risking human misinterpretation.

## 🛠️ 3차 수정 우선순위 (The "Real" Final Tasks)
1.  **순위 1:** **자동 피팅(Auto-Fitting) 연동** 및 **체크 밸브 로직** 이식.
2.  **순위 2:** **수충격(Joukowsky) 분석** 구현 (밸브 조작 시 압력 서지 계산).
3.  **순위 3:** **아키텍처 분리** (`AnalysisWorker`를 `core` 모듈로 이동).
4.  **순위 4:** **다중 소스 수두 합산 로직** 정교화.
