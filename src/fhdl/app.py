"""FHDL 애플리케이션 진입점 (콘솔 스크립트 `fhdl`).

시작 시 설계 분야(FHDL 유체 / EHDL 전기 …)를 고른다 — `fhdl.domains`.

    fhdl                  # 기억된 분야로 시작, 없으면 시작 화면
    fhdl --select         # 항상 시작 화면
    fhdl --domain fhdl    # 시작 화면 없이 바로 FHDL
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    from .domains import DOMAINS
    ap = argparse.ArgumentParser(prog="fhdl", description="FHDL/EHDL 설계 도구")
    ap.add_argument("--domain", choices=[d.key for d in DOMAINS], help="시작 화면 없이 바로 열 설계 분야")
    ap.add_argument("--select", action="store_true", help="기억된 선택을 무시하고 시작 화면 표시")
    return ap.parse_args(argv)


def _prepare_library() -> None:
    # 전역 부품 라이브러리 DB 준비 (없으면 시드 생성)
    from .db.library_db import LibraryDB, default_library_path
    LibraryDB(default_library_path()).close()      # 없으면 시드 생성, 있으면 시드 보강·이전 시드 교체


class AppController:
    """시작 화면 ↔ 분야 메인 창 전환. 메인 창을 닫으면 종료, '분야 전환'이면 시작 화면으로."""

    def __init__(self, app, settings):
        self.app = app
        self.settings = settings
        self.window = None
        app.setQuitOnLastWindowClosed(False)    # 전환 중 창이 0개가 되어도 종료하지 않음

    def ask(self, message: str = "") -> bool:
        from .gui.start_dialog import StartDialog
        dlg = StartDialog(self.settings, message=message)
        if dlg.exec() != dlg.DialogCode.Accepted or not dlg.selected:
            return False
        self.open(dlg.selected)
        return True

    def open(self, key: str) -> None:
        from .domains import get_domain, load_window_class
        win = load_window_class(get_domain(key))()
        if hasattr(win, "switch_domain_requested"):
            win.switch_domain_requested.connect(self.switch)
        if hasattr(win, "closed"):
            win.closed.connect(lambda w=win: self.window_closed(w))
        self.window = win
        win.show()

    def switch(self) -> None:
        win = self.window
        if win is not None:
            self.window = None
            if not win.close():              # 미저장 변경 확인에서 취소 → 전환 취소
                self.window = win
                return
            win.deleteLater()
        if not self.ask():
            self.app.quit()

    def window_closed(self, win) -> None:
        """사용자가 메인 창을 닫음 → 종료 (분야 전환으로 닫힌 창은 이미 self.window 가 아님)."""
        if self.window is win:
            self.app.quit()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    _prepare_library()

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from .domains import resolve_start_domain
    from .gui.start_dialog import SETTINGS_KEY

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("FHDL")
    app.setOrganizationName("FHDL Project")
    settings = QSettings("FHDL Project", "FHDL")

    ctl = AppController(app, settings)
    key, message = resolve_start_domain(args.domain, args.select, settings.value(SETTINGS_KEY))
    if key:
        ctl.open(key)
    elif not ctl.ask(message):
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
