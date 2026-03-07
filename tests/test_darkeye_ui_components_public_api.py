import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import darkeye_ui.components as components


def test_darkeye_ui_components_all_symbols_exist():
    missing = [name for name in components.__all__ if not hasattr(components, name)]
    assert missing == [], f"Missing symbols in darkeye_ui.components.__all__: {missing}"
