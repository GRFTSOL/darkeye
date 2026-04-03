"""阶段二：布局树与 QSplitter 动态管理。"""

"""测试文件在tests/"""
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import QSplitter, QWidget
from PySide6.QtCore import Qt
from typing import Union, Callable

from ui.myads.pane_widget import PaneWidget

# -------- 纯数据节点（无 Qt 依赖）--------

ModelNode = Union["SplitModelNode", "PaneModelNode"]


class PaneModelNode:
    """纯数据：仅保存 pane_id。"""

    __slots__ = ("pane_id",)

    def __init__(self, pane_id: str) -> None:
        self.pane_id = pane_id


class SplitModelNode:
    """纯数据：orientation + children + 可选 sizes（与 QSplitter.sizes() 一致）。"""

    __slots__ = ("orientation", "children", "sizes")

    def __init__(
        self,
        orientation: Qt.Orientation,
        children: list[ModelNode] | None = None,
        sizes: list[int] | None = None,
    ) -> None:
        self.orientation = orientation
        self.children: list[ModelNode] = children if children is not None else []
        self.sizes: list[int] | None = sizes


# -------- LayoutTreeModel（纯数据树）--------


# 与 QSplitter 一致的整数比例基数
_SIZE_BASE = 1000


def _model_index_of(parent: SplitModelNode, pane_id: str) -> int:
    """在 parent.children 中找 PaneModelNode.pane_id == pane_id 的索引。"""
    for i, c in enumerate(parent.children):
        if isinstance(c, PaneModelNode) and c.pane_id == pane_id:
            return i
    return -1


def _set_equal_sizes(node: SplitModelNode, M: int = _SIZE_BASE) -> None:
    """将 node.sizes 设为子节点均分。"""
    n = len(node.children)
    if n < 2:
        node.sizes = None
        return
    q, r = divmod(M, n)
    node.sizes = [q] * (n - 1) + [q + r]


def _expand_sizes_for_flatten(part: int, child: "SplitModelNode") -> list[int]:
    """展平时把单个槽位 part 展开为多段：用 child.sizes 按比例缩放，或均分。"""
    n = len(child.children)
    if n == 0:
        return []
    if child.sizes is not None and len(child.sizes) == n:
        total = sum(child.sizes)
        if total == 0:
            q, r = divmod(part, n)
            return [q] * (n - 1) + [q + r]
        scaled = [part * s // total for s in child.sizes]
        delta = part - sum(scaled)
        if delta != 0 and scaled:
            scaled[-1] += delta
        return scaled
    q, r = divmod(part, n)
    return [q] * (n - 1) + [q + r]


def _model_dump(node: ModelNode, indent: int = 0) -> list[str]:
    """递归收集模型树节点信息。，这个只能知道窗格的信息，无法知道pane里面有几个tab"""
    lines = []
    prefix = "  " * indent
    if isinstance(node, SplitModelNode):
        orient = (
            "H"
            if node.orientation == Qt.Horizontal
            else ("V" if node.orientation == Qt.Vertical else "—")
        )
        sizes_str = repr(node.sizes) if node.sizes is not None else "None"
        lines.append(
            f"{prefix}Split({orient}) children={len(node.children)} sizes={sizes_str}"
        )
        for child in node.children:
            lines.extend(_model_dump(child, indent + 1))
    else:
        lines.append(f"{prefix}Pane(id={node.pane_id})")
    return lines


class LayoutTreeModel:
    """纯数据布局树：根为 SplitModelNode，叶子为 PaneModelNode。无 Qt 依赖。"""

    def __init__(self, root: SplitModelNode) -> None:
        self._root = root
        self._pane_id_to_parent: dict[str, SplitModelNode] = {}

    def root(self) -> SplitModelNode:
        return self._root

    def _rebuild_pane_id_to_parent(self) -> None:
        """从树结构重建 _pane_id_to_parent。"""
        self._pane_id_to_parent.clear()

        def walk(node: ModelNode, parent: SplitModelNode | None) -> None:
            if isinstance(node, PaneModelNode):
                if parent is not None:
                    self._pane_id_to_parent[node.pane_id] = parent
            elif isinstance(node, SplitModelNode):
                for c in node.children:
                    walk(c, node)

        for c in self._root.children:
            walk(c, self._root)

    def add_pane_to_root(self, pane_id: str) -> None:
        """将 pane_id 对应窗格添加为根的子；若根下已有多个子则均分 sizes。"""
        self._root.children.append(PaneModelNode(pane_id))
        self._pane_id_to_parent[pane_id] = self._root
        if len(self._root.children) >= 2:
            _set_equal_sizes(self._root)
        else:
            self._root.sizes = None

    def find_parent_of_pane_id(self, pane_id: str) -> SplitModelNode | None:
        return self._pane_id_to_parent.get(pane_id)

    def pane_ids(self) -> list[str]:
        return list(self._pane_id_to_parent.keys())

    def get_default_target_pane_id(self) -> str | None:
        ids_list = self.pane_ids()
        return ids_list[0] if ids_list else None

    def _apply_sizes_after_split(
        self,
        parent: SplitModelNode,
        idx: int,
        insert_before: bool,
        ratio: float,
        old_sizes: list[int] | None,
    ) -> None:
        """split 后为 parent 计算并设置 sizes（同向插入时调用）。
        ratio 始终表示新分出那块占该次两块的比重：
        - insert_before: children=[new, old]，new 在前，sizes=[ratio, 1-ratio]
        - insert_before=False: children=[old, new]，new 在后，sizes=[1-ratio, ratio]
        """
        n = len(parent.children)
        if n < 2:
            parent.sizes = None
            return
        M = _SIZE_BASE
        if n == 2:
            # 新窗格占 ratio：insert_before 时新在前，否则新在后
            if insert_before:
                parent.sizes = [int(ratio * M), int((1 - ratio) * M)]
            else:
                parent.sizes = [int((1 - ratio) * M), int(ratio * M)]
        elif (
            old_sizes is not None
            and len(old_sizes) == n - 1
            and 0 <= idx < len(old_sizes)
        ):
            part = old_sizes[idx]
            # part 为原窗格占位，拆成 old 与 new，new 占 ratio
            if insert_before:
                new_first = int(ratio * part)
                new_second = part - new_first
            else:
                new_first = int((1 - ratio) * part)
                new_second = part - new_first
            parent.sizes = (
                old_sizes[:idx] + [new_first, new_second] + old_sizes[idx + 1 :]
            )
        else:
            _set_equal_sizes(parent)

    def split(
        self,
        pane_id: str,
        direction: Qt.Orientation,
        insert_before: bool,
        new_pane_id: str,
        *,
        ratio: float = 0.5,
    ) -> None:
        """同方向时在父下插入新 pane 为兄弟；不同方向时新建 SplitModelNode。sizes 在 model 内计算。"""
        parent = self.find_parent_of_pane_id(pane_id)
        if parent is None:
            idx = _model_index_of(self._root, pane_id)
            if idx >= 0:
                parent = self._root
                self._pane_id_to_parent[pane_id] = parent
            else:
                return
        idx = _model_index_of(parent, pane_id)
        if idx < 0:
            return

        old_sizes = None
        if parent.sizes is not None and len(parent.sizes) == len(parent.children):
            old_sizes = list(parent.sizes)

        new_node = PaneModelNode(new_pane_id)
        if parent.orientation == direction:
            insert_idx = idx if insert_before else idx + 1
            parent.children.insert(insert_idx, new_node)
            self._pane_id_to_parent[new_pane_id] = parent
            self._apply_sizes_after_split(parent, idx, insert_before, ratio, old_sizes)
        else:
            self._split_different_direction(
                parent, pane_id, idx, direction, insert_before, new_pane_id, ratio=ratio
            )
        self.normalize()

    def _split_different_direction(
        self,
        parent: SplitModelNode,
        pane_id: str,
        idx: int,
        direction: Qt.Orientation,
        insert_before: bool,
        new_pane_id: str,
        *,
        ratio: float = 0.5,
    ) -> None:
        old_node = parent.children[idx]
        assert isinstance(old_node, PaneModelNode) and old_node.pane_id == pane_id
        parent.children.pop(idx)
        self._pane_id_to_parent.pop(pane_id, None)
        new_split = SplitModelNode(direction)
        new_pane_node = PaneModelNode(new_pane_id)
        old_pane_node = PaneModelNode(pane_id)
        M = _SIZE_BASE
        if insert_before:
            new_split.children = [new_pane_node, old_pane_node]
            new_split.sizes = [int(ratio * M), int((1 - ratio) * M)]
        else:
            new_split.children = [old_pane_node, new_pane_node]
            new_split.sizes = [int((1 - ratio) * M), int(ratio * M)]
        self._pane_id_to_parent[new_pane_id] = new_split
        self._pane_id_to_parent[pane_id] = new_split
        parent.children.insert(idx, new_split)

    def remove_pane(self, pane_id: str) -> None:
        parent = self.find_parent_of_pane_id(pane_id)
        if parent is None:
            return
        idx = _model_index_of(parent, pane_id)
        if idx < 0:
            return
        # 按剩余子节点维持比例：先从 sizes 中去掉被删子节点对应项，再 pop 子节点
        if (
            parent.sizes is not None
            and len(parent.sizes) == len(parent.children)
            and 0 <= idx < len(parent.sizes)
        ):
            parent.sizes = parent.sizes[:idx] + parent.sizes[idx + 1 :]
        else:
            parent.sizes = None
        parent.children.pop(idx)
        self._pane_id_to_parent.pop(pane_id, None)
        self.normalize()

    def normalize(self) -> None:
        self._normalize_node(self._root, is_root=True)
        self._rebuild_pane_id_to_parent()

    def _normalize_node(self, node: SplitModelNode, is_root: bool) -> None:
        for child in list(node.children):
            if isinstance(child, SplitModelNode):
                self._normalize_node(child, False)

        self._apply_rule3_flatten(node)

        if len(node.children) != 1:
            return

        only_child = node.children[0]
        grandparent = self._find_parent_split(node)

        if isinstance(only_child, SplitModelNode):
            self._apply_rule1_merge(node, only_child, is_root)
            return

        if (
            isinstance(only_child, PaneModelNode)
            and not is_root
            and grandparent is not None
        ):
            if grandparent.orientation != node.orientation:
                self._apply_rule2_promote_pane(node, only_child)

    def _find_parent_split(self, node: SplitModelNode) -> SplitModelNode | None:
        """查找 node 的父 SplitModelNode（仅通过遍历根树）。"""

        def find(
            parent: SplitModelNode, target: SplitModelNode
        ) -> SplitModelNode | None:
            for c in parent.children:
                if c is target:
                    return parent
                if isinstance(c, SplitModelNode):
                    r = find(c, target)
                    if r is not None:
                        return r
            return None

        return find(self._root, node) if node is not self._root else None

    def _apply_rule1_merge(
        self, node: SplitModelNode, only_child: SplitModelNode, is_root: bool
    ) -> None:
        """规则 1：单子且子为 SplitModelNode，合并。"""
        if is_root:
            self._root = only_child
            node.children.clear()
            self._normalize_node(only_child, True)
            return
        grandparent = self._find_parent_split(node)
        if grandparent is None:
            return
        idx = grandparent.children.index(node)
        grandparent.children.pop(idx)
        grandparent.children.insert(idx, only_child)
        node.children.clear()
        self._normalize_node(grandparent, grandparent is self._root)

    def _apply_rule2_promote_pane(
        self, node: SplitModelNode, only_child: PaneModelNode
    ) -> None:
        """规则 2：单子且子为 Pane，且与祖父方向不同，提升到祖父。"""
        grandparent = self._find_parent_split(node)
        if grandparent is None:
            return
        idx = grandparent.children.index(node)
        grandparent.children.pop(idx)
        grandparent.children.insert(idx, only_child)
        node.children.clear()
        self._normalize_node(grandparent, grandparent is self._root)

    def _apply_rule3_flatten(self, node: SplitModelNode) -> None:
        """规则 3：多子中同向 SplitModelNode 展平。展平时重算 sizes，不直接置 None。"""
        old_sizes = (
            node.sizes
            if (node.sizes is not None and len(node.sizes) == len(node.children))
            else None
        )
        i = 0
        while i < len(node.children):
            child = node.children[i]
            if (
                isinstance(child, SplitModelNode)
                and child.orientation == node.orientation
            ):
                if old_sizes is not None:
                    expanded = _expand_sizes_for_flatten(old_sizes[i], child)
                    node.sizes = old_sizes[:i] + expanded + old_sizes[i + 1 :]
                    old_sizes = node.sizes
                node.children.pop(i)
                for j, gc in enumerate(child.children):
                    node.children.insert(i + j, gc)
                i += len(child.children)
                child.children.clear()
            else:
                i += 1
        if old_sizes is None:
            node.sizes = None

    def dump_tree(self) -> list[str]:
        return _model_dump(self._root)

    # 下面都是序列化的相关函数

    def to_dict(self) -> dict:
        """将根节点递归序列化为 JSON 友好 dict。"""
        return _model_node_to_dict(self._root)

    def load_from_dict(self, d: dict) -> None:
        """用 from_dict(d) 得到的根替换当前 _root，并重建 _pane_id_to_parent。"""
        self._root = LayoutTreeModel.from_dict(d)
        self._rebuild_pane_id_to_parent()

    @staticmethod
    def from_dict(d: dict) -> SplitModelNode:
        """从 dict 反序列化出整棵模型树，返回根 SplitModelNode。根必须是 type=='split'。非法结构抛出 ValueError。"""
        root = _dict_to_model_node(d)
        if not isinstance(root, SplitModelNode):
            raise ValueError("layout root must be a split node")
        return root

    @staticmethod
    def pane_ids_from_dict(d: dict) -> list[str]:
        """递归收集 dict 中所有 type=='pane' 的 pane_id，不修改模型。"""
        return _pane_ids_from_dict(d)


def _sizes_to_ratios(sizes: list[int]) -> list[float]:
    """将整数 sizes 转为比例列表，总和为 1.0；total=0 时返回均分。"""
    n = len(sizes)
    if n == 0:
        return []
    total = sum(sizes)
    if total > 0:
        return [s / total for s in sizes]
    return [1.0 / n] * n


def _ratios_to_sizes(ratios: list[float], base: int = _SIZE_BASE) -> list[int]:
    """将比例列表转为整数 sizes，总和为 base；最后一项做舍入修正。"""
    n = len(ratios)
    if n == 0:
        return []
    sizes = [int(r * base) for r in ratios]
    delta = base - sum(sizes)
    if delta != 0 and sizes:
        sizes[-1] += delta
    return sizes


def _model_node_to_dict(node: ModelNode) -> dict:
    if isinstance(node, SplitModelNode):
        orient = "horizontal" if node.orientation == Qt.Horizontal else "vertical"
        out: dict = {
            "type": "split",
            "orientation": orient,
            "children": [_model_node_to_dict(c) for c in node.children],
        }
        if node.sizes is not None and len(node.sizes) == len(node.children):
            out["size_ratios"] = _sizes_to_ratios(node.sizes)
        return out
    else:
        assert isinstance(node, PaneModelNode)
        return {"type": "pane", "pane_id": node.pane_id}


def _dict_to_model_node(d: dict) -> ModelNode:
    if not isinstance(d, dict):
        raise ValueError("layout node must be a dict")
    t = d.get("type")
    if t == "pane":
        pane_id = d.get("pane_id")
        if not isinstance(pane_id, str):
            raise ValueError("pane node must have pane_id: str")
        return PaneModelNode(pane_id)
    if t == "split":
        orient_str = d.get("orientation")
        if orient_str not in ("horizontal", "vertical"):
            raise ValueError(
                "split node must have orientation: 'horizontal' or 'vertical'"
            )
        orientation = Qt.Horizontal if orient_str == "horizontal" else Qt.Vertical
        children_raw = d.get("children")
        if not isinstance(children_raw, list):
            raise ValueError("split node must have children: list")
        children = [_dict_to_model_node(c) for c in children_raw]
        sizes = None
        ratios_raw = d.get("size_ratios")
        if isinstance(ratios_raw, list) and len(ratios_raw) == len(children):
            try:
                ratios = [float(x) for x in ratios_raw]
                if ratios:
                    sizes = _ratios_to_sizes(ratios)
            except (TypeError, ValueError) as e:
                logging.debug(
                    "布局 JSON: size_ratios 解析失败，将尝试 sizes: %s",
                    e,
                    exc_info=True,
                )
        if sizes is None:
            sizes_raw = d.get("sizes")
            if isinstance(sizes_raw, list) and len(sizes_raw) == len(children):
                try:
                    sizes = [int(x) for x in sizes_raw]
                except (TypeError, ValueError) as e:
                    logging.debug(
                        "布局 JSON: sizes 解析失败，使用默认拆分比例: %s",
                        e,
                        exc_info=True,
                    )
        return SplitModelNode(orientation, children, sizes=sizes)
    raise ValueError("layout node must have type: 'split' or 'pane'")


def _pane_ids_from_dict(d: dict) -> list[str]:
    if not isinstance(d, dict):
        return []
    if d.get("type") == "pane":
        pid = d.get("pane_id")
        return [pid] if isinstance(pid, str) else []
    if d.get("type") == "split":
        children = d.get("children") if isinstance(d.get("children"), list) else []
        result = []
        for c in children:
            result.extend(_pane_ids_from_dict(c))
        return result
    return []


# -------- LayoutRenderer（模型 → QSplitter 视图）--------


class LayoutRenderer:
    """根据 LayoutTreeModel 构建 QSplitter 树；不持有 PaneWidget，仅通过 get_widget(pane_id) 获取。"""

    def __init__(
        self,
        model: LayoutTreeModel,
        get_widget: Callable[[str], PaneWidget],
        style_splitter: Callable[[QSplitter], None] | None = None,
        on_root_replaced: Callable[[QWidget, QWidget], None] | None = None,
    ) -> None:
        self._model = model
        self._get_widget = get_widget
        self._style_splitter = style_splitter
        self._on_root_replaced = on_root_replaced
        self._root_widget: QWidget | None = None
        self._pane_id_to_parent_splitter: dict[str, QSplitter] = {}
        self._pane_id_to_index: dict[str, int] = {}
        self._splitter_to_node: dict[QSplitter, SplitModelNode] = {}

    def sync(self) -> None:
        """根据 model 全量重建 QSplitter 树；若根 widget 发生替换则调用 on_root_replaced。"""
        old_root = self._root_widget
        self._pane_id_to_parent_splitter.clear()
        self._pane_id_to_index.clear()
        self._splitter_to_node.clear()
        root_model = self._model.root()
        if not root_model.children:
            new_root = QSplitter(root_model.orientation)
            if self._style_splitter:
                self._style_splitter(new_root)
            self._root_widget = new_root
        else:
            self._root_widget = self._build_splitter(root_model)
        if (
            old_root is not None
            and old_root is not self._root_widget
            and self._on_root_replaced
        ):
            self._on_root_replaced(old_root, self._root_widget)

    def _build_splitter(self, node: SplitModelNode) -> QSplitter:
        splitter = QSplitter(node.orientation)
        if self._style_splitter:
            self._style_splitter(splitter)
        for i, child in enumerate(node.children):
            if isinstance(child, PaneModelNode):
                w = self._get_widget(child.pane_id)
                if w is not None:
                    splitter.addWidget(w)
                    w.show()
                    self._pane_id_to_parent_splitter[child.pane_id] = splitter
                    self._pane_id_to_index[child.pane_id] = i
            else:
                sub = self._build_splitter(child)
                splitter.addWidget(sub)
                sub.show()
        self._splitter_to_node[splitter] = node
        if splitter.count() >= 2:
            if node.sizes is not None and len(node.sizes) == splitter.count():
                splitter.setSizes(node.sizes)
            else:
                n = splitter.count()
                default_sizes = [9999] * n
                splitter.setSizes(default_sizes)
                # 仅当视图子节点数与 model 一致时写回，避免部分 pane 未注册导致 model 与 children 长度不一致
                if n == len(node.children):
                    node.sizes = default_sizes
            splitter.splitterMoved.connect(
                lambda pos, idx, s=splitter: self._on_splitter_moved(s)
            )
        return splitter

    def _on_splitter_moved(self, splitter: QSplitter) -> None:
        """用户拖动 splitter 时，将当前 sizes 写回对应 SplitModelNode。"""
        node = self._splitter_to_node.get(splitter)
        if node is not None and splitter.count() >= 2:
            node.sizes = list(splitter.sizes())

    def root_widget(self) -> QWidget:
        """当前根 widget（QSplitter）；sync 前可能为 None，调用方应在首次 sync 后使用。"""
        if self._root_widget is None:
            self.sync()
        assert self._root_widget is not None
        return self._root_widget

    def get_parent_splitter(self, pane_id: str) -> QSplitter | None:
        return self._pane_id_to_parent_splitter.get(pane_id)

    def get_index_in_parent(self, pane_id: str) -> int:
        return self._pane_id_to_index.get(pane_id, -1)


# -------- LayoutTree 门面（Model + Renderer + 注册表，保持对外 API）--------


class LayoutTree:
    """布局树门面：持有 Model + Renderer + pane 注册表，对外 API 与旧版兼容。"""

    def __init__(
        self,
        root: SplitModelNode,
        style_splitter: Callable[[QSplitter], None] | None = None,
        on_root_replaced: Callable[[QWidget, QWidget], None] | None = None,
    ) -> None:
        self._model = LayoutTreeModel(root)
        self._pane_id_to_widget: dict[str, PaneWidget] = {}
        self._renderer = LayoutRenderer(
            self._model,
            get_widget=lambda pid: self._pane_id_to_widget.get(pid),
            style_splitter=style_splitter,
            on_root_replaced=on_root_replaced,
        )
        self._renderer.sync()

    def root(self) -> QWidget:
        """根 widget（QSplitter）；直接返回 renderer 的根。"""
        return self._renderer.root_widget()

    def dump_tree(self) -> list[str]:
        return self._model.dump_tree()

    def print_tree(self) -> None:
        for line in self.dump_tree():
            print(line)
        print("---")

    def find_parent_of_pane(self, pane: PaneWidget) -> QSplitter | None:
        """pane 所在父节点，直接返回 QSplitter；若在根下则返回该 QSplitter。"""
        return self._renderer.get_parent_splitter(pane.pane_id)

    def register_pane_parent(self, pane: PaneWidget, parent: object = None) -> None:
        self._pane_id_to_widget[pane.pane_id] = pane

    def unregister_pane(self, pane: PaneWidget) -> None:
        self._pane_id_to_widget.pop(pane.pane_id, None)

    def find_pane_by_id(self, pane_id: str) -> PaneWidget | None:
        return self._pane_id_to_widget.get(pane_id)

    def panes(self) -> list[PaneWidget]:
        return list(self._pane_id_to_widget.values())

    def get_default_target_pane(self) -> PaneWidget | None:
        lst = self.panes()
        return lst[0] if lst else None

    def add_pane_to_root(self, pane: PaneWidget) -> None:
        self._model.add_pane_to_root(pane.pane_id)
        self.register_pane_parent(pane)
        self._renderer.sync()

    def split(
        self,
        pane: PaneWidget,
        direction: Qt.Orientation,
        insert_before: bool,
        new_pane: PaneWidget,
        *,
        ratio: float = 0.5,
    ) -> None:
        self._model.split(
            pane.pane_id, direction, insert_before, new_pane.pane_id, ratio=ratio
        )
        self.register_pane_parent(new_pane)
        self._renderer.sync()

    def remove_pane(self, pane: PaneWidget) -> None:
        """从布局中移除窗格并安排析构。调用后调用方不得再使用该 pane 的引用（pane 已 deleteLater）。"""
        self.unregister_pane(pane)
        self._model.remove_pane(pane.pane_id)
        pane.setParent(None)  # 从旧树摘出，避免 sync 替换根时随旧根被析构
        self._renderer.sync()
        pane.deleteLater()

    @staticmethod
    def load_layout_file(path: str | Path) -> dict:
        """从 path 读取布局 JSON 并返回 dict，不修改当前实例。"""
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def to_dict(self) -> dict:
        """返回当前布局模型的 JSON 友好 dict（用于与 pane_contents 等合并后保存）。"""
        return self._model.to_dict()

    def apply_layout(self, d: dict) -> None:
        """用 dict 替换当前模型并 sync。调用前需保证布局中所有 pane_id 已通过 register_pane_parent 注册。"""
        self._model.load_from_dict(d)
        self._renderer.sync()

    def load_layout_from_dict(
        self,
        layout_dict: dict,
        pane_factory: Callable[[str], PaneWidget],
    ) -> None:
        """从 layout_dict 加载布局（不读文件）。用于已解析的 dict，支持 layout 在根或 data['layout'] 中。"""
        for pid in LayoutTreeModel.pane_ids_from_dict(layout_dict):
            pane = pane_factory(pid)
            self.register_pane_parent(pane)
        self.apply_layout(layout_dict)

    def save_layout(self, path: str | Path) -> None:
        """将当前布局模型序列化为 JSON 并写入 path。"""
        path = Path(path)
        data = self._model.to_dict()
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_layout(
        self,
        path: str | Path,
        pane_factory: Callable[[str], PaneWidget],
    ) -> None:
        """一步加载：读文件 → 按 pane_ids 创建并注册 pane → 应用布局。pane_factory(pid) 应返回 pane_id=pid 的 PaneWidget。"""
        d = LayoutTree.load_layout_file(path)
        for pid in LayoutTreeModel.pane_ids_from_dict(d):
            pane = pane_factory(pid)
            self.register_pane_parent(pane)
        self.apply_layout(d)
