# FHDL 문서

> 본 문서 모음은 **현재 소스코드(`src/fhdl/`) 기준**으로 작성되었다.
> 구현 이전의 명세·감사 문서는 `archive/`(spec_legacy, design_legacy, spec_audit_legacy)에 보관.

## 목차

| 문서 | 내용 |
|---|---|
| [ARCHITECTURE](ARCHITECTURE.md) | 모듈 계층(core/db/gui), 파이프라인, 핵심 원칙 |
| [LANGUAGE](LANGUAGE.md) | FHDL DSL 레퍼런스 (블록·속성·재질·부속·단위·datum) |
| [SOLVER](SOLVER.md) | 2-Pass 수리 해석, 마찰/국부손실, 펌프, NPSHa |
| [DATA_MODEL](DATA_MODEL.md) | 엔티티·결과 모델, DB 스키마, 저장/로드/복원 |
| [GUI](GUI.md) | 5패널·콘솔·그래프 편집·단축키 |
| [DRAWING](DRAWING.md) | 도면 생성(ISO 아이소메트릭·평면·정면·P&ID)·ISO 기호·BOM·내보내기(PDF·DXF·SVG·STEP) |
| [COMMANDS](COMMANDS.md) | 하단 명령 콘솔(TUI) 레퍼런스 |
| [DIAGNOSTICS](DIAGNOSTICS.md) | 진단 코드(SYN/SEM/NET/CAL/WRN) |
| **EHDL** (전기) | [SPEC](ehdl/SPEC_v0.1.md) · [검토·결정](ehdl/REVIEW_v0.1.md) · [언어](ehdl/LANGUAGE.md) · [계산·판정·진단](ehdl/ENGINE.md) · [화면·명령·산출물](ehdl/GUI.md) · [기준 원문 DB](ehdl/KB.md) · [DXF 가져오기](ehdl/IMPORT.md) |
| [ROADMAP](ROADMAP.md) | 차후 대형 작업(Hardy-Cross 루프망, 수충격 MOC) |

설치·실행·빠른 시작은 루트 [README](../README.md) 참조.
