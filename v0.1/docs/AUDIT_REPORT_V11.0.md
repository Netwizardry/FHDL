# Fluid-HDL v11.0 Deep Integrity Audit Report

## 📋 11차 결함 체크리스트 (The Brutal Truth List)

### 1. 물리 로직 및 기만 (Physics Deception)
- [ ] **[BLOCKER] Water Hammer Sequence Error:** Calculates surge AFTER the flow becomes zero. Surge results are always 0.
- [ ] **[CRITICAL] Viscosity Paradox Incomplete:** Using Hazen-Williams means temperature changes never affect friction loss. Spec is misleading.
- [ ] **[MAJOR] Gauge vs Absolute Pressure:** NPSHa uses $P_{atm}$, but result reports may confuse users by showing gauge pressure without clear distinction.

### 2. 데이터 무결성 (Persistence Integrity)
- [ ] **[CRITICAL] Precision Loss:** Serializer truncates floats to 4 decimals, causing permanent data degradation on every save.
- [ ] **[CRITICAL] Nominal Size Priority Bug:** Updating diameter manually is overwritten by old nominal_size during serialization.
- [ ] **[MAJOR] Lost Atomic Save:** ProjectManager reverted to non-atomic file writing. Vulnerable to corruption.

### 3. 아키텍처 및 GUI (Structural Debts)
- [ ] **[MAJOR] Valve ID Desync:** Serialization and Parsing of valve IDs are inconsistent; risks losing user-defined names.
- [ ] **[MINOR] Thread Resource Leak:** Improper QThread shutdown sequence on error or interruption.

## 🛠️ 11차 수정 우선순위 (Mission: Absolute Honesty)
1.  **순위 1:** **수충격 분석 로직 선후관계 교정** (폐쇄 전 유속 보존) 및 **Atomic Save 복구**.
2.  **순위 2:** **직렬화 정밀도 보존** (Raw float 유지) 및 **Nominal Size 동기화 로직** 수정.
3.  **순위 3:** **Darcy-Weisbach 공식 도입 검토** (진정한 온도 보정 달성).
4.  **순위 4:** **QThread 종료 시퀀스 안정화**.
