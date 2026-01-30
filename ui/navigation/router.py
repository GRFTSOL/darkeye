from PySide6.QtWidgets import QStackedWidget, QWidget
from PySide6.QtCore import QObject
import logging
from typing import Dict, Any, Optional
from ui.widgets.Sidebar import Sidebar

class Router(QObject):
    _instance = None

    def __init__(self, stack_widget: QStackedWidget, sidebar:Sidebar):
        super().__init__()
        if Router._instance is not None:
            raise Exception("Router is a singleton!")
        Router._instance = self
        
        self.stack = stack_widget
        self.sidebar = sidebar
        self.routes: Dict[str, Any] = {}
        
        # 历史记录栈和指针
        self.history_stack = []
        self.current_index = -1
        
    @classmethod
    def instance(cls):
        if cls._instance is None:
            raise Exception("Router has not been initialized yet!")
        return cls._instance

    def register(self, route_name: str, page_widget: QWidget, sidebar_menu_id: Optional[str] = None):
        self.routes[route_name] = {
            "page": page_widget,
            "menu_id": sidebar_menu_id
        }

    def push(self, route_name: str, **kwargs):
        """
        跳转到指定路由，并记录到历史栈
        """
        if route_name not in self.routes:
            logging.error(f"Router: Route not found '{route_name}'")
            return

        # 如果是当前页面，且不是带参数的刷新，可以考虑是否记录
        # 这里简化处理：只要push就记录，除非完全一样且在栈顶（可选）
        
        # 截断历史栈：如果当前指针不在末尾，丢弃后面的记录
        if self.current_index < len(self.history_stack) - 1:
            self.history_stack = self.history_stack[:self.current_index + 1]
            
        # 避免重复入栈（可选）：如果新页面和当前栈顶页面相同，则不重复记录
        # 但考虑到参数可能不同，这里为了简单（仅支持无参回退），如果只是route_name相同，
        # 我们视情况而定。方案里说"不要带参数那种"，所以如果route_name一样，可以不入栈。
        if not self.history_stack or self.history_stack[-1] != route_name:
            self.history_stack.append(route_name)
            self.current_index += 1
        
        # 执行实际跳转
        self._switch_to_view(route_name, **kwargs)

    def back(self):
        """后退到上一个页面"""
        if self.current_index > 0:
            self.current_index -= 1
            route_name = self.history_stack[self.current_index]
            logging.info(f"Router: Back to '{route_name}'")
            # 回退时不带参数，恢复页面原有状态
            self._switch_to_view(route_name)

    def forward(self):
        """前进到下一个页面"""
        if self.current_index < len(self.history_stack) - 1:
            self.current_index += 1
            route_name = self.history_stack[self.current_index]
            logging.info(f"Router: Forward to '{route_name}'")
            self._switch_to_view(route_name)

    def _switch_to_view(self, route_name: str, **kwargs):
        """
        执行实际的视图切换逻辑（不操作历史栈）
        """
        if route_name not in self.routes:
            return

        route_info = self.routes[route_name]
        page = route_info["page"]
        menu_id = route_info["menu_id"]

        logging.info(f"Router: Switching view to '{route_name}' with params {kwargs}")

        self.stack.setCurrentWidget(page)#切换到页面
        if route_name == "setting":
            self.sidebar.clear_selection()
            # setting页面不需要return，可能后续还有逻辑？
            # 原代码有return，为了保持一致性，检查原逻辑
            # 原逻辑 setting return了，但这里我们要在方法底部统一处理
            # 不过setting比较特殊，它清除了sidebar选择。
            # 我们继续执行，看看有没有副作用。
            # 下面的 if self.sidebar and menu_id: 会处理侧边栏高亮
            # setting的menu_id是""，所以不会触发select
            pass

        if self.sidebar and menu_id:
            self.sidebar.select(menu_id)#高亮选中的侧边栏

        if route_name == "mutiwork":
            self._handle_work_route(page, **kwargs)
            return

        if route_name == "work_edit":
            self._handle_work_edit_route(page, **kwargs)
            return

        if "actress_id" in kwargs and hasattr(page, "update"):
            try:
                page.update(kwargs["actress_id"])
            except Exception as e:
                logging.error(f"Router: Failed to update page {route_name}: {e}")
                
        elif "work_id" in kwargs and hasattr(page, "update"):
            try:
                page.update(kwargs["work_id"])
            except Exception as e:
                logging.error(f"Router: Failed to update page {route_name}: {e}")

        elif "actor_id" in kwargs and hasattr(page, "update"):
            try:
                page.update(kwargs["actor_id"])
            except Exception as e:
                logging.error(f"Router: Failed to update page {route_name}: {e}")

    def _handle_work_route(self, page: QWidget, **kwargs):
        actor_id = kwargs.get("actor_id")
        tag_id=kwargs.get("tag_id")
        serial_number=kwargs.get("serial_number")
        if actor_id is not None and hasattr(page, "actor_input"):
            from core.database.query import get_actor_allname
            namelist = get_actor_allname(actor_id)
            if namelist:
                name = namelist[0].get("cn")
                page.actor_input.setText(name)
        if tag_id is not None and hasattr(page, "tagselector"):
            page.tagselector.load_with_ids([tag_id])
        if serial_number is not None and hasattr(page, "serial_number_input"):
            page.serial_number_input.setText(serial_number)

    def _handle_work_edit_route(self, page: QWidget, **kwargs):
        serial_number = kwargs.get("serial_number")
        if serial_number is None:
            return
        if hasattr(page, "tab_widget") and hasattr(page, "worktab"):
            page.tab_widget.setCurrentWidget(page.worktab)
            worktab = page.worktab
            if hasattr(worktab, "input_serial_number"):
                worktab.viewmodel.set_serial_number(serial_number)
                worktab.viewmodel._load_from_db()

                

     
