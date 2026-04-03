# 应用级单例/上下文，供 main 设置、各页面获取，避免循环导入
# 使用方式：在 main.py 中 set_theme_manager(theme_mgr)；在任意页面
#   from controller.app_context import get_theme_manager

_theme_manager = None


def get_theme_manager():
    """获取全局 ThemeManager，由 main.py 在启动时设置。用于 darkeye_ui 组件（Button、ToggleSwitch 等）的 theme_manager 参数。"""
    return _theme_manager


def set_theme_manager(mgr) -> None:
    global _theme_manager
    _theme_manager = mgr
