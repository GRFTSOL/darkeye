from PySide6.QtCore import QObject, Signal
import networkx as nx
from .graph_manager import GraphManager
from .graph_filter import GraphFilter, PassThroughFilter, EgoFilter


def _radius_from_degree(
    degrees: dict, node_id, min_deg: float, max_deg: float
) -> float:
    """根据度数重映射到半径 [4, 10]，与 ForceDirectedViewWidget._set_graph_from_networkx 一致"""
    deg = float(degrees.get(node_id, 1))
    if max_deg <= min_deg:
        return 7.0
    t = (deg - min_deg) / (max_deg - min_deg)
    return 4.0 + t * 6.0


class GraphViewSession(QObject):
    """
    （每个视图一个，会话/过滤层）
    初始化计算子图
    拿全局 G，根据当前 filter（GraphFilter 派生类）计算子图 sub_G。
    将全局 diff 按当前 filter 进行裁剪/转换，得到会话内子图的增量 diff，然后发给 UI。
    """

    dataReady = Signal(dict)  # 发射这个信号用于产生新的图，刷新全图
    # 增量 diff：实际发射的是 list[dict]（见 _on_global_diff / fast_calc_diff）
    diffChanged = Signal(list)  # 这个信号用于增量加点，不改变视口范围

    def __init__(self):
        super().__init__()
        self._filter: GraphFilter = PassThroughFilter()
        self.manager = GraphManager.instance()
        self.manager.graphDiffSignal.connect(self._on_global_diff)

        self.sub_G = None

    def set_filter(self, new_filter: GraphFilter):
        """设置一个新的过滤器"""
        self._filter = new_filter

    def apply_filter(self, G: nx.Graph) -> nx.Graph:
        """应用过滤器，返回新的子图"""
        sub_G = nx.Graph()
        # 1. Filter Nodes
        valid_nodes = set()
        for n in G.nodes():
            if self._filter.filter_node(G, n):
                # Copy node attributes
                sub_G.add_node(n, **G.nodes[n])
                valid_nodes.add(n)

        # 2. Filter Edges
        # Only include edges where both endpoints are valid
        for u, v in G.edges():
            if u in valid_nodes and v in valid_nodes:
                if self._filter.filter_edge(G, u, v):
                    # Copy edge attributes
                    sub_G.add_edge(u, v, **G.edges[u, v])

        return sub_G

    def fast_calc_diff(self, new_deepth: int) -> list:
        """
        对于以中心为过滤的视图，在变化过滤距离时的快速算法
        计算旧半径和新半径之间的增量差异，避免重新计算整个子图

        Args:
            new_deepth: 新的半径深度

        Returns:
            增量操作列表，格式与 _on_global_diff 中的 diff_list 一致
        """
        diff_list = []

        # 边界情况检查
        if not isinstance(self._filter, EgoFilter):
            # 不是 EgoFilter，不支持快速计算
            print("不是 EgoFilter，不支持快速计算")
            return diff_list

        if self.sub_G is None:
            # 子图未初始化
            return diff_list

        # 获取全局图
        G = self.manager.G
        if G is None:
            return diff_list

        # 检查中心节点是否在图中
        if self._filter.center_id not in G:
            return diff_list

        # 深度比较
        old_radius = self._filter.radius
        if new_deepth == old_radius:
            # 深度没有变化，返回空列表
            return diff_list

        # 计算新半径的节点集合
        new_ego_graph = nx.ego_graph(G, self._filter.center_id, radius=new_deepth)
        new_nodes = set(new_ego_graph.nodes())

        # 获取旧子图的节点集合
        old_nodes = set(self.sub_G.nodes())

        # 计算节点差异
        # 新增的节点：在新图中但不在旧图中
        added_nodes = new_nodes - old_nodes
        degrees = dict(new_ego_graph.degree())
        deg_values = list(degrees.values()) or [1]
        min_deg = min(deg_values)
        max_deg = max(deg_values)
        for node_id in added_nodes:
            if node_id in G.nodes():
                attr = dict(G.nodes[node_id])
                attr["radius"] = _radius_from_degree(degrees, node_id, min_deg, max_deg)
                diff_list.append({"op": "add_node", "id": node_id, "attr": attr})

        # 删除的节点：在旧图中但不在新图中
        removed_nodes = old_nodes - new_nodes
        for node_id in removed_nodes:
            diff_list.append({"op": "del_node", "id": node_id})

        # 计算边差异
        # 新增的边：在新子图中但不在旧子图中的边
        for u, v in new_ego_graph.edges():
            if u in new_nodes and v in new_nodes:
                if not self.sub_G.has_edge(u, v):
                    edge_attr = {}
                    if G.has_edge(u, v):
                        edge_attr = dict(G.edges[u, v])
                    diff_list.append(
                        {"op": "add_edge", "u": u, "v": v, "attr": edge_attr}
                    )

        # 删除的边：在旧子图中但至少一端不在新节点集合中的边
        for u, v in self.sub_G.edges():
            if u not in new_nodes or v not in new_nodes:
                diff_list.append({"op": "del_edge", "u": u, "v": v})

        # 更新状态（用反射改半径并清除 filter 缓存，使 apply_filter 按新半径重算）
        setattr(self._filter, "radius", new_deepth)
        if hasattr(self._filter, "_valid_nodes"):
            setattr(self._filter, "_valid_nodes", None)
        self.sub_G = self.apply_filter(G)
        print(diff_list)
        self.diffChanged.emit(diff_list)

    def new_load(self):
        """全新的加载，后面的图是刷新式的，意味着所有点与边的位置都变了"""
        G = self.manager.G
        if G is None:
            return

        # 与 DB 同步：去掉已软删作品，避免仅 new_load 时仍用内存里的旧节点
        self.manager.prune_soft_deleted_work_nodes(emit_diff=False)

        self.sub_G = self.apply_filter(G)

        self.dataReady.emit({"cmd": "load_graph", "graph": self.sub_G, "modify": False})

    def _on_global_diff(self, global_diff_list: list):
        """增量加载，后面的图是增量式的，原来的点与边保持不变，增加新的点与边后模拟,global_diff_list是全局图的增量diff,这个暂时不用"""
        # 这里重新从全局G中计算子图sub_G，然后计算增量diff，然后发给UI
        G = self.manager.G
        if G is None:
            return

        # 子图尚未初始化（用户未打开图视图或未调用 new_load），忽略本次 diff
        if self.sub_G is None:
            return

        new_sub_G = self.apply_filter(G)
        # 比较新图new_sub_G和旧图sub_G的差异，然后计算增量diff，然后发给UI
        diff_list = []
        # --- 1. 处理节点的差异 ---
        # 增加的节点：在新图但不在旧图
        degrees = dict(new_sub_G.degree())
        deg_values = list(degrees.values()) or [1]
        min_deg = min(deg_values)
        max_deg = max(deg_values)
        for n in new_sub_G.nodes():
            if n not in self.sub_G.nodes():
                attr = dict(new_sub_G.nodes[n])
                attr["radius"] = _radius_from_degree(degrees, n, min_deg, max_deg)
                diff_list.append({"op": "add_node", "id": n, "attr": attr})

        # 减少的节点：在旧图但不在新图
        for n in self.sub_G.nodes():
            if n not in new_sub_G.nodes():
                diff_list.append({"op": "del_node", "id": n})

        # --- 2. 处理边的差异 ---
        # 增加的边：在新图但不在旧图
        for u, v in new_sub_G.edges():
            if not self.sub_G.has_edge(u, v):
                diff_list.append(
                    {"op": "add_edge", "u": u, "v": v, "attr": new_sub_G.edges[u, v]}
                )

        # 减少的边：在旧图但不在新图
        for u, v in self.sub_G.edges():
            if not new_sub_G.has_edge(u, v):
                diff_list.append({"op": "del_edge", "u": u, "v": v})

        self.diffChanged.emit(diff_list)  # 这个继续转发出去
