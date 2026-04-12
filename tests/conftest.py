"""pytest 全局夹具；在无法加载 PySide6 时为 ``config`` 等模块提供最小 stub。"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def pytest_configure(config):
    try:
        import PySide6.QtCore  # noqa: F401, PLC0415
        import PySide6.QtGui  # noqa: F401, PLC0415
    except ImportError:
        root = MagicMock()
        sys.modules.setdefault("PySide6", root)
        sys.modules.setdefault("PySide6.QtCore", root)
        sys.modules.setdefault("PySide6.QtGui", root)
        sys.modules.setdefault("PySide6.QtWidgets", root)
