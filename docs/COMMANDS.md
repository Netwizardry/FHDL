# 명령 콘솔 레퍼런스 (TUI)

> 구현: `core/command.py`. 하단 콘솔 입력줄에서 실행. GUI 메뉴와 동일한 `dsl_editor` 동작을 공유한다.

명령 실행은 DSL 텍스트를 갱신하고(필요 시 자동 재해석) 결과를 로그에 출력한다.

## 명령 목록

| 명령 | 설명 | 예 |
|---|---|---|
| `add <type> <id> [k=v ...]` | 노드/배관 추가 (type: tank·pump·junction·terminal·pipe) | `add tank T1 z=10m x=0 y=0` |
| `add pipe <id> start=A end=B [...]` | 배관 추가(+connect 자동) | `add pipe p1 start=A end=B length=20m` |
| `set <id> k=v [...]` | 노드/배관 속성 수정 | `set T1 required_q=80lpm` |
| `del <id>` (rm, delete) | 노드(연결 포함)/배관 삭제 | `del T1` |
| `link <A> <B> [length=10m]` | A→B 연결(pipe+connect) 추가 | `link src j1 length=8m` |
| `unlink <A> <B>` | A→B 연결 삭제 | `unlink src j1` |
| `constraint k=v ...` | 제약(유속·안전율) 설정 | `constraint velocity_max=2.5m` |
| `ls` (list) | 노드/배관 목록 | `ls` |
| `run` | 해석 실행 | `run` |
| `save` | 프로젝트 저장 | `save` |
| `clear` | 로그 지우기 | `clear` |
| `help` (h, ?) | 명령 목록 | `help` |

## 속성 키

노드: `z`(또는 elevation), `x`, `y`, tank의 `volume`/`level_max`, pump의 `head`/`flow`/`npshr`/`efficiency`, terminal의 `required_q`/`required_p`.
배관: `length`, `diameter`(auto 가능), `material`, `fittings`, `k_factor`.

값은 단위를 포함해 그대로 입력한다(예: `z=10m`, `required_q=80lpm`, `head=30m`).

## 동작 메모

- `set`/`del` 은 `id` 가 배관이면 배관, 아니면 노드로 자동 라우팅.
- DSL 변형 명령은 실행 후 자동 재해석되어 결과/뷰가 갱신된다.
- 명령 히스토리는 입력줄에서 ↑/↓ 로 탐색.
