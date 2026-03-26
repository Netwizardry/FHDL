# Fluid-HDL v8.0 Exhaustive Audit Report (The Brutal Integrity)

## 📋 8차 결함 체크리스트 (The "Real" Final Reckoning)

### 1. 수리/물리 로직 (Solver Blocker)
- [ ] **[BLOCKER] Check Valve Logic Flipped:** Solver blocks FORWARD flow and allows REVERSE flow. (Fatal physical error)
- [ ] **[CRITICAL] Water Hammer Over-reporting:** Calculates surge for static valves; ignores operational sequence.
- [ ] **[MAJOR] Solver Interruption Debt:** `solver.run()` loop doesn't check for interruption requests; Stop button is ineffective during heavy math.

### 2. 데이터 및 직렬화 (Integrity Loss)
- [ ] **[CRITICAL] Valve ID Mutilation:** Serializer ignores original valve IDs and auto-generates new ones (`{pipe_id}_v`).
- [ ] **[MAJOR] Rigid Parameter Order:** Material parser crashes if `roughness` and `size_map` positions are swapped.
- [ ] **[MINOR] UI Sort Failure:** Result tables sort numbers as strings (e.g., "10" < "2").

### 3. 성능 및 아키텍처 (Efficiency)
- [ ] **[MAJOR] Quadratic Node Removal:** Deleting nodes takes $O(N)$ per deletion, leading to $O(N^2)$ lag in large projects.
- [ ] **[MINOR] Redundant Pipe Creation:** `valve` command in DSL causes desync if user defines both a pipe and a valve on the same edge without careful matching.

## 🛠️ 8차 수정 우선순위 (Mission: No More Lies)
1.  **순위 1:** **체크 밸브 로직 정상화** (방향성 판별 수정) 및 **Solver 내 중단 체크** 삽입.
2.  **순위 2:** **밸브 ID 보존 직렬화** 및 **테이블 수치형 정렬** 지원.
3.  **순위 3:** **노드 삭제 성능 최적화** (역참조 맵 활용).
4.  **순위 4:** **수충격 분석 조건 정교화** (상태 변화 감지).
