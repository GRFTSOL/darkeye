"""在系统文件管理器中定位并选中文件（不可用时退化为打开所在目录）。"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def reveal_file_in_os_file_manager(path: Path) -> None:
    resolved = path.resolve()
    path_str = str(resolved)
    try:
        if os.name == "nt":
            subprocess.run(["explorer", "/select,", path_str], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", path_str], check=False)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved.parent)))
    except Exception as e:
        logging.warning("无法在文件管理器中定位文件: %s", e)
