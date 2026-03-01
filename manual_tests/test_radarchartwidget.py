import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#---------------------------------------------------------------------------------------------------



import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem
from PySide6.QtGui import QBrush, QPen, QColor
from PySide6.QtCore import Qt

from darkeye_ui.components import RadarChartWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QGraphicsView 圆示例")
        self.resize(600, 600)

        categories = ["身高", "罩杯", "胸围", "腰围", "臀围"]
        values = [0.5, 0.8, 0.3, 0.5, 0.6]
        show_values=[160,"F",90,60,90]

        widget = RadarChartWidget()
        widget.resize(600, 600)
        widget.update_chart(categories,values,show_values)
        self.setCentralWidget(widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
