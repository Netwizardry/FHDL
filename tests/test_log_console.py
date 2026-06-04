"""T-LOG: 작업 로그 콘솔."""
import sys
import os
sys.path.insert(0, "src")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
    from fhdl.gui.log_console import LogConsole
    _HAS_QT = True
except Exception:
    _HAS_QT = False

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PySide6 unavailable")

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])
    return _app


def test_log_levels_and_content():
    _ensure_app()
    c = LogConsole()
    c.info("정보 메시지")
    c.warning("경고 메시지")
    c.error("에러 메시지")
    c.ok("성공")
    text = c._view.toPlainText()
    assert "정보 메시지" in text
    assert "INFO" in text and "WARNING" in text and "ERROR" in text
    # 타임스탬프 형식 [HH:MM:SS]
    assert "[" in text and "]" in text


def test_clear():
    _ensure_app()
    c = LogConsole()
    c.info("x")
    assert c._view.toPlainText().strip() != ""
    c.clear()
    assert c._view.toPlainText().strip() == ""


def test_html_escaped():
    _ensure_app()
    c = LogConsole()
    c.info("a < b > c & d")
    assert "a < b > c & d" in c._view.toPlainText()
