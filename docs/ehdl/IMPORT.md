# DXF 가져오기 (전기 설계도 → EHDL)

> 코드: `src/ehdl/dxf_import.py` · GUI 파일 → **DXF 가져오기**(Ctrl+I) · 콘솔 `import <파일.dxf>` ·
> 명령줄 `python -m ehdl.dxf_import 도면.dxf -o main.ehd`

국내 전기 설계도의 표를 **머리글 글자로** 찾는다(도면 좌표 상수 없음). 모형 공간 글자와 블록 안 글자(세계 좌표, 중첩 4단)를 모은다.

| 인식 대상 | 찾는 방법 | 만드는 것 |
|---|---|---|
| 부하 일람표(분전반 결선도) | 제목 `"이름" PANEL` + 머리글 번호·칭·(VA)·L1~L3·기·P·AF·AT·(KA) | panel · 주차단기(TOTAL LOAD 행) · 회로 차단기 · 부하(kVA·상) |
| CABLE SCHEDULE | 머리글 NO·FROM·TO·FEEDER(또는 CABLE SCHEDULE)·REMARK, 행 기준 = TO 칸 | cable(단면적·병렬 `xNFEEDER`·PE `(E)`/FGV·절연) · 전원 측 차단기 |
| 단선결선도 | `T.R : 3Ø …kVA`·`P.V`·`S.V`·`ACB … AF`·`Set. …%`·`LOAD NAME` 표·`… ONE LINE DIAGRAM (신설/기설)` | source · transformer · ACB(Ir 설정) · switchboard · 피더 |
| 전동기 SCHEDULE | 행 머리글 EQPT. NAME·kW·VA·MCCB P-AF/AT·기동 방식, 위쪽 `FROM:` 위 글자 = 반 이름(`S-1-BA,BB` 펼침) | 전동기 부하(kVA·상·직입기동→dol·예비→off) · 차단기 |
| 주기 | `정격감도전류 15mA` + `0.03초 이하` (표 아래, 없으면 도면 공통) · `접지 방식 : …` | ELB → `sensitivity`·`rcd_type = fast` · 접지 방식은 참고로만 |

표 읽기 규칙:
- 국내 도면 표는 머리글이 칸 가운데, 값은 칸 왼쪽 정렬인 경우가 많다 → 열 i = (머리글 i−1 오른쪽 끝, 머리글 i 오른쪽 끝].
- 병합 셀: 차단기 규격(종류·극수·AF·AT·kA)은 묶음 첫 행에만 적힌다 → 다음 행이 이어받는다.
- 상 칸(L1·L2·L3)에 값이 하나면 그 상의 단상 부하, 셋이면 3상.
- 겹친 다른 도면 글자(예: 'SLOPE')는 알려진 반 이름으로 정리하거나(간선 TO), 값이 없는 열(전동기)을 버린다.
- `%%D` 는 국내 전기 도면 글꼴에서 ㎟ 로 쓰인다(내화 케이블 `(830%%D/120min)` 은 ℃). 특고압(3 kV 이상)·접지선 행은 저압 간선이 아니다.

**지어내지 않는 값** (SPEC 9.2): 역률·배선 길이·변압기 %임피던스·한전 단락용량·계통접지 방식·공사방법·순시 특성은 비워 두고
'확인할 입력'으로 보고한다. 역률이 없는 kVA 부하는 엔진이 보수적 산술합으로 판정한다([ENGINE](ENGINE.md)).

**도면 교차 점검** (경고): 회로 합 ≠ TOTAL LOAD · 단선결선도 피더 AF/AT ≠ CABLE SCHEDULE · 단선결선도 부하 VA ≠ 일람표 TOTAL ·
간선 대상 반의 표 없음 · 반에 전원 측 간선·피더 없음.

GUI 는 가져온 소스를 새(저장 전) 계통으로 열고 회로가 많은 반은 접어 보여 준다. 보고서(요약·경고·참고·확인 질문)는 로그로.
