import sys
from PySide6.QtWidgets import QApplication
from src.fhdl.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Apply modern dark theme (Optional styling)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
