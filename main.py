"""FHDL 애플리케이션 진입점."""
import os
import sys
from pathlib import Path

# 소스 루트를 sys.path에 추가
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT / "src"))

# 라이브러리 DB 초기화
_DATA_DIR = _ROOT / "data"
_DATA_DIR.mkdir(exist_ok=True)
_LIB_DB = str(_DATA_DIR / "library.db")
if not (_DATA_DIR / "library.db").exists():
    from fhdl.db.library_db import LibraryDB
    LibraryDB(_LIB_DB).close()


def main():
    from PySide6.QtWidgets import QApplication
    from fhdl.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("FHDL")
    app.setOrganizationName("FHDL Project")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
