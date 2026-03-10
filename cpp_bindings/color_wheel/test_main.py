import sys

from PySide6.QtWidgets import QApplication
import PyColorWheel
from PyColorWheel import ColorWheelSimple

if __name__ == "__main__":
    app = QApplication()
    w :ColorWheelSimple = ColorWheelSimple()
    w.show()
    w.setInitialColor("#FF0000")
    sys.exit(app.exec())