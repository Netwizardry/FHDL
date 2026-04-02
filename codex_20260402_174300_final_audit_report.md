# 최종 감사보고서

최종 판정은 `FAIL`입니다. 현재 명세는 문서 수와 범위는 갖췄지만, 최종 감사 체크리스트 기준의 "구현과 테스트를 실제로 통제하는 규범 문서" 수준에는 아직 도달하지 못했습니다.

확인된 결함은 `Critical 3건`, `Major 6건`, `Minor 4건`입니다. 구현 착수는 가능하더라도, 이 상태로는 요구사항 추적성, 오류 바인딩, 데이터 계약, 출력 provenance를 동일 기준으로 검증할 수 없습니다. 특히 `RTM 파손`, `NPSHa 규범 부재`, `오류 카탈로그 미완성`은 구현팀과 테스트팀이 서로 다른 진실원을 갖게 만드는 결함입니다.

체크리스트 영역 판정:
- `DOC`: `FAIL`
- `RTM`: `FAIL`
- `ERR/RISK`: `FAIL`
- `FSM`: `PARTIAL`
- `DATA`: `FAIL`
- `ARCH`: `FAIL`
- `LOGIC`: `PARTIAL`
- `UI/MVP`: `PARTIAL`
- `NFR/OPS`: `PARTIAL`

## 핵심 Findings

1. `Critical` RTM가 실문서 기준으로 닫혀 있지 않습니다. 결함 내용: 추적 매트릭스가 존재하긴 하지만 다수 항목이 존재하지 않는 설계 ID 또는 테스트 ID를 가리킵니다. `R04`는 `T-NFR-003`을, `R08`은 `T-FLO-001`을, `R09`는 `T-ERR-001`을, `R12`는 `T-UNIT-001`을 가리키지만 테스트 문서에는 해당 케이스가 없습니다. `R05`는 `S-NFR-001`, `R06`은 `S-FOR-003`, `S-CAL-002`를 가리키지만 실제 문서 본문에는 그런 ID가 없습니다. 영향: 요구사항 커버리지, 설계 연결, 테스트 완료 여부를 판정할 수 없습니다. 오해 가능성: 매트릭스가 "완성된 추적성"처럼 보이지만 실제로는 링크가 끊겨 있어 감사자가 거짓 양성을 얻습니다. 보정 권고: `INDEX.md`를 기준 진실원으로 재구성하고, 존재하지 않는 ID를 모두 제거하거나 본문에 규범으로 추가한 뒤 각 요구사항을 `Source -> Design -> Test`로 다시 검증해야 합니다. 근거: `docs/spec/INDEX.md:40-51`, `docs/spec/16_TESTS.md:28-68`.

2. `Critical` v0.1 핵심 범위에 들어간 NPSHa 요구사항이 규범 계산으로 정의돼 있지 않습니다. 결함 내용: 목적/범위와 로드맵, 테스트는 v0.1에서 "기본 NPSHa 계산"을 요구하지만, 솔버와 공식 문서는 NPSHa/NPSHr 계산식, 입력 필드, 판정 기준, 데이터 출처를 정의하지 않습니다. 현재 솔버는 `WRN003`를 "압력이 진공 이하로 떨어질 때" 발생시키는 규칙만 두고 있어, 테스트가 기대하는 `NPSHa < NPSHr` 판정과 일치하지 않습니다. 영향: MVP 필수 요구사항 하나가 구현 가능 수준으로 명세되지 않았습니다. 오해 가능성: 구현자는 진공 압력 경고를 NPSHa 진단으로 오인할 수 있고, 테스트는 다른 기준으로 판정할 수 있습니다. 보정 권고: `NPSHa`, `NPSHr`, 흡입측 손실, 수조 수위, 증기압, 안전여유 기준, 경고 코드 바인딩을 공식 문서와 솔버 문서에 규범으로 추가해야 합니다. 근거: `docs/spec/00_CONCEPT.md:24-37`, `docs/spec/07_ROADMAP.md:18-25`, `docs/spec/16_TESTS.md:34-38`, `docs/spec/11_SOLVER.md:47-51`, `docs/spec/09_FORMULAS.md:41-84`.

3. `Critical` 오류 카탈로그가 여전히 placeholder에 의존합니다. 결함 내용: 오류 문서는 단일 source of truth처럼 선언되지만 `SEM001~003`, `NET001~003`, `CAL001~003`, `WRN001~003`을 "기존 유지"로 남겨 상세 정의를 비워두고 있습니다. 동시에 다른 문서들은 이 코드들을 진단, UI 스타일, 상태 복구의 근거로 사용합니다. 영향: 오류 코드, severity, 사용자 메시지, 조치 가이드가 문서 간에 일관되게 바인딩되지 않습니다. 오해 가능성: 구현자가 모듈별로 임의 메시지와 severity를 만들게 되고, UI와 테스트는 다른 카탈로그를 기준으로 삼게 됩니다. 보정 권고: 오류 카탈로그를 완전한 테이블로 복원하고 각 코드별 `조건`, `severity`, `message`, `action`, `pipeline stage`를 명시해야 합니다. 근거: `docs/spec/15_ERRORS.md:44-76`, `docs/spec/14_GUI.md:33-39`, `docs/spec/05_EXECUTION_FLOW.md:80-88`, `docs/spec/11_SOLVER.md:49-51`.

4. `Major` 데이터 계약과 단위 규약이 문서 간에 충돌합니다. 결함 내용: 공식 문서는 내부 유량 단위를 `m³/s`로 고정하지만, 모델 문서는 `required_q`와 `q_actual`를 `m^3/h`로 적고, 저장 스키마도 `flow_req`를 `m3/h`로 저장합니다. 또한 파이프라인 계약은 `Pipe.diameter`를 필수 실수값으로 고정하지만, 언어와 모델 문서는 `diameter = auto`를 허용합니다. 영향: 같은 값이 계층마다 다른 단위와 타입으로 해석될 수 있어 계산, 직렬화, 리포트가 불일치합니다. 오해 가능성: 정규화 단계에서 단위 변환을 한 번 더 하거나 누락하여 수치 오차를 만들 수 있습니다. 보정 권고: `single internal unit`를 하나로 확정하고, 각 필드의 저장 단위와 표현 단위를 별도 컬럼으로 규범화해야 합니다. `auto/manual/derived`를 허용하는 필드는 인터페이스 계약에서도 nullable 또는 `SizingState`로 명시해야 합니다. 근거: `docs/spec/09_FORMULAS.md:7-13`, `docs/spec/10_MODELS.md:39-46`, `docs/spec/10_MODELS.md:63-67`, `docs/spec/12_PIPELINE.md:53-73`, `docs/spec/20_STORAGE_SCHEMA.md:11-35`.

5. `Major` 내부 모델, 저장 스키마, 리포트 컬럼의 필드 정렬이 깨져 있습니다. 결함 내용: 리포트는 `Node.x, y, z`, `NetworkEdge.h_loss_total`, `NetworkEdge.surge_index`, `Node.sizing_mode`를 요구하지만, 모델 문서에는 `x`, `y`, `h_loss_total`, `surge_index`, `Node.sizing_mode`가 규범 필드로 정의돼 있지 않습니다. 저장 스키마는 `x, y, z`를 가지지만 모델은 `z`만 정의합니다. 테스트는 `Simulation_Summary.json`에 `provenance_map`을 기대하지만 요약 리포트 명세에는 그 필드가 없습니다. 영향: 출력값이 어느 계층에서 생성되고 영속화되는지 역추적할 수 없습니다. 오해 가능성: 구현자가 출력 전용 임시 필드를 도입해 문서 밖의 계약을 만들 수 있습니다. 보정 권고: 출력 컬럼별로 `source layer`, `canonical field`, `storage policy`, `recompute allowed`를 갖는 provenance 표를 별도 추가해야 합니다. 근거: `docs/spec/13_REPORTING.md:18-43`, `docs/spec/10_MODELS.md:57-78`, `docs/spec/20_STORAGE_SCHEMA.md:11-35`, `docs/spec/16_TESTS.md:64-68`.

6. `Major` 아키텍처와 데이터 모델 문서가 아직 미완성 placeholder를 포함합니다. 결함 내용: 아키텍처 문서는 `Snapshot Isolation` 이후와 저장 전략 장을 `...`로 남겨두고 있고, 데이터 모델 문서의 진단 모델 장도 `... (기존 내용 유지)`로 남아 있습니다. 영향: 동시성 경계, 저장 전략, 진단 객체가 규범적으로 닫혀 있지 않습니다. 오해 가능성: 파이프라인, 저장, UI, 오류 처리가 구현자별 추정에 의존하게 됩니다. 보정 권고: placeholder를 금지하고, 비워둔 장을 실제 인터페이스·스레딩·직렬화 규약으로 채워야 합니다. 근거: `docs/spec/04_ARCHITECTURE.md:69-74`, `docs/spec/10_MODELS.md:80-82`.

7. `Major` 상태기계는 존재하지만 폐쇄성과 운영 복구 규칙이 충분히 닫혀 있지 않습니다. 결함 내용: 상태 집합에는 `Saved`가 있으나 전이표에는 `Saved`에서 어디로 갈 수 있는지 정의가 없고, `Aborted` 복구는 `Dirty/Saved`로 복귀한다고만 적어 단일 상태를 보장하지 않습니다. `Any -> CLOSE` 같은 축약 규칙은 금지 전이·우선순위 해석과 충돌할 수 있습니다. 영향: UI, 저장, 중단/복구 로직이 동일한 FSM을 공유하기 어렵습니다. 오해 가능성: 구현마다 `Abort` 후 상태를 다르게 둘 수 있고, 테스트 기대 상태도 갈립니다. 보정 권고: 상태/이벤트/허용 전이/금지 전이/복구 후 상태를 단일 표로 완전 폐쇄해야 합니다. 근거: `docs/spec/05_EXECUTION_FLOW.md:37-76`, `docs/spec/05_EXECUTION_FLOW.md:85-88`.

8. `Major` 보고서와 테스트가 참조하는 식별자 일부가 본문에 없습니다. 결함 내용: 리포트는 `Velocity` 계산 근거로 `FOR-V-001`을 참조하지만 공식 문서에는 해당 ID가 없습니다. RTM도 `S-FOR-003`, `S-CAL-002`, `S-NFR-001` 같은 미정의 ID를 씁니다. 영향: 사람이 보고서를 읽어도 어떤 규범을 따라야 하는지 되짚을 수 없습니다. 오해 가능성: 나중에 같은 식별자를 다른 의미로 재사용할 위험이 큽니다. 보정 권고: 전 문서 ID lint를 돌려 존재하지 않는 ID 참조를 금지해야 합니다. 근거: `docs/spec/13_REPORTING.md:31-36`, `docs/spec/INDEX.md:43-45`.

9. `Major` 외부 장애 대응 규칙이 fail-safe 기준과 일부 충돌합니다. 결함 내용: SQLite 장애 시 메모리 전용 모드로 계속 진행하도록 허용하지만, 어떤 산출물이 비영속 상태인지, 이후 저장/종료/복구 절차가 어떻게 제한되는지 명시돼 있지 않습니다. NetworkX 장애는 fallback "시도"까지만 적혀 있고 성공/실패 기준이 없습니다. 영향: 장애 상황에서 어떤 결과를 신뢰할 수 있는지 판단하기 어렵습니다. 오해 가능성: 운영자가 일시적 메모리 상태 결과를 정상 저장 결과로 오인할 수 있습니다. 보정 권고: 장애별 운영 모드 전이, 기능 축소 범위, 저장 금지 여부, 사용자 경고 수준을 명시해야 합니다. 근거: `docs/spec/12_PIPELINE.md:96-108`, `docs/spec/19_OPERATIONS.md:38-58`, `docs/spec/06_NON_FUNCTIONAL_REQUIREMENTS.md:7-11`.

10. `Minor` 문서 링크와 번호 체계의 신뢰도가 낮습니다. 결함 내용: GUI 문서는 실제 파일명과 다른 `03_UI_UX_REQ.md`를 가리키고, GUI 문서는 `## 3.` 제목이 두 번 나오며, 아키텍처/모델 문서는 번호 체계가 끊기거나 중복됩니다. 영향: 감사와 구현 중 탐색 비용이 올라갑니다. 오해 가능성: 별도 문서가 존재한다고 잘못 이해할 수 있습니다. 보정 권고: 문서 lint 수준에서 링크와 번호를 검증해야 합니다. 근거: `docs/spec/14_GUI.md:7`, `docs/spec/14_GUI.md:29-41`, `docs/spec/10_MODELS.md:69-75`.

11. `Minor` 핵심 규범 문서 개별 revision 정보가 없습니다. 결함 내용: 버전 이력은 `INDEX.md`에만 있고, 개별 규범 문서에는 `status`, `version`, `last revised`, `supersedes`가 없습니다. 영향: 감사 지적이 어느 문서에 반영됐는지 문서 단독으로는 판단하기 어렵습니다. 오해 가능성: 오래된 사본이나 분기 문서를 최신으로 오인할 수 있습니다. 보정 권고: 최소한 핵심 문서 상단에 개별 revision 메타를 추가해야 합니다. 근거: `docs/spec/INDEX.md:55-67`, 개별 규범 문서 상단 전반.

12. `Minor` 보안과 운영 통제는 존재하지만 감사 수준으로는 얕습니다. 결함 내용: RBAC, 체크섬, 로컬 처리 원칙은 있으나 사용자 역할, 권한 부여 경계, 로그 민감정보 마스킹, 감사 보존 기간이 없습니다. 영향: 운영 통제가 필요해지는 시점에 문서가 직접 통제 기능을 제공하지 못합니다. 오해 가능성: "보안 요구사항 반영 완료"로 과대평가될 수 있습니다. 보정 권고: 최소 역할 모델, 민감정보 분류, 로그 마스킹, 보존 정책을 추가해야 합니다. 근거: `docs/spec/06_NON_FUNCTIONAL_REQUIREMENTS.md:34-45`, `docs/spec/19_OPERATIONS.md:18-23`.

13. `Minor` 일부 모호 표현이 남아 있습니다. 결함 내용: `필요 시`, `Fallback 시도`, `가능 구조`, `강제 재생성` 등은 조건이나 허용 범위가 수치/절차로 환원되지 않았습니다. 영향: 예외 상황에서 구현과 운영 판단이 흔들립니다. 오해 가능성: 같은 문장을 서로 다르게 해석할 수 있습니다. 보정 권고: 조건, 트리거, 금지사항, 결과 상태를 명시적 규칙으로 환원해야 합니다. 근거: `docs/spec/02_CALCULATION_REQUIREMENTS.md:44`, `docs/spec/12_PIPELINE.md:100`, `docs/spec/14_GUI.md:54`, `docs/spec/19_OPERATIONS.md:56-58`.

## 체크리스트 축별 요약

| 영역 | 판정 | 핵심 사유 |
| :--- | :--- | :--- |
| `DOC` | `FAIL` | placeholder, 잘못된 링크, 문서별 revision 메타 부재 |
| `RTM` | `FAIL` | 설계/테스트 ID 다수 미존재, 추적성 폐쇄 실패 |
| `ERR/RISK` | `FAIL` | 오류 카탈로그 미완성, NPSHa 규범 부재 |
| `FSM` | `PARTIAL` | 상태 표는 있으나 복구·종결·우선순위 규칙 불완전 |
| `DATA` | `FAIL` | 단위, 필드, storage/report provenance 충돌 |
| `ARCH` | `FAIL` | 핵심 장 placeholder 지속, 동시성/저장 전략 미완료 |
| `LOGIC` | `PARTIAL` | HW는 규범화됐지만 NPSHa와 일부 판정 근거가 비어 있음 |
| `UI/MVP` | `PARTIAL` | 5패널 구조는 정리됐으나 구현/링크/완료기준 보강 필요 |
| `NFR/OPS` | `PARTIAL` | 운영 절차는 있으나 장애 모드와 보안 통제가 얕음 |

## 우선 조치 순서

1. `INDEX.md` RTM를 실재 ID 기준으로 전면 재작성한다.
2. `NPSHa/NPSHr` 계산 및 경고 바인딩을 `09_FORMULAS.md`, `11_SOLVER.md`, `15_ERRORS.md`, `16_TESTS.md`에 추가한다.
3. `15_ERRORS.md`의 placeholder 코드 구간을 완전한 진단 카탈로그로 복원한다.
4. `10_MODELS.md`, `12_PIPELINE.md`, `20_STORAGE_SCHEMA.md`, `13_REPORTING.md`의 canonical field/unit 계약을 단일 표로 정렬한다.
5. `04_ARCHITECTURE.md`와 `10_MODELS.md`의 placeholder 장을 실문장 규범으로 채운다.
6. FSM 복구 후 상태와 저장/중단/종료 경계를 `05_EXECUTION_FLOW.md`에서 폐쇄한다.

## 결론

이번 버전은 이전 대비 문서 수와 구조는 정돈됐고, Hazen-Williams 공식이나 UI 5패널 구조처럼 실제로 보강된 항목도 있습니다. 그러나 최종 감사 체크리스트 기준으로는 여전히 `traceability`, `error binding`, `data contract`, `MVP 핵심 요구사항(NPSHa)`이 닫히지 않았습니다.

따라서 현재 상태는 "정제 진행본"이지 "최종 품질 게이트 통과본"은 아닙니다. 위 `Critical` 3건이 해소되기 전에는 구현 착수 또는 문서 동결(lock) 판단을 보류하는 것이 맞습니다.
