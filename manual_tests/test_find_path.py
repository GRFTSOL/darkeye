import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#---------------------------------------------------------------------------------------------------

import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QScrollArea,
                               QGridLayout, QLabel)
from PySide6.QtCore import Qt, QSize, QRandomGenerator
from PySide6.QtGui import QColor

from utils.utils import find_video

if __name__ == "__main__":
    # 测试find_video函数
    from pathlib import Path
    test_serial_number = "STSK-004"
    test_video_paths = [Path("D:\\AV"), Path("E:\\bitcomet")]

    find_video(test_serial_number, test_video_paths)


