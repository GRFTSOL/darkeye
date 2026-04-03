"""
controller 包（应用壳层：全局上下文、信号、快捷键、弹窗服务等）

注意：不要做包级重导出，避免 `import controller` 时提前导入 Qt/UI 相关模块，
拖慢启动并产生不必要的副作用。

请在使用处显式导入，例如：
- from controller.app_context import get_theme_manager, set_theme_manager
- from controller.global_signal_bus import global_signals
- from controller.message_service import MessageBoxService
- from controller.shortcut_registry import ShortcutRegistry
"""

__all__ = []
