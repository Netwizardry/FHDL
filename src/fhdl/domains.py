"""설계 분야(도메인) 레지스트리 — 시작 화면에서 고르는 FHDL·EHDL 등.

GUI 비의존. 분야를 추가하려면 DOMAINS 에 한 줄 넣고 `window` 에 메인 창 클래스
("모듈:클래스")를 지정한 뒤 available=True 로 바꾸면 시작 화면에 활성으로 나타난다.
메인 창 클래스는 `switch_domain_requested` 시그널(분야 전환)을 가지면 전환 메뉴와 연결된다.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Domain:
    key: str             # 설정·명령줄에 쓰는 ID (예: "fhdl")
    name: str            # 표시 이름 (예: "FHDL")
    title: str           # 한 줄 제목
    description: str     # 시작 화면 설명
    icon: str            # resources/icons/ 아래 파일명
    available: bool      # 구현 여부 (False = "준비 중", 선택 불가)
    window: str = ""     # 메인 창 클래스 "모듈:클래스"


DOMAINS: Tuple[Domain, ...] = (
    Domain("fhdl", "FHDL", "유체 설비 설계 (Fluid HDL)",
           "배관망을 DSL 로 기술해 정상상태 수리해석·관경 선정·펌프/탱크 사양·"
           "NPSH 진단을 자동화하고 ISO 배관 도면을 생성합니다.",
           "app.svg", True, "fhdl.gui.main_window:MainWindow"),
    Domain("ehdl", "EHDL", "전기 설비 설계 (Electrical HDL)",
           "전력계통을 노드로 구성해 부하·전류·전압강하·보호 협조를 계산하고, 설계 규격의 적합성과 "
           "'왜 이 규격인가'의 근거(KEC 원문 조항)를 보여 줍니다.",
           "ehdl.svg", True, "ehdl.gui.main_window:EHDLMainWindow"),
)


def get_domain(key: Optional[str]) -> Optional[Domain]:
    k = (key or "").strip().lower()
    return next((d for d in DOMAINS if d.key == k), None)


def resolve_start_domain(cli_domain: Optional[str], force_select: bool,
                         remembered: Optional[str]) -> Tuple[Optional[str], str]:
    """시작할 분야 결정 → (분야 키 또는 None=시작 화면 표시, 안내 메시지).

    우선순위: 명령줄 --domain > --select(항상 시작 화면) > 기억된 선택 > 시작 화면.
    없는/준비 중인 분야는 시작 화면으로 돌린다.
    """
    if cli_domain:
        d = get_domain(cli_domain)
        if d is None:
            return None, f"알 수 없는 분야 '{cli_domain}' — 시작 화면에서 선택하세요."
        if not d.available:
            return None, f"{d.name} 은(는) 아직 준비 중입니다 — 시작 화면에서 선택하세요."
        return d.key, ""
    if force_select:
        return None, ""
    d = get_domain(remembered)
    if d is not None and d.available:
        return d.key, ""
    return None, ""


def load_window_class(domain: Domain):
    """`window` 의 "모듈:클래스" 를 가져온다 (GUI 모듈은 이때 처음 import)."""
    module, _, cls = domain.window.partition(":")
    return getattr(importlib.import_module(module), cls)
