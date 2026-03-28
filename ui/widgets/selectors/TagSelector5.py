from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QSizePolicy,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsObject,
)
from PySide6.QtCore import (
    Signal,
    QEasingCurve,
    QVariantAnimation,
    Slot,
    QTimer,
    QRectF,
    Qt,
    QPointF,
)
from PySide6.QtGui import (
    QPixmap,
    QCursor,
    QPainter,
    QPainterPath,
    QColor,
    QFontMetrics,
    QFont,
)
from pathlib import Path
import logging
from typing import TYPE_CHECKING, Optional

from config import ICONS_PATH
from core.database.query import get_tags, get_tagid_by_keyword

from controller.MessageService import MessageBoxService
from darkeye_ui.components import TokenVerticalTabBar
from ui.base import SearchLineBase
from controller.GlobalSignalBus import global_signals
from utils.utils import (
    timeit,
    get_text_color_from_background,
    get_hover_color_from_background,
)
from darkeye_ui.components.icon_push_button import IconPushButton
from darkeye_ui.components.rotate_button import RotateButton
from darkeye_ui.components.shake_button import ShakeButton

if TYPE_CHECKING:
    from darkeye_ui.design.theme_manager import ThemeManager
    from darkeye_ui.design.tokens import ThemeTokens

# 这个纯ai改了3个小时，一遍一遍的改，没有人工的成分
# ==============================================================================
# 1. 核心图元类 TagGraphicsItem (替代 VerticalTagLabel2)
# ==============================================================================


class TagGraphicsItem(QGraphicsObject):
    """
    轻量级标签图元，用于在 QGraphicsScene 中高性能渲染。
    逻辑尽量复刻 VerticalTagLabel/VLabel 的绘制逻辑。
    """

    clicked = Signal(int)  # 发送 tag_id

    def __init__(
        self, tag_id, text, tag_type, background_color, detail, tag_mutex, parent=None
    ):
        super().__init__(parent)
        self.tag_id = tag_id
        self.text_content = text
        self.tag_type = tag_type
        self.detail = detail
        self.tag_mutex = tag_mutex

        # 颜色属性
        self.bg_color = QColor(background_color)
        self.text_color = get_text_color_from_background(self.bg_color)
        self.hover_color = get_hover_color_from_background(self.bg_color)
        self.border_color = QColor("#00000000")  # 默认透明边框

        # 状态
        self._hovered = False
        self._selected = False  # 如果被选中，可能需要变灰或隐藏
        self._flashing = False  # 是否处于搜索高亮闪烁状态

        # 闪烁定时器
        self._flash_timer = QTimer(self)
        self._flash_timer.timeout.connect(self._toggle_flash)

        # 字体初始化 (复用 VLabel 配置)
        self.chinese_font = QFont("KaiTi", 12)
        self.chinese_font.setBold(True)
        self.english_font = QFont("Courier New", 14)
        self.english_font.setBold(True)

        # 尺寸参数
        self.corner_cut_ratio = 0.2
        self.hole_radius_ratio = 0.1
        self.column_width = 27  # 默认列宽，与 WaterfallLayout 保持一致

        # 缓存计算好的尺寸和路径
        self._rect = QRectF()
        self._shape_path = QPainterPath()
        self._calculate_geometry()

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)

    def _calculate_geometry(self):
        """预计算尺寸和绘制路径，避免在 paint 中重复计算"""
        # 1. 计算高度 (复用 VLabel._calculate_size 逻辑)
        width = self.column_width

        # 字体度量
        metrics_cn = QFontMetrics(self.chinese_font)
        # standard_char_width = metrics_cn.horizontalAdvance("中")
        # width = standard_char_width * 1.7 # VLabel 里的逻辑，这里简化为固定宽，或外部传入

        if not self.text_content:
            height = width * 2
        else:
            total_height = 0
            for ch in self.text_content:
                if ch == "\n":
                    continue
                fm = QFontMetrics(self._select_font(ch))
                if self._is_chinese(ch):
                    char_height = fm.height()
                else:
                    char_height = fm.ascent() + fm.descent() * 0.3
                total_height += char_height

            # 头部视觉修正
            first_char = self.text_content[0]
            fm_first = QFontMetrics(self._select_font(first_char))
            char_width = fm_first.horizontalAdvance(first_char)
            if self._is_chinese(first_char):
                fmodify = char_width * 0.1
            else:
                fmodify = char_width * 0.4

            height = (
                total_height
                + width * self.corner_cut_ratio * 3
                + width * self.hole_radius_ratio * 2
                - fm_first.descent() * 0.3
                - fmodify
            )

        self._rect = QRectF(0, 0, width, height)

        # 2. 生成路径 (复用 VLabel.paintEvent 逻辑)
        rect = self._rect
        cut = rect.width() * self.corner_cut_ratio
        hole_radius = rect.width() * self.hole_radius_ratio

        # 外轮廓
        outer_path = QPainterPath()
        outer_path.moveTo(cut, 0)
        outer_path.lineTo(rect.width() - cut, 0)
        outer_path.lineTo(rect.width(), cut)
        outer_path.lineTo(rect.width(), rect.height() - cut)
        outer_path.lineTo(rect.width() - cut, rect.height())
        outer_path.lineTo(cut, rect.height())
        outer_path.lineTo(0, rect.height() - cut)
        outer_path.lineTo(0, cut)
        outer_path.closeSubpath()

        # 穿孔
        hole_path = QPainterPath()
        hole_center_x = rect.width() / 2
        hole_center_y = cut + hole_radius
        hole_path.addEllipse(
            QPointF(hole_center_x, hole_center_y), hole_radius, hole_radius
        )

        self._outer_path = outer_path
        self._hole_path = hole_path
        self._fill_path = outer_path.subtracted(hole_path)

    def flash(self, duration=3000, interval=150):
        """高亮闪烁 (快速切换)"""
        # 如果已经在闪烁，先停止
        if self._flash_timer.isActive():
            self._flash_timer.stop()

        self._flashing = True
        self.update()

        # 启动定时器进行快速切换
        self._flash_timer.start(interval)

        # 设定结束时间
        QTimer.singleShot(duration, self.stop_flash)

    def _toggle_flash(self):
        """切换闪烁状态"""
        self._flashing = not self._flashing
        self.update()

    def stop_flash(self):
        self._flash_timer.stop()
        self._flashing = False
        self.update()

    def boundingRect(self):
        return self._rect

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        # 确定颜色
        if self._flashing:
            # 反色模式：文字颜色做背景，背景颜色做文字，确保高对比度
            bg_color = (
                QColor(self.text_color)
                if isinstance(self.text_color, str)
                else self.text_color
            )
            text_color = (
                QColor(self.bg_color)
                if isinstance(self.bg_color, str)
                else self.bg_color
            )
            stroke_color = (
                QColor(self.border_color)
                if isinstance(self.border_color, str)
                else self.border_color
            )
        elif self._hovered:
            bg_color = self.bg_color.lighter(110)
            text_color = self.hover_color
            stroke_color = QColor("#FF0000")
        else:
            bg_color = self.bg_color
            text_color = self.text_color
            stroke_color = self.border_color

        # 绘制背景
        painter.fillPath(self._fill_path, bg_color)

        # 绘制边框
        painter.setPen(stroke_color)
        painter.drawPath(self._outer_path)
        painter.drawPath(self._hole_path)

        # 绘制文字
        self._draw_text(painter, text_color)

    def _draw_text(self, painter, text_color):
        rect = self._rect
        cut = rect.width() * self.corner_cut_ratio
        hole_radius = rect.width() * self.hole_radius_ratio

        metrics_cn = QFontMetrics(self.chinese_font)
        max_char_width = metrics_cn.horizontalAdvance("中")

        # 计算起始 Y
        fmodify = 0
        if self.text_content:
            first_char = self.text_content[0]
            fm = QFontMetrics(self._select_font(first_char))
            char_width = fm.horizontalAdvance(first_char)
            if self._is_chinese(first_char):
                fmodify = char_width * 0.1
            else:
                fmodify = char_width * 0.4

        y = cut * 2 + hole_radius * 2 - fmodify

        # 绘制循环
        # text_color 由外部传入

        for char in self.text_content:
            if char == "\n":
                continue

            font = self._select_font(char)
            painter.setFont(font)
            painter.setPen(text_color)

            fm = QFontMetrics(font)
            char_width = fm.horizontalAdvance(char)

            if self._is_chinese(char):
                char_height = fm.height()
            else:
                char_height = fm.ascent() + fm.descent() * 0.3

            # 水平居中
            char_x = (rect.width() - max_char_width) / 2 + (
                max_char_width - char_width
            ) / 2

            painter.drawText(char_x, y + fm.ascent(), char)
            y += char_height

    def _select_font(self, char):
        if "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff":
            return self.chinese_font
        return self.english_font

    def _is_chinese(self, char):
        return "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff"

    # 事件处理
    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
            self.clicked.emit(self.tag_id)
            return
        super().mousePressEvent(event)


# ==============================================================================
# 2. 瀑布流场景与视图 (TagWaterfallScene & View)
# ==============================================================================


class TagWaterfallScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items_map = {}  # tag_id -> TagGraphicsItem
        self.type_items = {}  # tag_type -> list[TagGraphicsItem]
        self.column_width = 27
        self.spacing = 5
        self.margin = 5

    def add_tag_item(self, item: TagGraphicsItem):
        self.addItem(item)
        self.items_map[item.tag_id] = item
        if item.tag_type not in self.type_items:
            self.type_items[item.tag_type] = []
        self.type_items[item.tag_type].append(item)

    def remove_tag_item(self, item: TagGraphicsItem):
        self.removeItem(item)
        if item.tag_id in self.items_map:
            del self.items_map[item.tag_id]
        if item.tag_type in self.type_items:
            items = self.type_items[item.tag_type]
            if item in items:
                items.remove(item)

    def move_to_end(self, item: TagGraphicsItem):
        """将指定 item 移到该类型列表的末尾，以实现'恢复时追加到最后'的效果"""
        if item.tag_type in self.type_items:
            items = self.type_items[item.tag_type]
            if item in items:
                items.remove(item)
                items.append(item)

    def layout_items(self, width, current_type=None, custom_items=None):
        """核心布局算法：纯数学计算"""
        # 确定目标 items
        if custom_items is not None:
            target_items = custom_items
            # 自定义列表模式下，强制所有 item 可见
            for item in target_items:
                item.setVisible(True)
        elif current_type:
            target_items = self.type_items.get(current_type, [])
            # 类型过滤模式：处理可见性
            for t_type, items in self.type_items.items():
                is_current_type = t_type == current_type
                for item in items:
                    if is_current_type:
                        # 如果是被选中的（Item上有标记），则保持隐藏
                        if getattr(item, "_is_selected_hidden", False):
                            item.setVisible(False)
                        else:
                            item.setVisible(True)
                    else:
                        item.setVisible(False)
        else:
            return

        if not target_items:
            self.setSceneRect(0, 0, width, 0)
            return

        # 开始瀑布流计算
        available_width = width - self.margin * 2
        # 防止宽度过小导致除零或负数
        if available_width <= 0:
            return

        col_count = max(1, int(available_width // (self.column_width + self.spacing)))

        # 居中偏移
        total_content_width = (
            col_count * self.column_width + (col_count - 1) * self.spacing
        )
        offset_x = self.margin + (available_width - total_content_width) / 2

        col_heights = [self.margin] * col_count

        for item in target_items:
            if not item.isVisible():
                continue

            # 找最短列
            min_h = min(col_heights)
            col_idx = col_heights.index(min_h)

            x = offset_x + col_idx * (self.column_width + self.spacing)
            y = min_h

            item.setPos(x, y)
            col_heights[col_idx] += item.boundingRect().height() + self.spacing

        total_height = max(col_heights) + self.margin
        # 关键修复：确保 SceneRect 的高度足够大，否则 ScrollBar 认为无需滚动
        self.setSceneRect(0, 0, width, total_height)


class TagWaterfallView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # 去掉边框和背景
        self.setStyleSheet("background: transparent; border: none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )  # 改为按需显示，或保持 AlwaysOn 但需确保 SceneRect 正确
        self.current_tag_type = None
        self.custom_items = None  # List of items for custom layout

    def showEvent(self, event):
        super().showEvent(event)
        # 第一次显示时，强制布局一次，确保内容正确填充
        if self.scene() and self.viewport().width() > 0:
            if self.custom_items is not None:
                self.scene().layout_items(
                    self.viewport().width(), custom_items=self.custom_items
                )
            else:
                self.scene().layout_items(
                    self.viewport().width(), self.current_tag_type
                )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 宽度变化时重新布局
        if self.scene():
            # 使用 viewport 的宽度，扣除滚动条可能占用的空间
            # 如果宽度过小（初始化或动画中），则忽略或使用默认值
            vp_width = self.viewport().width()
            if vp_width < 50:
                return

            if self.custom_items is not None:
                self.scene().layout_items(vp_width, custom_items=self.custom_items)
            else:
                self.scene().layout_items(vp_width, self.current_tag_type)

    def set_current_type(self, tag_type):
        self.current_tag_type = tag_type
        self.update_layout()
        # 滚动回顶部
        self.verticalScrollBar().setValue(0)

    def update_layout(self):
        """手动触发布局更新"""
        if self.scene():
            width = self.viewport().width()
            if width < 50:
                width = self.width()  # Fallback

            if self.custom_items is not None:
                self.scene().layout_items(width, custom_items=self.custom_items)
            else:
                self.scene().layout_items(width, self.current_tag_type)


# ==============================================================================
# 3. 主容器 TagSelector5 (组合 Widget 与 GraphicsView)
# ==============================================================================


class FloatingPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mainlayout = QVBoxLayout(self)
        self.mainlayout.setContentsMargins(0, 0, 0, 0)

        self.searchLine = SearchLineBase()

        self.tag_emit_tabwidget = QTabWidget()
        self.tag_emit_tabwidget.setTabPosition(QTabWidget.West)
        self.tag_emit_tabwidget.setTabBar(TokenVerticalTabBar())

        self.mainlayout.addWidget(self.searchLine)
        self.mainlayout.addWidget(self.tag_emit_tabwidget)

        # 确保 TabWidget 不会因为内容过多而撑破布局，而是应该在内部滚动
        self.tag_emit_tabwidget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        self.tag_emit_tabwidget.setStyleSheet("""
            QTabWidget {
                border: none;
                background: transparent;
            }
            QTabWidget::pane {
                border: none;
                background: transparent;
                margin: 0;
                padding: 0;
            }
        """)

    def animate_width(self, target_width, duration=300):
        self.anim = QVariantAnimation(
            startValue=self.width(),
            endValue=target_width,
            duration=duration,
            easingCurve=QEasingCurve.InOutQuad,
        )
        self.anim.valueChanged.connect(self.setFixedWidth)
        self.anim.start()


class TagSelector5(QWidget):
    """
    TagSelector5 - 基于 QGraphicsView 的高性能标签选择器
    架构：
    - 左侧 (已选区): 使用 QGraphicsView + TagWaterfallScene
    - 右侧 (备选区): 使用 QGraphicsView + TagWaterfallScene
    """

    success = Signal(bool)
    selectionChanged = Signal()

    def __init__(self, enbale_mutex_check=True):
        super().__init__()
        self.setCursor(
            QCursor(QPixmap(Path(ICONS_PATH / "mouse_off.png")), hotX=32, hotY=32)
        )
        self.setStyleSheet("""
            QTabWidget::pane, QScrollArea, QFrame {
                border: none;
                background: transparent;
            }
        """)

        self.enbale_mutex_check = enbale_mutex_check
        self.msg = MessageBoxService(self)

        # 数据核心
        self.tag_data_map = {}  # tag_id -> TagData (dict or obj)
        self.selected_ids = set()

        # 左侧 UI (Widget 模式)
        self._init_left_ui()

        # 右侧 UI (FloatingPanel + GraphicsView)
        self._init_right_ui()

        # 布局组合
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.left_widget, 0)
        main_layout.addWidget(self.panel, 0)
        main_layout.addStretch(1)

        # 初始化逻辑
        self.load_tags()
        self.beatutetoolbox()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_tabwidget_styles)
        self.signal_connect()

        self.panel_visible = False
        self.panel.animate_width(0)
        self.panel.searchLine.set_search_navi(self.search_func, self.navi_func)

    def _init_left_ui(self):
        # 1. 创建左侧 View 和 Scene (替代原有的 WaterfallLayout + ScrollArea)
        self.left_scene = TagWaterfallScene()
        self.left_view = TagWaterfallView(self.left_scene)
        self.left_view.custom_items = []  # 启用自定义列表模式
        self.left_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        # 宽度设定：配合 left_widget 的总宽，预留给 View 的空间
        self.left_view.setFixedWidth(130)
        # 背景与边框由设计令牌控制，见 _apply_left_view_styles
        self._theme_manager: Optional["ThemeManager"] = None
        try:
            from controller.app_context import get_theme_manager

            self._theme_manager = get_theme_manager()
        except Exception as e:
            logging.debug(
                "TagSelector5: 获取主题管理器失败，左侧样式将用默认令牌: %s",
                e,
                exc_info=True,
            )
        self._apply_left_view_styles()
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_left_view_styles)

        # 2. 标题 Item (使用 TagGraphicsItem 模拟，ID=-1)，颜色由令牌控制
        title_bg, title_border = self._get_title_item_token_colors()
        self.title_item = TagGraphicsItem(-1, "作品标签", "TITLE", title_bg, "", "")
        self.title_item.border_color = QColor(title_border)
        self.title_item.setAcceptHoverEvents(False)  # 标题不响应悬停
        self.title_item.setCursor(Qt.ArrowCursor)

        self.left_scene.add_tag_item(self.title_item)
        self.left_view.custom_items.append(self.title_item)

        # 3. 工具按钮
        self.btn_clear = ShakeButton(
            icon_name="brush_cleaning", icon_size=24, out_size=24
        )
        self.btn_reload_tag = RotateButton(
            icon_name="refresh_cw", icon_size=24, out_size=24
        )
        self.btn_expand = IconPushButton(
            icon_name="arrow_right", icon_size=24, out_size=24
        )

        v_small_widget = QWidget()
        v_small_widget.setFixedWidth(24)
        left_small_layout = QVBoxLayout(v_small_widget)
        left_small_layout.setContentsMargins(0, 0, 0, 0)
        left_small_layout.addWidget(self.btn_clear)
        left_small_layout.addWidget(self.btn_reload_tag)
        left_small_layout.addWidget(self.btn_expand)
        left_small_layout.addStretch()

        # 4. 左侧主容器
        self.left_widget = QWidget()
        self.left_widget.setFixedWidth(130 + 24)  # View宽度 + 按钮条宽度
        left_layout = QHBoxLayout(self.left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.left_view)
        left_layout.addWidget(v_small_widget)

    def _apply_view_style(self, view: TagWaterfallView) -> None:
        """根据当前主题令牌设置单个 View 的边框与背景。"""
        if self._theme_manager is not None:
            t = self._theme_manager.tokens()
            view.setStyleSheet(f"""
                QGraphicsView {{
                    border: {t.border_width} dashed {t.color_border};
                    border-radius: {t.radius_md};
                    background: {t.color_bg};
                }}
            """)
        else:
            view.setStyleSheet("""
                QGraphicsView {
                    border: 2px dashed #ccc;
                    border-radius: 8px;
                    background: #ffffff;
                }
            """)

    def _get_title_item_token_colors(self) -> tuple[str, str]:
        """从设计令牌获取标题项的背景色和边框色。"""
        if self._theme_manager is not None:
            t = self._theme_manager.tokens()
            return (t.color_text, t.color_border)
        return ("#333333", "#ccc")

    def _apply_left_view_styles(self) -> None:
        """根据当前主题令牌刷新左侧和右侧所有 View 的样式。"""
        # 左侧 View
        if hasattr(self, "left_view") and self.left_view is not None:
            self._apply_view_style(self.left_view)
        # 标题 Item 颜色（随主题更新）
        if hasattr(self, "title_item") and self.title_item is not None:
            title_bg, title_border = self._get_title_item_token_colors()
            self.title_item.bg_color = QColor(title_bg)
            self.title_item.text_color = get_text_color_from_background(
                self.title_item.bg_color
            )
            self.title_item.border_color = QColor(title_border)
            self.title_item.update()
        # 右侧所有 Tab 中的 View
        for view in getattr(self, "views_map", {}).values():
            if view is not None:
                self._apply_view_style(view)
        # 右侧 TabWidget 的 TabBar 样式
        self._apply_tabwidget_styles()

    def _init_right_ui(self):
        self.panel = FloatingPanel()
        self.panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.panel_fix_width = 255
        self.panel.setFixedWidth(self.panel_fix_width)

        # 初始化 Scene
        self.scene = TagWaterfallScene()

        # 关键改动：不再为每个 Type 创建 ScrollArea，而是共用一个 View，只是切换 Scene 的过滤
        # 为了兼容 TabBar 的交互，我们还是要在 TabWidget 里填一些占位符，
        # 或者拦截 TabBar 的点击事件。
        # 这里为了视觉效果，我们可以在 TabWidget 的页面里放入 View。
        # 但考虑到 View 的复用，更好的做法是：
        # TabWidget 只作为 TabBar 使用（内容区为空），当 Tab 切换时，通知 View 切换数据。
        # 但原有的设计是 TabWidget 包含内容。

        # 方案：为每个 TagType 创建一个 QGraphicsView？太重。
        # 方案：共用一个 View，当 Tab 切换时，Scene 重新布局。
        # 我们创建一个 Map: TabIndex -> TagType

        self.panel.tag_emit_tabwidget.currentChanged.connect(self.on_tab_changed)
        self.tab_type_map = {}  # index -> tag_type

        # 右侧视图容器 (这里直接替换 TabWidget 的 Content 可能比较麻烦，
        # 所以我们在 TabWidget 的每个 Tab 里放一个空的 Widget，
        # 然后把 View 覆盖在上面？不，直接把 View 放在每个 Tab 里是最简单的迁移方式，
        # 虽然会有多个 View 实例，但 Scene 可以是同一个吗？
        # GraphicsView 对应一个 Scene。如果我们为每个 Type 创建一个 Scene，View 可以切换 Scene。
        # 最佳方案：只有一个 Scene（包含所有 Items），通过过滤显示。只有一个 View。
        # 那么 TabWidget 的作用就是“筛选器”。

        # 这里为了保持原有布局结构，我们把 View 放在 StackedWidget 里？
        # 为了不破坏 panel.tag_emit_tabwidget 的结构，我们在每个 Tab 里塞一个 View。
        # 这样会创建多个 View，但每个 View 管理自己的 Scene 部分？
        # 实际上，原代码是每个 Tab 一个 QScrollArea。
        # 我们可以为每个 Tab 创建一个 TagWaterfallView (共享同一个 Scene? 不行，Item 只能属于一个 Scene)
        # 所以：每个 Tab 一个 Scene + 一个 View。虽然有些浪费，但逻辑隔离最清晰。

        self.views_map = {}  # tag_type -> TagWaterfallView
        self.scenes_map = {}  # tag_type -> TagWaterfallScene

    @Slot(int)
    def on_tab_changed(self, index):
        # 可以在这里做懒加载或动画
        if index < 0:
            return
        tag_type = self.panel.tag_emit_tabwidget.tabText(index)
        view = self.views_map.get(tag_type)
        if not view:
            return
        view.set_current_type(tag_type)

    def signal_connect(self):
        self.btn_expand.clicked.connect(self.toggle_panel)
        self.btn_reload_tag.clicked.connect(self.reload_tag)
        self.btn_clear.clicked.connect(self.clear_left_tags)
        global_signals.tagDataChanged.connect(self.reload_tag)

    def load_tags(self):
        """
        加载 Tag 数据，创建 GraphicsItems。
        耗时优化核心：只创建 Python 对象和 GraphicsItem，不创建 Widget。
        """
        logging.debug("TagSelector5 加载 tag 数据库")
        tags = get_tags()

        # 清理旧数据
        self.panel.tag_emit_tabwidget.clear()
        self.views_map.clear()
        self.scenes_map.clear()
        self.tag_data_map.clear()

        # 临时字典用于分组
        grouped_tags = {}  # type -> list[data]

        for tag_id, name, tag_type, color, detail, tag_mutex in tags:
            # 存储纯数据
            tag_data = {
                "id": tag_id,
                "name": name,
                "type": tag_type,
                "color": color,
                "detail": detail,
                "mutex": tag_mutex,
            }
            self.tag_data_map[tag_id] = tag_data

            if tag_type not in grouped_tags:
                grouped_tags[tag_type] = []
            grouped_tags[tag_type].append(tag_data)

        # 为每个类型创建 Scene 和 View
        for tag_type, data_list in grouped_tags.items():
            scene = TagWaterfallScene()
            # 创建 View，并使用设计令牌控制其背景与边框
            view = TagWaterfallView(scene)
            self._apply_view_style(view)
            view.set_current_type(
                tag_type
            )  # 关键：设置当前类型，否则 View 的事件触发布局时会因为 type=None 而清空内容

            for data in data_list:
                item = TagGraphicsItem(
                    data["id"],
                    data["name"],
                    data["type"],
                    data["color"],
                    data["detail"],
                    data["mutex"],
                )
                item.clicked.connect(self.handle_tag_click_id)
                scene.add_tag_item(item)

            # 初始布局 (使用面板固定宽度作为预估，减去滚动条大约宽度)
            estimated_width = self.panel_fix_width - 25
            scene.layout_items(estimated_width, tag_type)

            self.scenes_map[tag_type] = scene
            self.views_map[tag_type] = view

            self.panel.tag_emit_tabwidget.addTab(view, tag_type)

    def handle_tag_click_id(self, tag_id):
        """处理 GraphicsItem 点击"""
        if tag_id in self.selected_ids:
            # 已经在左边了，这里应该不会触发，因为右边通常不显示已选的？
            # 或者右边显示但不可点？
            # 现有逻辑：右边点击移到左边。
            pass
        else:
            tag_data = self.tag_data_map.get(tag_id)
            if not tag_data:
                return

            if self.enbale_mutex_check:
                conflicting_name = self.check_mutex_with_selected(tag_data)
                if conflicting_name:
                    self.msg.show_warning(
                        "标签冲突",
                        f"标签 <b>'{tag_data['name']}'</b> 与已选标签 <b>'{conflicting_name}'</b> 互斥！\n\n"
                        "请先移除冲突标签再添加。",
                    )
                    return

            self.move_to_left(tag_id)

    def move_to_left(self, tag_id):
        """从右侧移到左侧 (创建 GraphicsItem)"""
        if tag_id in self.selected_ids:
            return

        data = self.tag_data_map[tag_id]

        # 1. 右侧隐藏 (设置不可见并重新布局)
        if data["type"] in self.scenes_map:
            scene = self.scenes_map[data["type"]]
            if tag_id in scene.items_map:
                item = scene.items_map[tag_id]
                item._is_selected_hidden = True  # 标记为因选中而隐藏
                item.setVisible(False)  # 关键：隐藏

                # 触发重新布局填补空缺
                view = self.views_map[data["type"]]
                scene.layout_items(view.width(), data["type"])

        # 2. 左侧创建 GraphicsItem
        item = TagGraphicsItem(
            data["id"],
            data["name"],
            data["type"],
            data["color"],
            data["detail"],
            data["mutex"],
        )
        # 延迟执行，避免在本次 mousePress 中同步移除自身导致 Qt 在 release 时对已移除 item 调用 ungrabMouse
        item.clicked.connect(
            lambda tid=tag_id: QTimer.singleShot(0, lambda: self.restore_to_right(tid))
        )

        self.left_scene.add_tag_item(item)
        self.left_view.custom_items.append(item)

        self.selected_ids.add(tag_id)
        self.selectionChanged.emit()

        self.left_view.update_layout()

    def restore_to_right(self, tag_id, switch_tab=True):
        """从左侧移回右侧"""
        if tag_id not in self.selected_ids:
            return

        # 1. 左侧移除 Item
        if tag_id in self.left_scene.items_map:
            item = self.left_scene.items_map[tag_id]
            self.left_scene.remove_tag_item(item)
            if item in self.left_view.custom_items:
                self.left_view.custom_items.remove(item)

        self.selected_ids.remove(tag_id)
        self.left_view.update_layout()

        # 2. 右侧恢复显示
        data = self.tag_data_map[tag_id]
        if data["type"] in self.scenes_map:
            scene = self.scenes_map[data["type"]]
            if tag_id in scene.items_map:
                item = scene.items_map[tag_id]
                item._is_selected_hidden = False  # 取消隐藏标记

                # 修复：重置 hover 状态
                item._hovered = False
                item.update()

                # 修复：将 item 移到列表末尾
                scene.move_to_end(item)

                item.setVisible(True)
                view = self.views_map[data["type"]]
                scene.layout_items(view.width(), data["type"])

        # 3. 切换到对应的 Tab (如果是用户交互触发)
        if switch_tab:
            for i in range(self.panel.tag_emit_tabwidget.count()):
                if self.panel.tag_emit_tabwidget.tabText(i) == data["type"]:
                    self.panel.tag_emit_tabwidget.setCurrentIndex(i)
                    break

        self.selectionChanged.emit()

    def check_mutex_with_selected(self, new_tag_data) -> str | None:
        """互斥检查"""
        if not new_tag_data["mutex"]:
            return None

        for sid in self.selected_ids:
            exist_data = self.tag_data_map.get(sid)
            if exist_data and exist_data["mutex"] == new_tag_data["mutex"]:
                return exist_data["name"]
        return None

    def load_with_ids(self, ids: list[int]):
        """同步外部 ID 列表"""
        new_ids = set(ids)
        current_ids = self.selected_ids.copy()

        # 需要移除的
        for tid in current_ids - new_ids:
            self.restore_to_right(tid, switch_tab=False)

        # 需要添加的
        for tid in new_ids - current_ids:
            if tid in self.tag_data_map:
                self.move_to_left(tid)

    def get_selected_ids(self) -> list[int]:
        return list(self.selected_ids)

    def clear_left_tags(self):
        for tid in list(self.selected_ids):
            self.restore_to_right(tid, switch_tab=False)

    def reload_tag(self):
        """重新加载"""
        logging.debug("TagSelector5 重新加载")
        exist_ids = self.get_selected_ids()
        # 清空左侧
        self.clear_left_tags()
        # 重新加载右侧
        self.load_tags()
        # 恢复选中
        self.load_with_ids(exist_ids)

    @Slot()
    def toggle_panel(self):
        if self.panel_visible:
            self.panel.animate_width(0)
            self.btn_expand.set_icon_name("arrow_right")
        else:
            self.panel.animate_width(self.panel_fix_width)
            self.btn_expand.set_icon_name("arrow_left")

            # 延迟刷新布局，确保宽度已就位
            QTimer.singleShot(350, self.refresh_current_tab_layout)

        self.panel_visible = not self.panel_visible

    def refresh_current_tab_layout(self):
        """面板展开后强制刷新当前 Tab 的布局"""
        index = self.panel.tag_emit_tabwidget.currentIndex()
        if index == -1:
            return
        tag_type = self.panel.tag_emit_tabwidget.tabText(index)
        if tag_type in self.scenes_map:
            view = self.views_map[tag_type]
            scene = self.scenes_map[tag_type]
            # 使用 panel_fix_width 减去边距，或者直接用 view.width()
            # 此时动画结束，view.width() 应该是准确的
            scene.layout_items(view.width(), tag_type)

    def set_state(self, state: bool):
        """控制边框样式"""
        t = self._theme_manager.tokens()
        if not state:
            style = f"""
                QGraphicsView {{
                    border: {t.border_width} dashed {t.color_warning};    
                    border-radius: 5px;             
                }}
            """
        else:
            style = f"""
                QGraphicsView {{
                    border: {t.border_width} dashed {t.color_border};    
                    border-radius: 5px;             
                }}
            """
        self.left_view.setStyleSheet(style)

    def _apply_tabwidget_styles(self) -> None:
        """根据当前主题令牌设置右侧 QTabWidget 的 pane 与 QTabBar::tab 样式。"""
        if not hasattr(self, "panel") or self.panel is None:
            return
        if self._theme_manager is not None:
            t = self._theme_manager.tokens()
            self.panel.tag_emit_tabwidget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: none;
                    border-radius: 0;
                    background: transparent;
                    margin: 0;
                    padding: 0;
                }}
                QTabBar::tab {{
                    background: {t.color_bg};
                    color: {t.color_text};
                    border: {t.border_width} solid {t.color_border};
                    padding: 8px 18px;
                    /* 竖直标签栏的“宽度”（厚度） */
                    min-width: 90px;
                    border-top-left-radius: {t.radius_md};
                    border-bottom-left-radius: {t.radius_md};
                    margin-right: 4px;
                }}
                QTabBar::tab:hover {{
                    background: {t.color_bg_input};
                    color: {t.color_text};
                }}
                QTabBar::tab:selected {{
                    background: {t.color_primary};
                    color: {t.color_text_inverse};
                    font-weight: bold;
                }}
            """)
            # VerticalTabBar 自绘文字，需通过 dynamic property 传入颜色才能按令牌显示
            tab_bar = self.panel.tag_emit_tabwidget.tabBar()
            tab_bar.setProperty("tabTextColor", t.color_text)
            tab_bar.setProperty("tabTextColorSelected", t.color_text_inverse)
            tab_bar.style().unpolish(tab_bar)
            tab_bar.style().polish(tab_bar)
            tab_bar.update()
        else:
            self.panel.tag_emit_tabwidget.setStyleSheet("""
                QTabWidget::pane {
                    border: none;
                    border-radius: 0;
                    background: transparent;
                    margin: 0;
                    padding: 0;
                }
                QTabBar::tab {
                    background: #ffffff;
                    color: #999;
                    border: 2px solid #ccc;
                    padding: 8px 18px;
                    /* 竖直标签栏的“宽度”（厚度） */
                    min-width: 90px;
                    border-top-left-radius: 8px;
                    border-bottom-left-radius: 8px;
                    margin-right: 4px;
                }
                QTabBar::tab:hover {
                    background: #f0faff;
                    color: #333;
                }
                QTabBar::tab:selected {
                    background: #00aaff;
                    color: #ffffff;
                    font-weight: bold;
                }
            """)
            tab_bar = self.panel.tag_emit_tabwidget.tabBar()
            tab_bar.setProperty("tabTextColor", "#999")
            tab_bar.setProperty("tabTextColorSelected", "#ffffff")
            tab_bar.update()

    def beatutetoolbox(self):
        """美化 TabWidget（样式由令牌控制，见 _apply_tabwidget_styles）"""
        self._apply_tabwidget_styles()

    # 搜索功能适配
    def search_func(self, keyword: str) -> list:
        if not keyword:
            return []
        tag_ids = get_tagid_by_keyword(keyword)
        return tag_ids if tag_ids else []

    def navi_func(self, results: list, index: int):
        """搜索导航"""
        if not results:
            return
        tag_id = results[index]

        # 1. 检查是否在左侧 (已选)
        if tag_id in self.selected_ids:
            if tag_id in self.left_scene.items_map:
                item = self.left_scene.items_map[tag_id]
                self.left_view.centerOn(item)
                item.flash(3000)
            return

        # 2. 在右侧查找
        tag_data = self.tag_data_map.get(tag_id)
        if not tag_data:
            return

        # 切换到对应的 Tab
        tag_type = tag_data["type"]

        # 查找 Tab index
        for i in range(self.panel.tag_emit_tabwidget.count()):
            if self.panel.tag_emit_tabwidget.tabText(i) == tag_type:
                self.panel.tag_emit_tabwidget.setCurrentIndex(i)
                break

        # 滚动并高亮
        if tag_type in self.scenes_map:
            scene = self.scenes_map[tag_type]
            view = self.views_map[tag_type]
            if tag_id in scene.items_map:
                item = scene.items_map[tag_id]
                view.centerOn(item)
                # 高亮效果 (反色显示3秒)
                item.flash(3000)
