# Fluid-HDL v4.0 Deep Audit Report (Stability & Integrity)

## 📋 4차 결함 체크리스트 (The "Real" Final Truth)

### 1. 수리 해석 엔진 (Physics & Math)
- [ ] **[CRITICAL] Multi-source Demand Doubling:** Pass 1 over-calculates flow in parallel source paths.
- [ ] **[MAJOR] Jacobian Instability:** Setting $K=10^9$ for check valves ruins matrix convergence.
- [ ] **[MAJOR] Silent Fallback:** Parser uses default 50.0mm when size ID is missing, instead of raising an error. (Safety risk)

### 2. 데이터 정합성 (Data & Persistence)
- [ ] **[BLOCKER] Serializer Self-Destruction:** Serialized raw numbers cause "Size Not Found" on re-load if nominal_size is missing.
- [ ] **[CRITICAL] Destructive CRUD:** UI actions overwrite unsaved editor buffers without warning. (Data loss risk)
- [ ] **[MAJOR] DB Atomicity:** No SQLite transactions during sync; vulnerable to corruption.

### 3. 사용자 인터페이스 (GUI & UX)
- [ ] **[MAJOR] Linter Lag:** Main-thread regex linting on every keypress blocks UI for large files.
- [ ] **[MAJOR] Ghost Highlights:** Error line highlighting persists after the error is fixed.
- [ ] **[MINOR] Missing Unit Headers:** ResultViewer tables don't clearly state units (m vs mm vs MPa) in headers.

## 🛠️ 4차 수정 우선순위 (The "Zero-Defect" Mission)
1.  **순위 1:** **Serializer 고도화 및 Silent Fallback 제거** (데이터 무결성 최우선).
2.  **순위 2:** **Destructive Save 방지** (에디터 Dirty-flag 체크 로직).
3.  **순위 3:** **수치 해석 안정화** (Check valve 및 Low-flow 가드 정교화).
4.  **순위 4:** **UI 성능 최적화** (Linter Debounce 도입).
