# Fluid-HDL v5.0 Ultimate Audit Report (The Last Check)

## 📋 5차 결함 체크리스트 (Final Defect List)

### 1. 코드 기만 및 정합성 (Code Integrity)
- [ ] **[BLOCKER] Check Valve Fake Fix:** Code still uses $K=1e9$ instead of the reported "Soft Block" logic. (Verification fraud)
- [ ] **[CRITICAL] No Exit Guard:** MainWindow closes without checking `is_dirty`. Data loss on program exit.
- [ ] **[MAJOR] Overwrite Silence:** Duplicate IDs for nodes/materials are silently overwritten instead of raising errors.

### 2. 수리 연산 오류 (Solver & Physics)
- [ ] **[CRITICAL] Parallel Flow Error:** Pass 1 over-calculates flow in parallel pump paths, leading to massive over-design.
- [ ] **[MAJOR] Head Floor Constraint:** `max(..., node.z)` in solver prevents negative gauge pressure (Siphon/Vacuum) analysis.
- [ ] **[MINOR] Redundant Density Calc:** `ReportGenerator` and `Solver` both calculate `rho` independently; should be passed via `FluidSystem`.

### 3. 컴파일러 및 데이터 (Parser & Data)
- [ ] **[MAJOR] Brittle Material Regex:** Material definition fails if optional parameters (wave_velocity) are missing.
- [ ] **[MINOR] Missing CSV Units:** Output CSV headers lack explicit unit notations (e.g., "Pressure (MPa)").

## 🛠️ 5차 수정 우선순위 (The "True" Finalization)
1.  **순위 1:** **진짜 Soft Block** 및 **병렬 유량 합산 로직** 수정.
2.  **순위 2:** **MainWindow 종료 가드** 및 **중복 ID 검증** 추가.
3.  **순위 3:** **유연한 재질 파서** 구현 (Optional params 대응).
4.  **순위 4:** **CSV 리포트 단위 명시** 및 **밀도 참조 통일**.
