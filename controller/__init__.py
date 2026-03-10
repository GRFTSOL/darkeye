"""
controller 包

注意：这里不要做包级重导出（例如 TaskManager/StatusManager/MessageBoxService 等），
避免 `import controller` 时提前导入 Qt/UI 相关模块，拖慢启动并产生不必要的副作用。

请在使用处显式导入，例如：
- from controller.MessageService import MessageBoxService
- from controller.TaskService import TaskManager
- from controller.ShortcutRegistry import ShortcutRegistry
"""

__all__ = []