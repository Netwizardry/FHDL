"""T-START: 시작 화면 — 설계 분야(FHDL/EHDL) 선택·기억·전환."""
import os
import sys
sys.path.insert(0, "src")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from fhdl.app import AppController, parse_args
from fhdl.domains import DOMAINS, get_domain, load_window_class, resolve_start_domain


def test_domain_registry():
    assert [d.key for d in DOMAINS] == ["fhdl", "ehdl"]
    assert get_domain("FHDL").available and get_domain("ehdl").available
    assert get_domain("nope") is None


@pytest.mark.parametrize("cli, select, remembered, expect", [
    (None, False, None, None),          # 처음 실행 → 시작 화면
    (None, False, "fhdl", "fhdl"),      # 기억된 선택
    (None, True, "fhdl", None),         # --select
    ("fhdl", True, None, "fhdl"),       # --domain 이 우선
    ("ehdl", False, None, "ehdl"),      # EHDL 도 바로 시작
    (None, False, "ehdl", "ehdl"),
    (None, False, "garbage", None),
])
def test_resolve_start_domain(cli, select, remembered, expect):
    key, msg = resolve_start_domain(cli, select, remembered)
    assert key == expect
    assert msg == ""


def test_parse_args():
    assert parse_args([]).domain is None
    assert parse_args(["--domain", "fhdl", "--select"]).select
    with pytest.raises(SystemExit):
        parse_args(["--domain", "xyz"])


@pytest.fixture
def qt(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app, QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)


def test_start_dialog_choice_and_remember(qt):
    from fhdl.gui.start_dialog import SETTINGS_KEY, StartDialog
    _, settings = qt
    dlg = StartDialog(settings)
    assert dlg._cards["fhdl"].isEnabled() and dlg._cards["ehdl"].isEnabled()
    dlg.choose("nope")                              # 없는 분야 → 무시
    assert dlg.selected is None and dlg.result() == 0
    dlg._remember.setChecked(True)
    dlg.choose("fhdl")
    assert dlg.selected == "fhdl" and settings.value(SETTINGS_KEY) == "fhdl"
    dlg2 = StartDialog(settings)                    # 체크 해제로 고르면 기억 삭제
    dlg2.choose("fhdl")
    assert settings.value(SETTINGS_KEY) is None


@pytest.mark.parametrize("key", ["fhdl", "ehdl"])
def test_windows_have_switch_and_closed_signals(qt, key):
    cls = load_window_class(get_domain(key))
    assert hasattr(cls, "switch_domain_requested") and hasattr(cls, "closed")


class _FakeApp:
    def __init__(self):
        self.quit_called = 0

    def setQuitOnLastWindowClosed(self, v):
        self.quit_on_last = v

    def quit(self):
        self.quit_called += 1


def test_controller_switch_and_close(qt, monkeypatch):
    _, settings = qt
    app = _FakeApp()
    ctl = AppController(app, settings)
    assert app.quit_on_last is False
    ctl.open("fhdl")
    first = ctl.window
    # 분야 전환 → 시작 화면에서 다시 FHDL 선택: 종료하지 않고 새 창
    monkeypatch.setattr(ctl, "ask", lambda message="": (ctl.open("fhdl"), True)[1])
    first.switch_domain_requested.emit()
    assert ctl.window is not first and app.quit_called == 0
    # 사용자가 창을 닫으면 종료
    ctl.window.close()
    assert app.quit_called == 1
    # 분야 전환 후 시작 화면을 닫으면(취소) 종료
    ctl.open("fhdl")
    monkeypatch.setattr(ctl, "ask", lambda message="": False)
    ctl.switch()
    assert app.quit_called == 2
