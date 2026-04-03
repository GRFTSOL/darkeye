"""测试 layout_tree 中 LayoutTreeModel、LayoutRenderer 与 LayoutTree 门面的正确性。"""

import sys
import tempfile
from pathlib import Path

root_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.demo.layout_tree import (
    SplitModelNode,
    PaneModelNode,
    LayoutTreeModel,
    LayoutRenderer,
    LayoutTree,
)
from ui.demo.pane_widget import PaneWidget


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# -------- LayoutTreeModel 测试（纯数据，无需 Qt）--------


def test_model_add_pane_to_root():
    """add_pane_to_root 将 pane_id 加入根并更新索引。"""
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("p1")
    assert len(root.children) == 1
    assert (
        isinstance(root.children[0], PaneModelNode) and root.children[0].pane_id == "p1"
    )
    assert model.find_parent_of_pane_id("p1") is root
    assert model.pane_ids() == ["p1"]
    assert model.get_default_target_pane_id() == "p1"


def test_model_split_same_direction():
    """同方向 split 在父下插入兄弟。"""
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("p1")
    model.split("p1", Qt.Horizontal, insert_before=False, new_pane_id="p2")
    assert len(root.children) == 2
    assert root.children[0].pane_id == "p1" and root.children[1].pane_id == "p2"
    assert model.find_parent_of_pane_id("p1") is root
    assert model.find_parent_of_pane_id("p2") is root
    assert set(model.pane_ids()) == {"p1", "p2"}


def test_model_split_different_direction():
    """不同方向 split 新建 SplitModelNode；normalize 后单子 Split 会提升为根。"""
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("p1")
    assert len(root.children) == 1
    model.split("p1", Qt.Vertical, insert_before=True, new_pane_id="p2")
    # normalize 会将单子 Split 合并：原根(H)下唯一的 Vertical Split 提升为新根
    inner = model.root()
    assert isinstance(inner, SplitModelNode) and inner.orientation == Qt.Vertical
    assert len(inner.children) == 2
    assert inner.children[0].pane_id == "p2" and inner.children[1].pane_id == "p1"
    assert model.find_parent_of_pane_id("p1") is inner
    assert model.find_parent_of_pane_id("p2") is inner


def test_model_remove_pane():
    """remove_pane 从树中移除并规范化。"""
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("p1")
    model.split("p1", Qt.Horizontal, insert_before=False, new_pane_id="p2")
    model.remove_pane("p2")
    assert len(root.children) == 1
    assert root.children[0].pane_id == "p1"
    assert "p2" not in model.pane_ids()
    assert model.get_default_target_pane_id() == "p1"


def test_model_normalize_merge_single_split():
    """规则 1：单子且子为 SplitModelNode 时合并。"""
    root = SplitModelNode(Qt.Horizontal, [])
    inner = SplitModelNode(Qt.Vertical, [PaneModelNode("p1"), PaneModelNode("p2")])
    root.children.append(inner)
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    model.normalize()
    assert model.root() is inner
    assert len(inner.children) == 2
    assert model.find_parent_of_pane_id("p1") is inner
    assert model.find_parent_of_pane_id("p2") is inner


def test_model_normalize_flatten_same_direction():
    """规则 3：同向 SplitModelNode 展平。"""
    root = SplitModelNode(Qt.Horizontal, [])
    root.children.append(PaneModelNode("p1"))
    inner = SplitModelNode(Qt.Horizontal, [PaneModelNode("p2"), PaneModelNode("p3")])
    root.children.append(inner)
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    model.normalize()
    assert len(root.children) == 3
    assert [
        c.pane_id if isinstance(c, PaneModelNode) else None for c in root.children
    ] == ["p1", "p2", "p3"]


def test_model_dump_tree():
    """dump_tree 输出模型树结构。"""
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("a")
    lines = model.dump_tree()
    assert any("Split" in l for l in lines)
    assert any("Pane(id=a)" in l or "id=a" in l for l in lines)


# -------- LayoutRenderer 测试（需要 QApplication）--------


def test_renderer_sync_builds_root():
    """sync 后 root_widget 为 QSplitter。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("p1")
    widgets = {"p1": PaneWidget(pane_id="p1")}
    renderer = LayoutRenderer(model, get_widget=lambda pid: widgets.get(pid))
    renderer.sync()
    from PySide6.QtWidgets import QSplitter

    assert isinstance(renderer.root_widget(), QSplitter)
    assert renderer.root_widget().count() == 1
    assert renderer.get_parent_splitter("p1") is renderer.root_widget()


def test_renderer_get_parent_splitter():
    """get_parent_splitter 返回对应 pane 的父 QSplitter。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    model.add_pane_to_root("p1")
    model.split("p1", Qt.Horizontal, insert_before=False, new_pane_id="p2")
    widgets = {"p1": PaneWidget(pane_id="p1"), "p2": PaneWidget(pane_id="p2")}
    renderer = LayoutRenderer(model, get_widget=lambda pid: widgets.get(pid))
    renderer.sync()
    sp = renderer.get_parent_splitter("p1")
    assert sp is not None and sp == renderer.get_parent_splitter("p2")
    assert sp.count() == 2


# -------- LayoutTree 门面测试 --------


def test_layout_tree_register_find_pane():
    """register_pane_parent / unregister_pane / find_parent_of_pane / find_pane_by_id。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="id-1")
    p2 = PaneWidget(pane_id="id-2")
    tree.add_pane_to_root(p1)
    tree.add_pane_to_root(p2)

    parent1 = tree.find_parent_of_pane(p1)
    parent2 = tree.find_parent_of_pane(p2)
    assert parent1 is not None and parent2 is not None
    assert tree.find_pane_by_id("id-1") is p1
    assert tree.find_pane_by_id("id-2") is p2
    assert tree.find_pane_by_id("none") is None

    tree.unregister_pane(p1)
    tree.remove_pane(p1)
    assert tree.find_pane_by_id("id-1") is None
    assert tree.find_pane_by_id("id-2") is p2


def test_layout_tree_add_pane_to_root():
    """add_pane_to_root 将 pane 作为根的唯一子并注册。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p = PaneWidget(pane_id="root-pane")

    tree.add_pane_to_root(p)

    assert tree._model.root().children
    assert tree._model.root().children[0].pane_id == "root-pane"
    assert tree.find_parent_of_pane(p) is not None
    assert tree.find_pane_by_id("root-pane") is p


def test_layout_tree_split_insert_before():
    """同向 split insert_before=True 时新 pane 在原 pane 前。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    tree.add_pane_to_root(p1)
    p2 = PaneWidget(pane_id="p2")
    tree.split(p1, Qt.Horizontal, insert_before=True, new_pane=p2)

    assert len(tree._model.root().children) == 2
    assert tree._model.root().children[0].pane_id == "p2"
    assert tree._model.root().children[1].pane_id == "p1"
    assert tree.find_parent_of_pane(p1) is not None
    assert tree.find_parent_of_pane(p2) is not None
    assert tree.find_pane_by_id("p1") is p1 and tree.find_pane_by_id("p2") is p2


def test_layout_tree_split_insert_after():
    """同向 split insert_before=False 时新 pane 在后。"""
    _ensure_app()
    root = SplitModelNode(Qt.Vertical, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    tree.add_pane_to_root(p1)
    p2 = PaneWidget(pane_id="p2")
    tree.split(p1, Qt.Vertical, insert_before=False, new_pane=p2)

    assert len(tree._model.root().children) == 2
    assert tree._model.root().children[0].pane_id == "p1"
    assert tree._model.root().children[1].pane_id == "p2"


def test_layout_tree_remove_pane_collapse():
    """remove_pane 后若根只剩 1 子，保持根 + 单子。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    p2 = PaneWidget(pane_id="p2")
    tree.add_pane_to_root(p1)
    tree.split(p1, Qt.Horizontal, insert_before=False, new_pane=p2)

    tree.remove_pane(p2)

    assert len(tree._model.root().children) == 1
    assert tree._model.root().children[0].pane_id == "p1"
    assert tree.find_parent_of_pane(p1) is not None
    assert tree.find_pane_by_id("p1") is p1
    assert tree.find_pane_by_id("p2") is None


def test_layout_tree_remove_pane_no_collapse():
    """remove_pane 后若父仍有 2+ 子，不折叠。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    p2 = PaneWidget(pane_id="p2")
    p3 = PaneWidget(pane_id="p3")
    tree.add_pane_to_root(p1)
    tree.split(p1, Qt.Horizontal, insert_before=False, new_pane=p2)
    tree.split(p2, Qt.Horizontal, insert_before=False, new_pane=p3)

    tree.remove_pane(p3)

    assert len(tree._model.root().children) == 2
    assert tree.find_parent_of_pane(p1) is not None
    assert tree.find_parent_of_pane(p2) is not None


def test_layout_tree_remove_pane_promote_root():
    """删除唯一 Pane 后若产生单子 Split，合并后根替换并触发 on_root_replaced。"""
    _ensure_app()
    root = SplitModelNode(Qt.Vertical, [])
    tree = LayoutTree(root)
    p3 = PaneWidget(pane_id="p3")
    tree.add_pane_to_root(p3)
    p2 = PaneWidget(pane_id="p2")
    tree.split(p3, Qt.Vertical, insert_before=True, new_pane=p2)
    p4 = PaneWidget(pane_id="p4")
    tree.split(p2, Qt.Horizontal, insert_before=False, new_pane=p4)

    tree.remove_pane(p3)

    assert tree._model.root().orientation == Qt.Horizontal
    assert len(tree._model.root().children) == 2
    assert (
        tree._model.root().children[0].pane_id == "p2"
        and tree._model.root().children[1].pane_id == "p4"
    )
    assert tree.find_parent_of_pane(p2) is not None
    assert tree.find_parent_of_pane(p4) is not None
    assert tree.find_pane_by_id("p3") is None


def test_layout_tree_split_uses_registered_parent():
    """split 时 pane 在根下（通过 add_pane_to_root 已注册）可正确 split。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    tree.add_pane_to_root(p1)
    p2 = PaneWidget(pane_id="p2")
    tree.split(p1, Qt.Horizontal, insert_before=True, new_pane=p2)

    assert len(tree._model.root().children) == 2
    assert tree._model.root().children[0].pane_id == "p2"
    assert tree._model.root().children[1].pane_id == "p1"
    assert tree.find_parent_of_pane(p1) is not None
    assert tree.find_parent_of_pane(p2) is not None


def test_normalize_merge_single_split_child():
    """规则 1：单子且子为 Split 时合并，根替换。"""
    root = SplitModelNode(Qt.Horizontal, [])
    inner = SplitModelNode(Qt.Vertical, [PaneModelNode("p1"), PaneModelNode("p2")])
    root.children.append(inner)
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    model.normalize()

    assert model.root() is inner
    assert len(inner.children) == 2
    assert model.find_parent_of_pane_id("p1") is inner
    assert model.find_parent_of_pane_id("p2") is inner


def test_normalize_flatten_same_direction():
    """规则 3：同向 Split 展平为 N-ary。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    root.children.append(PaneModelNode("p1"))
    inner = SplitModelNode(Qt.Horizontal, [PaneModelNode("p2"), PaneModelNode("p3")])
    root.children.append(inner)
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    model.normalize()

    assert len(root.children) == 3
    assert [c.pane_id for c in root.children if isinstance(c, PaneModelNode)] == [
        "p1",
        "p2",
        "p3",
    ]


# -------- PaneWidget 在树中的显示测试 --------


def test_layout_tree_find_parent_has_splitter_and_children():
    """find_parent_of_pane 直接返回 QSplitter，可读 count 与 widget(i)。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    p2 = PaneWidget(pane_id="p2")
    tree.add_pane_to_root(p1)
    tree.split(p1, Qt.Horizontal, insert_before=False, new_pane=p2)

    parent = tree.find_parent_of_pane(p1)
    assert parent is not None
    assert parent.count() == 2
    idx_p1 = next((i for i in range(parent.count()) if parent.widget(i) is p1), -1)
    idx_p2 = next((i for i in range(parent.count()) if parent.widget(i) is p2), -1)
    assert idx_p1 in (0, 1) and idx_p2 in (0, 1)


def test_layout_tree_pane_displayed_in_window():
    """LayoutTree 的根作为窗口 centralWidget 时，add_pane_to_root 的 PaneWidget 显示正确。"""
    _ensure_app()
    from PySide6.QtWidgets import QMainWindow

    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p = PaneWidget(pane_id="display-test")
    tree.add_pane_to_root(p)

    win = QMainWindow()
    win.setCentralWidget(tree.root())
    win.resize(400, 300)
    win.show()
    QApplication.processEvents()

    assert p.parent() is not None
    assert tree.find_pane_by_id("display-test") is p
    assert p.isVisible()
    assert p.size().width() > 0 and p.size().height() > 0


def test_layout_tree_split_panes_displayed_in_window():
    """split 后两个 PaneWidget 均在窗口中正确显示。"""
    _ensure_app()
    from PySide6.QtWidgets import QMainWindow

    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="p1")
    tree.add_pane_to_root(p1)
    p2 = PaneWidget(pane_id="p2")
    tree.split(p1, Qt.Horizontal, insert_before=False, new_pane=p2)

    win = QMainWindow()
    win.setCentralWidget(tree.root())
    win.resize(500, 300)
    win.show()
    QApplication.processEvents()

    for pane in (p1, p2):
        assert pane.isVisible()
        assert pane.size().width() > 0 and pane.size().height() > 0


# -------- 布局序列化测试 --------


def test_model_to_dict_single_pane():
    """单 pane 时 to_dict 与 from_dict 往返一致。"""
    root = SplitModelNode(Qt.Horizontal, [PaneModelNode("p1")])
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    d = model.to_dict()
    assert d["type"] == "split"
    assert d["orientation"] == "horizontal"
    assert len(d["children"]) == 1
    assert d["children"][0] == {"type": "pane", "pane_id": "p1"}
    root2 = LayoutTreeModel.from_dict(d)
    assert isinstance(root2, SplitModelNode)
    assert root2.orientation == Qt.Horizontal
    assert len(root2.children) == 1 and root2.children[0].pane_id == "p1"


def test_model_to_dict_two_panes():
    """两 pane 水平排列往返。"""
    root = SplitModelNode(Qt.Horizontal, [PaneModelNode("a"), PaneModelNode("b")])
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    d = model.to_dict()
    assert d["type"] == "split" and d["orientation"] == "horizontal"
    assert [c.get("pane_id") for c in d["children"]] == ["a", "b"]
    root2 = LayoutTreeModel.from_dict(d)
    assert len(root2.children) == 2
    assert root2.children[0].pane_id == "a" and root2.children[1].pane_id == "b"


def test_model_to_dict_nested_split():
    """多层 split 往返。"""
    inner = SplitModelNode(Qt.Vertical, [PaneModelNode("p1"), PaneModelNode("p2")])
    root = SplitModelNode(Qt.Horizontal, [inner, PaneModelNode("p3")])
    model = LayoutTreeModel(root)
    model._rebuild_pane_id_to_parent()
    d = model.to_dict()
    assert d["type"] == "split" and d["orientation"] == "horizontal"
    assert len(d["children"]) == 2
    assert (
        d["children"][0]["type"] == "split"
        and d["children"][0]["orientation"] == "vertical"
    )
    assert [c["pane_id"] for c in d["children"][0]["children"]] == ["p1", "p2"]
    assert d["children"][1]["type"] == "pane" and d["children"][1]["pane_id"] == "p3"
    root2 = LayoutTreeModel.from_dict(d)
    assert len(root2.children) == 2
    assert isinstance(root2.children[0], SplitModelNode)
    assert root2.children[0].orientation == Qt.Vertical
    assert [c.pane_id for c in root2.children[0].children] == ["p1", "p2"]
    assert root2.children[1].pane_id == "p3"


def test_model_load_from_dict():
    """load_from_dict 后 pane_ids() 与结构正确。"""
    root = SplitModelNode(Qt.Horizontal, [])
    model = LayoutTreeModel(root)
    d = {
        "type": "split",
        "orientation": "vertical",
        "children": [
            {"type": "pane", "pane_id": "x"},
            {"type": "pane", "pane_id": "y"},
        ],
    }
    model.load_from_dict(d)
    assert set(model.pane_ids()) == {"x", "y"}
    r = model.root()
    assert r.orientation == Qt.Vertical
    assert (
        len(r.children) == 2
        and r.children[0].pane_id == "x"
        and r.children[1].pane_id == "y"
    )


def test_model_pane_ids_from_dict():
    """pane_ids_from_dict 递归收集所有 pane_id。"""
    d = {
        "type": "split",
        "orientation": "horizontal",
        "children": [
            {"type": "pane", "pane_id": "a"},
            {
                "type": "split",
                "orientation": "vertical",
                "children": [
                    {"type": "pane", "pane_id": "b"},
                    {"type": "pane", "pane_id": "c"},
                ],
            },
        ],
    }
    ids = LayoutTreeModel.pane_ids_from_dict(d)
    assert set(ids) == {"a", "b", "c"}


def test_model_from_dict_root_must_be_split():
    """根为 pane 时 from_dict 抛出 ValueError。"""
    d = {"type": "pane", "pane_id": "only"}
    try:
        LayoutTreeModel.from_dict(d)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "split" in str(e).lower() or "root" in str(e).lower()


def test_model_from_dict_pane_must_have_pane_id():
    """pane 节点缺少 pane_id 或非字符串时抛出。"""
    d = {"type": "split", "orientation": "horizontal", "children": [{"type": "pane"}]}
    try:
        LayoutTreeModel.from_dict(d)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_model_from_dict_invalid_type():
    """非法 type 抛出 ValueError。"""
    d = {"type": "unknown", "orientation": "horizontal", "children": []}
    try:
        LayoutTreeModel.from_dict(d)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_layout_tree_save_and_load_file():
    """save_layout 写文件，load_layout_file 读回相同 dict；apply_layout 后结构一致。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    p1 = PaneWidget(pane_id="pa")
    p2 = PaneWidget(pane_id="pb")
    tree.add_pane_to_root(p1)
    tree.split(p1, Qt.Horizontal, insert_before=False, new_pane=p2)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        tree.save_layout(path)
        d = LayoutTree.load_layout_file(path)
        assert d["type"] == "split"
        assert set(LayoutTreeModel.pane_ids_from_dict(d)) == {"pa", "pb"}
        # 同一 tree 应用读回的布局（panes 已注册）
        tree.apply_layout(d)
        assert set(tree._model.pane_ids()) == {"pa", "pb"}
        assert len(tree._model.root().children) == 2
    finally:
        Path(path).unlink(missing_ok=True)


def test_layout_tree_load_layout_with_factory():
    """load_layout(path, pane_factory) 读文件、创建并注册 panes、应用布局。"""
    _ensure_app()
    root = SplitModelNode(Qt.Horizontal, [])
    tree = LayoutTree(root)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        layout_dict = {
            "type": "split",
            "orientation": "vertical",
            "children": [
                {"type": "pane", "pane_id": "load_a"},
                {"type": "pane", "pane_id": "load_b"},
            ],
        }
        import json

        with open(path, "w", encoding="utf-8") as out:
            json.dump(layout_dict, out, indent=2)
        created = []

        def factory(pid):
            p = PaneWidget(pane_id=pid)
            created.append(p)
            return p

        tree.load_layout(path, pane_factory=factory)
        assert len(created) == 2
        assert set(p.pane_id for p in created) == {"load_a", "load_b"}
        assert tree.find_pane_by_id("load_a") is not None
        assert tree.find_pane_by_id("load_b") is not None
        assert set(tree._model.pane_ids()) == {"load_a", "load_b"}
        assert len(tree._model.root().children) == 2
    finally:
        Path(path).unlink(missing_ok=True)


def run_manual():
    """命令行运行：执行所有测试并打印结果。"""
    _ensure_app()
    mod = sys.modules[__name__]
    tests = [
        getattr(mod, n)
        for n in dir(mod)
        if n.startswith("test_") and callable(getattr(mod, n))
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except Exception as e:
            failed.append((t.__name__, e))
            print(f"  FAIL {t.__name__}: {e}")
    if failed:
        print(f"\n失败: {len(failed)}/{len(tests)}")
        return 1
    print(f"\n全部通过: {len(tests)}")
    return 0


if __name__ == "__main__":
    sys.exit(run_manual())
