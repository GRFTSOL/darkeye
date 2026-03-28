import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import darkeye_ui


def test_darkeye_ui_all_symbols_exist():
    missing = [name for name in darkeye_ui.__all__ if not hasattr(darkeye_ui, name)]
    assert missing == [], f"Missing symbols in darkeye_ui.__all__: {missing}"
