from PySide6.QtWidgets import QWidget, QHBoxLayout,QLabel, QPushButton,QMainWindow,QVBoxLayout,QListWidget
from PySide6.QtCore import Slot, Qt,QObject,QTimer,QPoint
from ui.basic import IconPushButton
from datetime import datetime
from controller.GlobalSignalBus import global_signals

class Task():
    '''要被实例化成一个个任务'''
    def __init__(self,name,starttime,status):
        self.name=name
        self.starttime=starttime
        self.endtime=None
        self.spendtime=None
        self.status=status

class TaskManager(QObject):
    """后台任务管理器
    当有后台任务的时后在这里显示，完成后有完成的通知，可以清楚消息
    负责创建显示任务
    当任务数大于1时控制组件
    """
    _instance = None  # 类变量，保存唯一实例

    @classmethod
    def instance(cls, taskwindow=None, notification=None):
        if cls._instance is None:
            if taskwindow is None or notification is None:
                raise ValueError("首次创建必须传入 taskwindow 和 notification")
            cls._instance = super().__new__(cls)
            super(TaskManager, cls._instance).__init__()
            cls._instance.task_window = taskwindow
            cls._instance.status_notifier = notification
            cls._instance.tasks = []
        return cls._instance

    def __init__(self):
        # 防止直接实例化
        if TaskManager._instance is not None and TaskManager._instance is not self:
            raise RuntimeError("请使用 TaskManager.instance() 获取实例")
        super().__init__()

    def add_task(self, title: str, message: str = "正在处理..."):
        '''当有任务时使用'''
        now = datetime.now()
        task = Task(
            name=title,
            starttime=now.strftime("%H:%M:%S"),
            status="running"
        )
        global_signals.status_msg_changed.emit(title+message)

        self.tasks.append(task)
        # 更新任务列表显示
        item_text = f"● {title}  [{task.starttime}]  {message}"
        item = self.task_window.task_list.addItem(item_text)
        list_item = self.task_window.task_list.item(self.task_window.task_list.count() - 1)
        list_item.setData(Qt.UserRole, task)  # 绑定 task 对象，便于后续查找

        self._update_status_counter()

        return task

    def complete_task(self, task:Task,message: str = "完成"):
        """任务完成使用"""
        if task not in self.tasks:
            return

        task.status = "success"
        task.endtime = datetime.now()
        task.spendtime = str(task.endtime - datetime.strptime(
            f"{task.endtime.date()} {task.starttime}", "%Y-%m-%d %H:%M:%S"))
        
        global_signals.status_msg_changed.emit(task.name+message)
        self._refresh_task_item(task, f"✓ {task.name}  [{task.starttime} → {task.endtime.strftime('%H:%M:%S')}]  {message}")

    def error_task(self, task:Task,message: str = "失败"):
        '''任务失败时使用'''
        if task not in self.tasks:
            return

        task.status = "error"
        task.endtime = datetime.now()
        global_signals.status_msg_changed.emit(task.name+message)
        self._refresh_task_item(task, f"✗ {task.name}  [{task.starttime}]  {message}", error=True)

    def _refresh_task_item(self, task: Task, text: str, error: bool = False):
        """刷新列表中对应任务项的显示"""
        for i in range(self.task_window.task_list.count()):
            item = self.task_window.task_list.item(i)
            if item.data(Qt.UserRole) == task:
                item.setText(text)
                if error:
                    item.setForeground(Qt.red)
                else:
                    item.setForeground(Qt.green)
                break

        # 更新状态栏（失败也算未读）
        self._update_status_counter()

    def _update_status_counter(self):
        """更新状态栏未读计数（进行中 + 失败的任务算未读）"""
        unread_count = sum(1 for t in self.tasks if t.status in ("running", "error"))
        if unread_count > 0:
            self.status_notifier.count_label.setText(f"({unread_count})")
            #self.status_notifier.count_label.show()
        else:
            self.status_notifier.count_label.setText("(0)")
            #self.status_notifier.count_label.hide()
