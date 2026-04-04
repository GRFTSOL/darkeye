"""core.graph.graph_filter：过滤器语义（必要时绕过 core/__init__）。"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path

import networkx as nx
import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_GRAPH_FILTER = "core.graph.graph_filter"


def _get_graph_filter_module():
    if _GRAPH_FILTER in sys.modules:
        return sys.modules[_GRAPH_FILTER]

    core_mod = sys.modules.get("core")
    real_core = core_mod is not None and getattr(core_mod, "__file__", None)
    if real_core:
        return importlib.import_module(_GRAPH_FILTER)

    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = [str(_ROOT / "core")]
    sys.modules["core"] = core_pkg
    gpkg = types.ModuleType("core.graph")
    gpkg.__path__ = [str(_ROOT / "core" / "graph")]
    sys.modules["core.graph"] = gpkg

    spec = importlib.util.spec_from_file_location(
        _GRAPH_FILTER,
        _ROOT / "core" / "graph" / "graph_filter.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_GRAPH_FILTER] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gf():
    return _get_graph_filter_module()


def test_empty_filter_excludes_all(gf):
    g = nx.path_graph(["a", "b", "c"])
    flt = gf.EmptyFilter()
    assert not flt.filter_node(g, "a")
    assert not flt.filter_edge(g, "a", "b")


def test_pass_through_includes_all(gf):
    g = nx.path_graph(["a", "b"])
    flt = gf.PassThroughFilter()
    assert flt.filter_node(g, "a") and flt.filter_node(g, "b")
    assert flt.filter_edge(g, "a", "b")


def test_ego_filter_radius_one(gf):
    g = nx.Graph()
    g.add_edges_from([("A", "B"), ("B", "C")])
    flt = gf.EgoFilter("A", radius=1)
    assert flt.filter_node(g, "A") and flt.filter_node(g, "B")
    assert not flt.filter_node(g, "C")
    assert flt.filter_edge(g, "A", "B")
    assert not flt.filter_edge(g, "B", "C")


def test_ego_filter_missing_center_is_empty(gf):
    g = nx.path_graph(["X", "Y"])
    flt = gf.EgoFilter("no-such", radius=2)
    assert not flt.filter_node(g, "X")
    assert not flt.filter_edge(g, "X", "Y")


def test_ego_filter_radius_one_on_path_excludes_distant_leaf(gf):
    g = nx.path_graph(["A", "B", "C", "D"])
    flt = gf.EgoFilter("B", radius=1)
    assert flt.filter_node(g, "A")
    assert flt.filter_node(g, "B")
    assert flt.filter_node(g, "C")
    assert not flt.filter_node(g, "D")
