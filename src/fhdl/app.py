"""FHDL 애플리케이션 진입점 (콘솔 스크립트 `fhdl`)."""
from __future__ import annotations

import os
import sys


def main() -> int:
    # 전역 부품 라이브러리 DB 준비 (없으면 시드 생성)
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    lib_path = os.path.join(data_dir, "library.db")
    if not os.path.exists(lib_path):
        from .db.library_db import LibraryDB
        LibraryDB(lib_path).close()

    from PySide6.QtWidgets import QApplication
    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("FHDL")
    app.setOrganizationName("FHDL Project")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
