import sys
import os
from pathlib import Path
import logging

# ----------------------------------------------------------
root_dir = Path(__file__).resolve().parents[2]  # 上两级
sys.path.insert(0, str(root_dir))

import networkx as nx
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtGui import QColor
from PySide6.QtCore import QSize, QTimer, QEvent, Slot
import PySide6

qt_bin = Path(PySide6.__file__).resolve().parent
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(str(qt_bin))

from cpp_bindings.forced_direct_view.PyForceView import ForceViewOpenGL
from core.graph.graph_session import GraphViewSession
from core.graph.graph_filter import PassThroughFilter, EgoFilter
from core.graph.force_view_settings_panel import ForceViewSettingsPanel
from darkeye_ui.components.state_toggle_button import StateToggleButton
from core.graph.image_overlay_widget import ImageOverlayWidget


class ForceDirectedViewWidget(QWidget):
    """控制面板+view的容器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 图片叠加层总开关（由设置面板控制）
        self._image_overlay_enabled: bool = True
        # 节点颜色覆盖：{"actress"|"work"|"center"|"default" -> QColor or None}
        self._color_overrides: dict[str, QColor | None] = {}
        self._center_id: str | None = None
        # 首次加载 graph 但控件尚未可见时，需要在 show 后补一次刷新/fit
        self._pending_first_paint_refresh: bool = False

        # 主题管理器（用于令牌驱动视图背景色）
        self._theme_manager = None
        try:
            from controller.app_context import get_theme_manager

            self._theme_manager = get_theme_manager()
        except ImportError as e:
            logging.debug(
                "ForceDirectedViewWidget: 无法导入主题管理器: %s",
                e,
                exc_info=True,
            )

        self.init_ui()
        self.signal_connect()
        # 根据面板当前状态同步图片叠加层开关
        self.set_image_overlay_enabled(self.panel.show_image.isChecked())

    def init_ui(self):
        mainlayout = QVBoxLayout(self)
        mainlayout.setContentsMargins(0, 0, 0, 0)

        self.view = ForceViewOpenGL(parent=self)
        mainlayout.addWidget(self.view)

        # 创建定时器，用于定期更新图片位置（必须在创建image_overlay之前）
        self.image_update_timer = QTimer(self)
        self.image_update_timer.setInterval(16)  # 60fps
        self.image_update_timer.timeout.connect(self._update_image_position)

        # 创建图片叠加层（悬浮层，不添加到布局）

        self.image_overlay = ImageOverlayWidget(parent=self)
        # 不添加到布局，使用绝对定位

        self.image_overlay.set_view_widget(
            self.view, self.image_update_timer
        )  # 设置view引用以监听scale变化

        # -------- Session：GraphManager -> 过滤 -> OpenGL View --------
        self.session = GraphViewSession()
        self.session.dataReady.connect(self._on_graph_data_ready)
        self.session.diffChanged.connect(self._on_graph_diff_changed)

        # self.settings_button = IconPushButton(iconpath="settings.svg", iconsize=24,outsize=32,color="#5C5C5C", parent=self)
        # self.settings_button=StateToggleButton(state1_icon="settings.svg",state1_color="#5C5C5C",state2_icon="x.svg",state2_color="#5C5C5C",iconsize=24,outsize=32,hoverable=True,parent=self)
        self.settings_button = StateToggleButton(
            state1_icon="settings",
            state2_icon="x",
            icon_size=24,
            out_size=32,
            hoverable=True,
            parent=self,
        )

        self.panel = ForceViewSettingsPanel(self)

        self.settings_button.raise_()
        self.panel.raise_()

    def signal_connect(self):
        self.settings_button.clicked.connect(self._toggle_panel)
        # View -> 业务逻辑
        self.view.nodeLeftClicked.connect(self._on_node_clicked)

        self.panel.arrowEnabledChanged.connect(self.view.setArrowEnabled)
        self.panel.arrowScaleChanged.connect(self.view.setArrowScale)
        # Panel -> 图片叠加层开关
        self.panel.imageOverlayEnabledChanged.connect(self.set_image_overlay_enabled)
        # 连接图片悬停信号（先经过总开关判断）
        self.view.nodeHoveredWithInfo.connect(self._on_view_node_hovered_with_info)

        self.panel.manyBodyStrengthChanged.connect(self.view.setManyBodyStrength)
        self.panel.centerStrengthChanged.connect(self.view.setCenterStrength)
        self.panel.linkStrengthChanged.connect(self.view.setLinkStrength)
        self.panel.linkDistanceChanged.connect(self.view.setLinkDistance)
        self.panel.neighborDepthChanged.connect(self.view.setNeighborDepth)
        self.panel.graphNeighborDepthChanged.connect(self.set_graph_neighbor_depth)

        self.panel.radiusFactorChanged.connect(self.view.setRadiusFactor)
        self.panel.linkWidthFactorChanged.connect(self.view.setSideWidthFactor)
        self.panel.textThresholdFactorChanged.connect(self.view.setTextThresholdFactor)
        self.panel.nodeColorGroupChanged.connect(self._on_nodeColorGroupChanged)

        self.panel.restartRequested.connect(self.view.restartSimulation)
        self.panel.pauseRequested.connect(self.view.pauseSimulation)
        self.panel.resumeRequested.connect(self.view.resumeSimulation)
        self.panel.fitInViewRequested.connect(self.view.fitViewToContent)

        self.panel.addNodeRequested.connect(self._on_addNodeRequested)
        self.panel.removeNodeRequested.connect(self._on_removeNodeRequested)
        self.panel.addEdgeRequested.connect(self._on_addEdgeRequested)
        self.panel.removeEdgeRequested.connect(self._on_removeEdgeRequested)

        self.panel.graphModeChanged.connect(self._switch_graph)
        # 与面板内 deferred 几何同步配合：此处直接更新，避免再叠一层 singleShot 晚一帧
        self.panel.contentSizeChanged.connect(self._update_panel_geometry)

        # 令牌驱动：视图背景、边、节点、文本颜色随主题切换
        if self._theme_manager is not None:
            self._theme_manager.themeChanged.connect(self._apply_theme_from_tokens)
            self._apply_theme_from_tokens()

        # View -> panel (update labels)
        self.view.fpsUpdated.connect(self.panel.set_fps)
        self.view.tickTimeUpdated.connect(self.panel.set_tick_time)
        self.view.paintTimeUpdated.connect(self.panel.set_paint_time)
        self.view.scaleChanged.connect(self.panel.set_scale)
        self.view.alphaUpdated.connect(self.panel.set_alpha)

    @Slot()
    def _apply_theme_from_tokens(self) -> None:
        """根据当前主题令牌设置 OpenGL 视图背景、边、节点、文本颜色。"""
        if self._theme_manager is None:
            return
        tokens = self._theme_manager.tokens()

        def _apply(name: str, setter, fallback: str = "#808080") -> None:
            color_str = getattr(tokens, name, fallback) or fallback
            c = QColor(color_str)
            if c.isValid():
                setter(c)

        bg = getattr(tokens, "color_bg", None) or getattr(tokens, "color_bg", "#ffffff")
        if (c := QColor(bg)).isValid():
            self.view.setBackgroundColor(c)
        _apply("color_border", self.view.setEdgeColor)
        _apply("color_bg_page", self.view.setEdgeDimColor)
        _apply("color_text", self.view.setBaseColor)
        _apply("color_bg_page", self.view.setDimColor)
        _apply("color_primary", self.view.setHoverColor)
        _apply("color_text", self.view.setTextColor)
        _apply("color_bg_page", self.view.setTextDimColor)

    def set_graph_neighbor_depth(self, depth: int):
        """设置图邻居深度,用于这个中心过滤模式下的深度切换"""
        logging.debug(f"设置图邻居深度: {depth}")
        self.session.fast_calc_diff(depth)

    def _on_view_node_hovered_with_info(
        self,
        node_id: str,
        x: float,
        y: float,
        radius: float,
        scale: float,
        dragging: bool,
    ) -> None:
        """
        统一入口处理节点悬停事件：
        - 根据 _image_overlay_enabled 决定是否转发给图片叠加层
        """
        if not self._image_overlay_enabled:
            # 关闭时确保叠加层隐藏
            if self.image_overlay:
                self.image_overlay.hide_image()
            return

        if self.image_overlay:
            self.image_overlay.on_node_hovered_with_info(
                node_id, x, y, radius, scale, dragging
            )

    def set_image_overlay_enabled(self, enabled: bool) -> None:
        """
        开关图片叠加层：
        - 控制悬浮图片控件可见性
        - 控制是否响应节点悬停事件
        - 可选：根据开关启停位置更新定时器
        """
        self._image_overlay_enabled = bool(enabled)

        if not self.image_overlay:
            return

        if enabled:
            # 开启时显示叠加层，并启动位置更新定时器
            self.image_overlay.setVisible(True)
            if self.image_update_timer is not None:
                self.image_update_timer.start()
        else:
            # 关闭时隐藏叠加层并停止定时器
            self.image_overlay.hide_image()
            self.image_overlay.setVisible(False)
            if self.image_update_timer is not None:
                self.image_update_timer.stop()

    def _on_addNodeRequested(self):
        self.view.add_node_runtime("c200", 10.0, 10.0, "c200", 7.0, QColor("#5C5C5C"))
        self.view.add_node_runtime("c201", 0.0, 0.0, "c201", 7.0, QColor("#257845"))

    def _on_removeNodeRequested(self):
        self.view.remove_node_runtime("c200")

    def _on_addEdgeRequested(self):
        self.view.add_edge_runtime("c200", "c201")

    def _on_removeEdgeRequested(self):
        self.view.remove_edge_runtime("c200", "c201")

    def _update_image_position(self):
        """定期更新图片位置，使其跟随节点移动"""
        if not self.image_overlay or not self.image_overlay.isVisible():
            return

        # 检查是否有图片正在显示
        if (
            not self.image_overlay.current_image
            or self.image_overlay.current_image.isNull()
        ):
            return

        # 获取当前悬停的节点ID
        node_id = self.image_overlay.current_node_id
        if not node_id:
            return

        # 更新图片位置
        self.image_overlay.update_position_from_node_id(node_id, self.view)

    def _on_node_clicked(self, node_id: str) -> None:
        """
        节点点击后的跳转逻辑（node_id 为节点 id，来自 m_ids[index]）：
        - a 开头：跳转 single_actress
        - w 开头：跳转 work
        """
        if not node_id:
            return
        nodename = str(node_id)

        if nodename.startswith("a"):
            from ui.navigation.router import Router

            Router.instance().push("single_actress", actress_id=int(nodename[1:]))
            print(f"跳转女优界面：{nodename}")
        elif nodename.startswith("w"):
            from ui.navigation.router import Router

            # Router.instance().push("work", work_id=int(nodename[1:]))
            Router.instance().push("shelf", work_id=int(nodename[1:]))
            print(f"跳转作品界面：{nodename}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_panel_geometry()
        # 触发图片叠加层重新计算位置（如果当前正在显示图片）
        if (
            self.image_overlay.isVisible()
            and self.image_overlay.current_image
            and not self.image_overlay.current_image.isNull()
        ):
            # 直接触发位置更新，不需要重新调用on_node_hovered_with_info
            if (
                hasattr(self.image_overlay, "_update_widget_geometry")
                and self.image_overlay._last_hover_info
            ):
                node_id, x, y, radius, scale, dragging = (
                    self.image_overlay._last_hover_info
                )
                if not dragging:
                    self.image_overlay.image_rect = (
                        self.image_overlay._calculate_image_rect(
                            x, y, radius, scale, node_id
                        )
                    )
                    self.image_overlay._update_widget_geometry(x, y)

    def showEvent(self, event):
        """当控件重新显示（例如从其他页面/窗口切回来）时，强制刷新悬浮控件位置。"""
        super().showEvent(event)
        # 延迟 0ms，确保布局和尺寸已经稳定，再根据最新 rect 重新定位
        QTimer.singleShot(0, self._update_panel_geometry)
        # 兜底：如果第一次 setGraph 发生在控件隐藏/0尺寸时，OpenGL 可能没真正绘制出来。
        # 在 show 后补一次 fit + update，确保第一次进入也能显示。
        if self._pending_first_paint_refresh:
            self._pending_first_paint_refresh = False
            QTimer.singleShot(0, self._refresh_view_after_first_show)

    def _refresh_view_after_first_show(self) -> None:
        try:
            if self.view is not None:
                self.view.fitViewToContent()
                self.view.update()
        except Exception:
            # 不要让 UI 因为兜底逻辑崩溃
            logging.exception("ForceDirectedViewWidget: 首次显示后刷新 OpenGL 视图失败")

    def _update_panel_geometry(self) -> None:
        """悬浮的东西只能自己手动定位"""
        rect = self.rect()
        if rect.isEmpty():  # 外框
            return
        margin = 10
        offset_x = 0
        offset_y = 0
        btn_size: QSize = self.settings_button.sizeHint()
        self.settings_button.move(
            max(margin, rect.width() - btn_size.width() - margin - offset_x),
            margin + offset_y,
        )
        if self.panel.isVisible():
            panel_width: int = min(250, max(0, rect.width() - 2 * margin))
            # 计算最大可用高度(保留底部边距)
            max_available_height = rect.height() - 2 * margin - offset_y
            self.panel.set_maximum_panel_height(max_available_height)

            panel_height: int = min(
                self.panel.sizeHint().height(), max_available_height
            )
            self.panel.resize(panel_width, panel_height)
            self.panel.move(
                max(margin, rect.width() - panel_width - margin - offset_x),
                margin + offset_y,
            )
            self.panel.raise_()
            self.settings_button.raise_()

    def _toggle_panel(self):
        if self.panel.isVisible():
            self.panel.setVisible(False)
        else:
            self.panel.setVisible(True)
            # 延迟调整,确保可见后再计算
            from PySide6.QtCore import QTimer

            def delayed_adjust():
                self.panel._adjust_panel_height()
                self._update_panel_geometry()
                self.panel.raise_()
                self.settings_button.raise_()

            QTimer.singleShot(0, delayed_adjust)

    def _on_nodeColorGroupChanged(self, group: str, color: QColor) -> None:
        """面板修改某类节点颜色后，更新覆盖并实时推送到 view。"""
        self._color_overrides[group] = color
        ids = self.view.getNodeIds()
        if not ids:
            return
        colors = [
            self._node_color(
                str(nid),
                None,
                is_center=(self._center_id is not None and str(nid) == self._center_id),
            )
            for nid in ids
        ]
        self.view.setNodeColors(colors)

    def _switch_graph(self, mode: str):
        """
        切换图类型：只是用于测试使用
        - all: 使用 PassThroughFilter，全图
        - favorite: 使用 EgoFilter 或你自定义的“片关系图”过滤器
        - test: 使用随机图（不经过 GraphManager）
        """
        if mode == "test":
            # 测试模式：直接生成一张随机小图，不走 GraphManager / Session
            G = nx.gnm_random_graph(200, 400)
            # 这里你也可以给节点加 label/group 属性
            for n in G.nodes():
                G.nodes[n]["label"] = f"n{n}"
            self._set_graph_from_networkx(G, modify=False)
            return

        # 其他模式走 GraphViewSession + GraphManager
        if mode == "all":
            self.session.set_filter(PassThroughFilter())
        elif mode == "favorite":
            # 示例：以某个中心点的 ego 图作为“片关系图”
            # center_id 你可以改成当前选中的作品/女优，比如 "a100" / "w123"
            center_id = "a36"
            self.session.set_filter(EgoFilter(center_id=center_id, radius=2))
        else:
            self.session.set_filter(PassThroughFilter())

        # 触发一次重载
        self.session.new_load()

    def load_graph(self, G):
        pass
        # self.view.load_graph(G)

    def _node_color(
        self, node_id: str, attr: dict | None, is_center: bool = False
    ) -> QColor:
        """
        根据节点 id / group 计算显示颜色。可由 panel 颜色覆盖（_color_overrides）。
        """
        if is_center:
            c = self._color_overrides.get("center")
            return c if c is not None else QColor("#FFD700")
        group = attr.get("group") if attr else None
        if node_id.startswith("a") or group == "actress":
            c = self._color_overrides.get("actress")
            return c if c is not None else QColor("#ff99cc")
        if node_id.startswith("w") or group == "work":
            c = self._color_overrides.get("work")
            return c if c is not None else QColor("#99ccff")
        c = self._color_overrides.get("default")
        return c if c is not None else QColor("#5C5C5C")

    def _set_graph_from_networkx(self, G: nx.Graph, modify: bool = False) -> None:
        """
        把一个 networkx.Graph 转成 ForceView/ForceViewOpenGL.setGraph 所需的参数。
        """
        if G is None:
            return

        nodes = list(G.nodes())
        n = len(nodes)
        if n == 0:
            return

        index_of = {node_id: i for i, node_id in enumerate(nodes)}

        # 1. edges: 扁平化 [src0, dst0, src1, dst1, ...]，用“索引”即可
        edges: list[int] = []
        for u, v in G.edges():
            iu = index_of[u]
            iv = index_of[v]
            edges.append(iu)
            edges.append(iv)
        pos: list[float] = []

        # 3. ids / labels / radii
        # ids: 传给 C++ 的是字符串列表（与 labels 同类型）；C++ 点击时发出m_id[下标]
        # nx 节点 id 就是 nodes[i]（女优 "a"+数字，作品 "w"+数字），已保存在 self._nodes 里。
        ids: list[str] = []
        labels: list[str] = []
        radii: list[float] = []

        degrees = dict(G.degree())
        deg_values = list(degrees.values()) or [1]
        min_deg = min(deg_values)
        max_deg = max(deg_values)

        for i, node_id in enumerate(nodes):
            # node_id 即 nx 图节点 id（如 "a100"/"w123"）；C++ 接收 QStringList，传 str(node_id)。
            ids.append(str(node_id))

            data = G.nodes[node_id]
            label = data.get(
                "label", str(node_id)
            )  # label就是节点的标签，女优是姓名，作品是番号名
            labels.append(str(label))

            deg = float(degrees.get(node_id, 1))
            # 度数重映射到半径 [4, 10]
            if max_deg <= min_deg:
                r = 7.0  # 全部同度数时取中间值
            else:
                t = (deg - min_deg) / (max_deg - min_deg)
                r = 4.0 + t * 6.0
            radii.append(r)

        # 4. 颜色：由 _node_color 根据 node_id/group 计算（中心节点金色）
        center_id = None
        if isinstance(self.session._filter, EgoFilter):
            center_id = self.session._filter.center_id
        self._center_id = center_id
        node_colors = []
        for node_id in nodes:
            data = G.nodes[node_id]
            is_center = center_id is not None and node_id == center_id
            node_colors.append(self._node_color(node_id, data, is_center=is_center))
        logging.info(G)

        # 保存节点和 label，供点击跳转使用
        self._nodes = nodes
        self._labels = labels

        # 5. 调用 C++ 视图（用位置参数，避免关键字 id 与 Python 内置 id 冲突导致 Shiboken 绑定异常）
        self.view.setGraph(n, edges, pos, ids, labels, radii, node_colors)

    def _on_graph_data_ready(self, payload: dict) -> None:
        """
        Session -> View：收到过滤后的子图，调用 setGraph。
        """
        cmd = payload.get("cmd")
        if cmd != "load_graph":
            return

        G = payload.get("graph")
        if G is None:
            return

        modify = bool(payload.get("modify", False))
        self._set_graph_from_networkx(G, modify=modify)
        # 如果此时控件还没真正显示出来（例如 overlay 延迟显示），标记在 showEvent 里补刷新
        if not self.isVisible() or self.width() <= 0 or self.height() <= 0:
            self._pending_first_paint_refresh = True
        else:
            QTimer.singleShot(0, self._refresh_view_after_first_show)

    def _on_graph_diff_changed(self, diff_list: list) -> None:
        """
        Session -> View：收到增量更新，调用增加点与减点的方法
        """
        # 基本健壮性判断
        if not diff_list:
            return

        ops: list[dict] = []

        for item in diff_list:
            # 跳过异常项，避免打断 UI
            if not isinstance(item, dict):
                continue

            op = item.get("op")

            # ----- 节点增删 -----
            if op == "add_node":
                node_id = item.get("id")
                if node_id is None:
                    continue

                node_id = str(node_id)
                attr = item.get("attr") or {}

                # 文本标签
                label = str(attr.get("label", node_id))

                # 半径（如果没有就用默认 7.0）这个东西就是混合了，如果半径依赖度数就必须在session里弄，如果不依赖就在widget里弄
                try:
                    radius = float(attr.get("radius", 7.0))
                except (TypeError, ValueError):
                    radius = 7.0

                # 颜色：由 _node_color 根据 node_id/group 计算
                color = self._node_color(node_id, attr, is_center=False)

                # 坐标暂时传 0,0，由模拟自己调整布局
                ops.append(
                    {
                        "op": "add_node",
                        "id": node_id,
                        "x": 0.0,
                        "y": 0.0,
                        "attr": {
                            "label": label,
                            "radius": radius,
                            "color": color,
                        },
                    }
                )

            elif op == "del_node":
                node_id = item.get("id")
                if node_id is None:
                    continue
                ops.append({"op": "del_node", "id": str(node_id)})

            # ----- 边增删 -----
            elif op == "add_edge":
                u = item.get("u")
                v = item.get("v")
                if u is None or v is None:
                    continue
                ops.append({"op": "add_edge", "u": str(u), "v": str(v)})

            elif op == "del_edge":
                u = item.get("u")
                v = item.get("v")
                if u is None or v is None:
                    continue
                ops.append({"op": "del_edge", "u": str(u), "v": str(v)})

        if not ops:
            return

        # 一次性应用增量，避免频繁 stop/rebuild/start 导致卡顿或崩溃
        self.view.apply_diff_runtime(ops)


def main():
    from core.graph.graph_filter import EgoFilter
    from core.graph.graph_manager import GraphManager

    app = QApplication(sys.argv)

    # 1. 显式初始化 GraphManager（异步，后台线程加载图）
    manager = GraphManager.instance()
    if not manager._initialized:
        manager.initialize()

    window = QMainWindow()
    window.setWindowTitle("ForceView - Ego Graph (Actress ID 100)")
    window.resize(1000, 700)

    central_widget = ForceDirectedViewWidget()
    window.setCentralWidget(central_widget)
    view_session = central_widget.session

    # 2. 等图加载完成后再设置过滤器并加载视图（否则 reload() 时 G 仍为空）
    def on_graph_ready():
        # view_session.set_filter(EgoFilter(center_id="a100", radius=3))
        view_session.new_load()

    if manager._initialized:
        on_graph_ready()
    else:
        manager.initializationFinished.connect(on_graph_ready)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
