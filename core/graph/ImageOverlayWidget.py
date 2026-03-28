import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Qt, QRectF, QPointF, QEvent
from PySide6.QtGui import QPainter, QImage
from PySide6.QtWidgets import QWidget

from core.graph.async_image_loader import global_image_loader


class ImageOverlayWidget(QWidget):
    """
    图片叠加层Widget，用于在节点悬停时显示女优或作品图片

    功能：
    - 接收 nodeHoveredWithInfo 信号，显示/隐藏图片
    - 图片位置跟随节点，但保持屏幕尺寸固定
    - 异步加载图片，避免阻塞UI
    - 拖拽时自动隐藏图片
    """

    # 屏幕像素尺寸：女优 180x180，作品 140x200
    _SIZE_ACTRESS = (180.0, 180.0)
    _SIZE_WORK = (140.0, 200.0)
    _FORWARD_EVENT_TYPES = (
        QEvent.Type.Enter,
        QEvent.Type.Leave,
        QEvent.Type.MouseMove,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.Wheel,
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置窗口属性 - 使其成为透明悬浮层
        # 注意：不设置 WindowTransparentForInput，因为我们需要动态管理它
        # 初始状态使用透明输入，隐藏时让事件穿透到底层视图
        self._update_window_flags(transparent_input=True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # 不显示在布局中，使用绝对定位
        # 初始大小为0，隐藏状态
        self.setGeometry(0, 0, 0, 0)

        # 连接全局图片加载器的信号
        global_image_loader.image_loaded.connect(self._on_image_loaded)

        # 当前显示的状态
        self.current_image: Optional[QImage] = None
        self.current_node_id: str = ""
        self.image_rect: Optional[QRectF] = None
        self.dragging: bool = False
        self._last_scale = 1.0

        # 保存最后的悬停信息，用于缩放或resize时更新位置
        self._last_hover_info = None

        # 保存view的引用，用于连接信号
        self._view_widget = None

        # 定时器引用（由父widget创建）
        self._image_update_timer = None

        # 默认隐藏
        self.hide()

    def _update_window_flags(self, transparent_input: bool):
        """
        动态更新窗口标志，管理鼠标事件穿透

        Args:
            transparent_input: True 时事件穿透到底层视图，False 时拦截事件
        """
        if transparent_input:
            # 隐藏状态：让鼠标事件穿透到底层 ForceViewOpenGL
            flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowTransparentForInput
            )
        else:
            # 显示状态：不设置 WindowTransparentForInput，允许事件正常传递
            # 通过 eventFilter 转发事件给底层视图
            flags = Qt.WindowType.FramelessWindowHint

        # 注意：setWindowFlags 会隐藏窗口，需要重新显示
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def _hide_overlay(self, clear_state: bool = False):
        """隐藏叠加层；clear_state 为 True 时同时清空当前图片与悬停信息。"""
        self.hide()
        self._update_window_flags(transparent_input=True)
        self._stop_image_update_timer()
        if clear_state:
            self.current_image = None
            self.current_node_id = ""
            self.image_rect = None
            self._last_hover_info = None

    def _on_image_loaded(self):
        """图片加载完成时更新显示"""
        if not self._last_hover_info or not self._last_hover_info[0]:
            return
        node_id, x, y, radius, scale, dragging = self._last_hover_info
        if node_id:
            # 重新尝试获取图片
            image = self._get_image_for_node(node_id)
            if image and not image.isNull():
                # 图片加载完成，更新并显示
                self.current_image = image
                self.current_node_id = node_id
                self.image_rect = self._calculate_image_rect(
                    x, y, radius, scale, node_id
                )
                if not dragging:
                    self._update_widget_geometry(x, y)
                    # 显示前更新窗口标志，允许事件传递
                    self._update_window_flags(transparent_input=False)
                    self.show()
                    self._start_image_update_timer()

    def set_view_widget(self, view_widget, timer=None):
        """设置view widget引用，连接信号
        Args:
            view_widget: ForceViewOpenGL 视图控件
            timer: 图片更新定时器（可选，由父widget传入）
        """
        self._view_widget = view_widget
        if self._view_widget:
            self._image_update_timer = timer

    def on_node_hovered_with_info(
        self,
        node_id: str,
        x: float,
        y: float,
        radius: float,
        scale: float,
        dragging: bool,
    ):
        """
        处理悬停事件，显示或隐藏图片

        Args:
            node_id: 节点ID（如 "a100" 或 "w123"）
            x: 节点场景坐标 X
            y: 节点场景坐标 Y
            radius: 节点半径
            scale: 当前缩放级别
            dragging: 是否正在拖拽
        """
        self.dragging = dragging
        self._last_scale = scale  # 保存缩放级别

        # 保存悬停信息，用于resize或图片加载完成后更新
        self._last_hover_info = (node_id, x, y, radius, scale, dragging)

        # 如果正在拖拽，隐藏图片
        if dragging:
            self._hide_overlay()
            return

        # 如果节点ID为空，隐藏图片
        if not node_id:
            self._hide_overlay(clear_state=True)
            return

        # 尝试获取图片
        image = self._get_image_for_node(node_id)

        if image and not image.isNull():
            self.current_image = image
            self.current_node_id = node_id

            # 计算图片显示位置（保持屏幕尺寸固定）
            self.image_rect = self._calculate_image_rect(x, y, radius, scale, node_id)

            # 转换为窗口坐标并显示
            self._update_widget_geometry(x, y)
            self._update_window_flags(transparent_input=False)
            self.show()
            self.update()

            # 启动定时器，让图片跟随节点移动
            self._start_image_update_timer()
        else:
            # 图片未加载完成，隐藏
            self._hide_overlay()
            # 注意：图片加载完成后，image_loaded信号会触发update()
            # 但我们需要重新计算位置，所以需要保存悬停信息

    def _get_image_for_node(self, node_id: str) -> Optional[QImage]:
        """根据节点ID获取对应的图片（a 女优，w 作品）"""
        if not node_id or len(node_id) < 2:
            return None
        prefix = node_id[0]
        getters = {
            "a": lambda i: global_image_loader.get_actress_image(i),
            "w": lambda i: global_image_loader.get_work_image(i),
        }
        if prefix not in getters:
            return None
        try:
            raw_id = int(node_id[1:])
            return getters[prefix](raw_id)
        except ValueError:
            return None

    def _calculate_image_rect(
        self, x: float, y: float, radius: float, scale: float, node_id: str
    ) -> QRectF:
        """
        计算图片在场景坐标系中的显示矩形

        图片尺寸固定为屏幕像素尺寸，根据scale反算场景坐标
        """
        img_w_screen, img_h_screen = (
            self._SIZE_ACTRESS if node_id.startswith("a") else self._SIZE_WORK
        )
        # 根据缩放比例反算场景坐标
        img_w = img_w_screen / scale
        img_h = img_h_screen / scale

        # 计算图片位置（显示在节点上方）
        # 偏移量：半径 + 图片高度 + 固定间距(20像素)
        image_x = x - img_w * 0.5
        image_y = y - radius - img_h - (20.0 / scale)

        return QRectF(image_x, image_y, img_w, img_h)

    def _update_widget_geometry(self, x: float, y: float):
        """
        更新Widget在父窗口中的几何位置

        将场景坐标转换为屏幕坐标，再转换为Widget坐标
        C++中的screenToScene：outX = panX + (sx - viewportW/2) / zoom
        反推：sx = (sceneX - panX) * zoom + viewportW / 2

        Args:
            x: 节点场景坐标 X（用于计算中心点）
            y: 节点场景坐标 Y（用于计算中心点）
        """
        if not self.image_rect or not self._view_widget:
            return

        view_widget = self._view_widget
        # 获取viewport尺寸
        viewport_width = view_widget.width()
        viewport_height = view_widget.height()

        # 使用view的getter方法获取变换信息
        try:
            pan_x = view_widget.getPanX()
            pan_y = view_widget.getPanY()
            scale = view_widget.getZoom()
        except AttributeError:
            # 如果方法不存在，使用保存的scale和默认的pan
            scale = getattr(self, "_last_scale", 1.0)
            pan_x = 0.0
            pan_y = 0.0

        # 计算图片中心点的屏幕坐标（相对于viewport）
        # screen_x = (scene_x - pan_x) * zoom + viewport_width / 2
        scene_center_x = self.image_rect.center().x()
        scene_center_y = self.image_rect.center().y()

        screen_x = (scene_center_x - pan_x) * scale + viewport_width / 2
        screen_y = (scene_center_y - pan_y) * scale + viewport_height / 2

        # 获取图片的屏幕尺寸
        screen_w = self.image_rect.width() * scale
        screen_h = self.image_rect.height() * scale

        # 计算Widget在父容器中的位置（左上角）
        widget_x = screen_x - screen_w / 2
        widget_y = screen_y - screen_h / 2

        # 获取view在parent中的位置
        view_pos = view_widget.pos()

        # 图片叠加层的最终位置 = view位置 + 屏幕坐标偏移
        final_x = view_pos.x() + int(widget_x)
        final_y = view_pos.y() + int(widget_y)

        # 设置Widget几何属性（使用屏幕尺寸，绝对定位）
        # 注意：不使用move()，直接设置geometry
        self.setGeometry(final_x, final_y, int(screen_w), int(screen_h))

    def paintEvent(self, event):
        """绘制当前图片"""
        if not self.current_image or self.current_image.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制图片
        target_rect = self.rect()
        painter.drawImage(target_rect, self.current_image)

        painter.end()

    def hide_image(self):
        """隐藏图片"""
        self._hide_overlay(clear_state=True)

    def _start_image_update_timer(self):
        """启动图片位置更新定时器"""
        if self._image_update_timer:
            self._image_update_timer.start()

    def _stop_image_update_timer(self):
        """停止图片位置更新定时器"""
        if self._image_update_timer:
            self._image_update_timer.stop()

    def update_position_from_node_id(self, node_id: str, view_widget) -> bool:
        """
        根据节点ID更新图片位置（从视图获取最新的节点位置）

        Args:
            node_id: 节点ID
            view_widget: ForceViewOpenGL 视图控件

        Returns:
            是否成功更新位置
        """
        if not node_id or not view_widget:
            return False

        # 检查是否正在拖拽
        if self._last_hover_info:
            _, _, _, _, _, dragging = self._last_hover_info
            if dragging:
                return False  # 拖拽时不更新

        # 从视图获取节点位置
        try:
            node_pos = view_widget.getNodePosition(node_id)
            if node_pos.isNull():
                return False

            x = node_pos.x()
            y = node_pos.y()

            # 获取scale和radius
            scale = (
                view_widget.getZoom()
                if hasattr(view_widget, "getZoom")
                else self._last_scale
            )
            radius = 7.0  # 默认半径

            # 重新计算图片位置
            self.image_rect = self._calculate_image_rect(x, y, radius, scale, node_id)

            # 更新widget几何属性
            self._update_widget_geometry(x, y)
            self.update()
            if self._last_hover_info:
                _, _, _, last_radius, _, dragging = self._last_hover_info
                updated_radius = last_radius if last_radius else radius
                self._last_hover_info = (node_id, x, y, updated_radius, scale, dragging)
            return True

        except Exception as e:
            logging.warning(f"更新图片位置失败: {e}")
            return False

    def resizeEvent(self, event):
        """窗口大小改变时更新"""
        super().resizeEvent(event)
        # 如果有悬停信息，重新计算位置
        if self._last_hover_info and self._last_hover_info[0]:
            # 重新使用最后悬停信息更新位置
            node_id, x, y, radius, scale, dragging = self._last_hover_info
            if not dragging and self.current_image and not self.current_image.isNull():
                self.image_rect = self._calculate_image_rect(
                    x, y, radius, scale, node_id
                )
                self._update_widget_geometry(x, y)
                self.update()
