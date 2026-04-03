"""工作区管理类：持布局树、窗格工厂、拖拽与预览，供 WorkspaceDemoWidget 等容器使用。"""

import json
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from ui.myads.pane_widget import PaneWidget
from ui.myads.layout_tree import LayoutTree, SplitModelNode
from ui.myads.tab_drag_handler import execute_drop_action
from ui.myads.split_preview import SplitPreviewOverlay
from ui.myads.drag_drop_overlay import DragDropOverlay


# 与 QtAds 的 LeftDockWidgetArea / CenterDockWidgetArea 等语义一致，便于对照 test_dock 写法
class Placement:
    Left = 1
    Right = 2
    Top = 3
    Bottom = 4


def _make_placeholder_content(text: str) -> QWidget:
    """创建占位内容。"""
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.addWidget(QLabel(text))
    return w


SPLITTER_STYLE = """
    QSplitter::handle {
        background: #cccccc;
        width: 2px;
        height: 2px;
        border: none;
        margin: 0;
    }
    QSplitter::handle:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4facfe, stop:0.5 #00f2fe, stop:1 #4facfe);
    }
"""


def _style_splitter(splitter):
    splitter.setStyleSheet(SPLITTER_STYLE)
    splitter.setChildrenCollapsible(False)


class _WorkspaceHostWidget(QWidget):
    """内部宿主：承载 layout 根 widget 与预览/拖放 overlay，resize 时自动更新几何与层级。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._overlay: SplitPreviewOverlay | None = None
        self._drag_overlay: DragDropOverlay | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def set_overlay(self, overlay: SplitPreviewOverlay) -> None:
        self._overlay = overlay
        self._update_overlay_geometry()

    def set_drag_overlay(self, overlay: DragDropOverlay) -> None:
        self._drag_overlay = overlay
        self._update_overlay_geometry()

    def _update_overlay_geometry(self) -> None:
        r = self.rect()
        if self._overlay is not None:
            self._overlay.setGeometry(r)
            self._overlay.raise_()
        if self._drag_overlay is not None:
            self._drag_overlay.setGeometry(r)
            self._drag_overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_geometry()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_overlay_geometry()


class ContentConfig:
    """先创建、再 set_widget/set_window_title/set_icon、最后由 manager.place_content 加入布局。"""

    __slots__ = ("content_id", "_widget", "_title", "_icon", "_closeable")

    def __init__(self, content_id: str) -> None:
        self.content_id = content_id
        self._widget: QWidget | None = None
        self._title: str | None = None
        self._icon: QIcon | None = None
        self._closeable: bool = True

    def set_widget(self, w: QWidget) -> "ContentConfig":
        self._widget = w
        return self

    def set_window_title(self, title: str) -> "ContentConfig":
        self._title = title
        return self

    def set_icon(self, icon: QIcon | None) -> "ContentConfig":
        self._icon = icon
        return self

    def set_closeable(self, closeable: bool) -> "ContentConfig":
        self._closeable = closeable
        return self


class WorkspaceManager:
    """工作区管理：根节点、LayoutTree、overlay、拖拽、窗格/内容工厂与拆分 API。对外提供 widget()，ADS 式用法：layout.addWidget(manager.widget())。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._host = _WorkspaceHostWidget(parent)
        root_model = SplitModelNode(Qt.Horizontal, [])

        self._layout_tree = LayoutTree(
            root_model,
            style_splitter=_style_splitter,
            on_root_replaced=self._on_root_replaced,
        )

        self._host.layout().addWidget(self._layout_tree.root())
        self._overlay = SplitPreviewOverlay(self._host)
        self._host.set_overlay(self._overlay)

        def execute_drop(pane, zone, ev):
            return execute_drop_action(
                self._layout_tree,
                self._new_pane,
                self._layout_tree.find_pane_by_id,
                self._register_pane,
                pane,
                zone,
                ev,
            )

        self._drag_overlay = DragDropOverlay(
            self._host,
            get_panes=lambda: self._layout_tree.panes(),
            preview_callback=self._on_preview,
            execute_drop=execute_drop,
        )
        self._host.set_drag_overlay(self._drag_overlay)

        self._pane_counter = 0
        self._content_counter = 0
        self._content_closeable: dict[str, bool] = {}

    def _on_root_replaced(self, old_w: QWidget, new_w: QWidget) -> None:
        """根被提升替换时，在容器的 layout 中把旧根 widget 换成新根 widget，并销毁旧根避免遗留分割线、阻挡点击。"""
        lay = self._host.layout()
        if lay is None:
            return
        for i in range(lay.count()):
            item = lay.itemAt(i)
            if item and item.widget() is old_w:
                lay.removeWidget(old_w)
                lay.insertWidget(i, new_w)
                new_w.show()
                # 旧根从 layout 移除后仍是 _host 的子控件，先隐藏再延迟销毁，避免 setParent(None) 导致闪窗
                old_w.hide()
                old_w.deleteLater()
                break
        self._overlay.raise_()
        self._drag_overlay.raise_()

    def widget(self) -> QWidget:
        """返回宿主 widget（含根视图与 overlay），调用方仅需 layout.addWidget(manager.widget())。"""
        return self._host

    def layout_tree(self) -> LayoutTree:
        return self._layout_tree

    def find_pane_by_content_id(self, content_id: str) -> PaneWidget | None:
        """根据 content_id（内容唯一 id）查找包含该内容的窗格。"""
        for pane in self._layout_tree.panes():
            if content_id in pane.content_ids():
                return pane
        return None

    def is_content_closeable(self, content_id: str) -> bool:
        """查询 content_id 是否可关闭（用于序列化）。"""
        return self._content_closeable.get(content_id, True)

    def _new_pane(self) -> PaneWidget:
        self._pane_counter += 1
        return PaneWidget(pane_id=f"pane_{self._pane_counter}")

    def new_content_id(self) -> str:
        self._content_counter += 1
        return f"content_{self._content_counter}"

    def _register_pane(self, pane: PaneWidget) -> None:
        """内部注册：连接信号、拖拽开始/结束时激活/恢复 overlay；closeable 由 manager 统一提供。"""
        pane.paneEmpty.connect(self._on_pane_empty)
        pane.set_drag_start_callback(self._drag_overlay.activate)
        pane.set_drag_end_callback(self._drag_overlay.deactivate)
        pane.set_get_content_closeable(
            lambda cid: self._content_closeable.get(cid, True)
        )
        # 不再对每个 pane 设置 drop_handler，由 DragDropOverlay 统一命中与执行

    def _on_pane_empty(self, pane: PaneWidget) -> None:
        pane.paneEmpty.disconnect(self._on_pane_empty)
        self._layout_tree.remove_pane(pane)
        if not self._layout_tree.panes():
            new_pane = self._new_pane()
            self._layout_tree.add_pane_to_root(new_pane)
            self._register_pane(new_pane)

    def _get_or_create_center_pane(self) -> PaneWidget:
        """无根下窗格时创建并挂到根，否则返回当前默认目标窗格。"""
        target = self._layout_tree.get_default_target_pane()
        if target is not None:
            return target
        pane = self._new_pane()
        self._layout_tree.add_pane_to_root(pane)
        self._register_pane(pane)
        return pane

    def get_root_pane(self) -> PaneWidget:
        """返回根窗格，作为布局起点；无则懒创建并挂到根。"""
        return self._get_or_create_center_pane()

    def _placement_to_split_args(self, area: int) -> tuple[Qt.Orientation, bool]:
        """Placement -> (direction, insert_before)。"""
        if area == Placement.Left:
            return Qt.Horizontal, True
        if area == Placement.Right:
            return Qt.Horizontal, False
        if area == Placement.Top:
            return Qt.Vertical, True
        if area == Placement.Bottom:
            return Qt.Vertical, False
        return Qt.Horizontal, False

    def split(
        self,
        pane: PaneWidget,
        placement: int,
        *,
        ratio: float = 0.5,
    ) -> PaneWidget:
        """从指定 pane 切出新窗格并返回。
        ratio 始终为新分出那块占该次两块的比重，例如 Placement.Right + ratio=0.3 表示右边新窗格占 30%。
        """
        direction, insert_before = self._placement_to_split_args(placement)
        new_pane = self._new_pane()
        tree = self._layout_tree
        if tree.find_parent_of_pane(pane) is not None:
            tree.split(pane, direction, insert_before, new_pane, ratio=ratio)
        else:
            tree.add_pane_to_root(new_pane)
        self._register_pane(new_pane)
        return new_pane

    def fill_pane(self, pane: PaneWidget, content_config: ContentConfig) -> None:
        """将已配置的 ContentConfig 填入指定 pane（内部转成 add_content）。
        若该 pane 中已存在 content_config.content_id，则使用新 content_id 添加为新 tab，保证每次调用都会多一个 tab。
        同一 pane 内每个 tab 由唯一 content_id 标识；要对同一 pane 添加多个 tab 需传入不同 content_id 或复用同一 config（此时会自动分配新 id）。
        """
        content_id = content_config.content_id
        if content_id in pane.content_ids():
            content_id = self.new_content_id()
        self._content_closeable[content_id] = content_config._closeable
        title = (
            content_config._title
            if content_config._title is not None
            else content_config.content_id
        )
        widget = (
            content_config._widget
            if content_config._widget is not None
            else _make_placeholder_content(content_config.content_id)
        )
        icon = content_config._icon
        pane.add_content(content_id, title, widget, icon=icon)

    def _on_preview(self, zone, target_pane) -> None:
        self._overlay.show_preview(zone, target_pane)

    def save_layout(
        self,
        path: str | Path,
        *,
        get_content_descriptor: Callable[[PaneWidget, str], dict | None] | None = None,
        get_pane_metadata: Callable[[PaneWidget], dict] | None = None,
    ) -> None:
        """将布局与内容序列化为 JSON。get_content_descriptor(pane, content_id) 返回可序列化的内容描述；
        get_pane_metadata(pane) 返回窗格元数据（如 icon_only）。不提供时仅保存布局结构。"""
        layout_dict = self._layout_tree.to_dict()
        data: dict = {"layout": layout_dict}
        if get_content_descriptor is not None:
            pane_contents: dict[str, list[dict]] = {}
            for pane in self._layout_tree.panes():
                items = []
                for content_id in pane.content_ids():
                    desc = get_content_descriptor(pane, content_id)
                    if desc is not None:
                        desc = dict(desc)
                        desc.setdefault("content_id", content_id)
                        items.append(desc)
                if items:
                    pane_contents[pane.pane_id] = items
            data["pane_contents"] = pane_contents
        if get_pane_metadata is not None:
            pane_metadata = {}
            for pane in self._layout_tree.panes():
                meta = get_pane_metadata(pane)
                if meta:
                    pane_metadata[pane.pane_id] = meta
            data["pane_metadata"] = pane_metadata
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_layout(
        self,
        path: str | Path,
        *,
        content_factory: Callable[[dict], ContentConfig | None] | None = None,
    ) -> None:
        """从 path 加载布局与内容。content_factory(descriptor) 根据描述创建 ContentConfig；
        不提供时仅恢复布局结构，窗格为空。支持旧格式（仅 layout 的 JSON）。"""
        data = LayoutTree.load_layout_file(path)
        layout_dict = data.get("layout", data)
        pane_contents = data.get("pane_contents", {})
        pane_metadata = data.get("pane_metadata", {})

        for pane in list(self._layout_tree.panes()):
            try:
                pane.paneEmpty.disconnect(self._on_pane_empty)
            except (TypeError, RuntimeError) as e:
                logging.debug(
                    "load_layout: 断开 pane_empty 失败（可能未连接）: %s",
                    e,
                    exc_info=True,
                )
            self._layout_tree.remove_pane(pane)

        def pane_factory(pid: str) -> PaneWidget:
            pane = PaneWidget(pane_id=pid)
            self._register_pane(pane)
            meta = pane_metadata.get(pid, {})
            if meta.get("icon_only"):
                pane.set_icon_only(True)
            return pane

        self._layout_tree.load_layout_from_dict(layout_dict, pane_factory)

        if content_factory is not None and pane_contents:
            for pane_id, items in pane_contents.items():
                pane = self._layout_tree.find_pane_by_id(pane_id)
                if pane is None:
                    continue
                for desc in items:
                    cfg = content_factory(desc)
                    if cfg is not None:
                        self.fill_pane(pane, cfg)

    def create_content_config(self, content_id: str | None = None) -> ContentConfig:
        """创建内容配置，content_id 为 None 时由内部自动分配。"""
        if content_id is None:
            content_id = self.new_content_id()
        return ContentConfig(content_id)
