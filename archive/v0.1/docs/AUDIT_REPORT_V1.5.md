# Fluid-HDL v1.5 Comprehensive Audit Report

## 📋 결함 체크리스트 (Defect Checklist)

### 1. 프로젝트 및 데이터 정합성 (Persistence & Sync)
- [ ] **[CRITICAL] One-way Sync:** `sync_system_to_db`는 존재하나, DB의 변경사항을 `.fhd` 텍스트로 되돌리는 **Serialization** 로직이 전무함. (삭제/수정 기능이 파일에 반영 안 됨)
- [ ] **[MAJOR] Dead Sync Check:** `sync_check` 메서드는 정의만 되어 있을 뿐, UI나 엔진 어디에서도 호출되지 않는 보여주기식 코드임.
- [ ] **[MAJOR] Atomic Save incomplete:** `.tmp` 파일을 쓰긴 하지만, 파일 쓰기 실패 시 예외가 상위로 전파되지 않아 유저는 저장이 성공한 줄 착각하게 됨.

### 2. 컴파일러 및 파서 (Parser/Compiler)
- [ ] **[CRITICAL] Error Fragility:** `params[0:4]` 처럼 슬라이싱을 직접 사용. 파라미터가 3개만 들어와도 앱이 Crash됨. (FHDLParserError로 유도되지 않음)
- [ ] **[MAJOR] Semicolon Illusion:** `rstrip(';')`은 행 끝의 세미콜론만 처리함. 한 줄에 여러 명령어가 있거나 주석 뒤에 세미콜론이 있는 경우 파싱 실패.
- [ ] **[MINOR] Case Sensitivity Gap:** 키워드는 `lower()`로 처리하나, `NodeType` 매핑 시 `ntype.upper()`를 사용하여 정의되지 않은 타입 입력 시 `KeyError` 발생.

### 3. 수리 해석 엔진 (Hydraulic Solver)
- [ ] **[BLOCKER] Minor Loss Abandoned:** `LibraryManager.calculate_angle_k`로 계산된 K값이 `Solver`의 연산 루프에 전달되는 통로가 없음. (피팅 손실이 0으로 계산됨)
- [ ] **[CRITICAL] Loop Death:** `solve_pass1`의 재귀 탐색은 루프(Cycle) 관망을 만날 경우 **Stack Overflow**로 프로그램이 죽음. (방문 처리 로직이 미흡함)
- [ ] **[MAJOR] Fake Hardy-Cross:** 현재 `solve_pass2`는 루프 보정법이 아닌 단순 Nodal Relaxation임. 이는 수리학적 정합성을 보장할 수 없음.
- [ ] **[MAJOR] Density Static:** 온도를 받지만, `rho` 값은 초기 1회만 계산됨. 시뮬레이션 도중 온도 변화가 생겨도 반영되지 않음.

### 4. 사용자 인터페이스 (Qt GUI)
- [ ] **[BLOCKER] Synchronous Execution:** `_on_run_analysis`가 메인 스레드에서 실행됨. 계산 중 UI 조작 불가 및 강제 종료 안 됨.
- [ ] **[MAJOR] Linter Performance:** 매 타이핑마다 전체 텍스트를 Regex로 훑음. 파일이 1000줄을 넘어가면 심각한 입력 지연 발생.
- [ ] **[MINOR] Project Tree Placeholder:** 좌측 익스플로러는 `QTreeView` 객체만 있을 뿐, 실제 파일 목록을 로드하는 모델이 연결되어 있지 않음.

### 5. 안정성 및 예외 처리 (Stability)
- [ ] **[CRITICAL] Global Exception Trap:** `FHDL_SOLVER_CRITICAL`로 모든 에러를 뭉뚱그려 리포트함. 유저는 내부에서 `ZeroDivision`이 났는지 `IndexError`가 났는지 알 길이 없음.
- [ ] **[MAJOR] Zero-Length Guard Bypass:** `0.001m`으로 길이를 보정하지만, 이로 인해 유속($V=Q/A$) 계산 시 분모가 너무 작아져 수치적 폭발 발생 위험.

---

## 🛠️ 긴급 수정 우선순위 (Urgent Action Items)
1.  **순위 1:** 솔버 내 **피팅 손실(K) 적용** 및 **루프 탐지** 로직 수정.
2.  **순위 2:** `ProjectManager`의 **Inverse Sync (Memory -> File)** 구현.
3.  **순위 3:** 파서의 **IndexError 방지** 및 파라미터 검증 강화.
4.  **순위 4:** 분석 로직의 **QThread(비동기)** 이식.
