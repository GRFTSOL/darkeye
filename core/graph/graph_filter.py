from abc import ABC, abstractmethod
import networkx as nx


class GraphFilter(ABC):
    @abstractmethod
    def filter_node(self, graph: nx.Graph, node_id) -> bool:
        """Return True if the node should be included in the view."""
        pass

    @abstractmethod
    def filter_edge(self, graph: nx.Graph, u, v) -> bool:
        """Return True if the edge should be included in the view."""
        pass


class EmptyFilter(GraphFilter):
    """过滤器，什么都不返回（过滤掉所有节点和边）。"""

    def filter_node(self, graph: nx.Graph, node_id) -> bool:
        return False

    def filter_edge(self, graph: nx.Graph, u, v) -> bool:
        return False


class PassThroughFilter(GraphFilter):
    """Default filter that includes everything."""

    def filter_node(self, graph: nx.Graph, node_id) -> bool:
        return True

    def filter_edge(self, graph: nx.Graph, u, v) -> bool:
        return True


class EgoFilter(GraphFilter):
    """自我中心过滤器，过滤以指定节点为中心，半径为指定值的子图"""

    def __init__(self, center_id: str, radius: int = 1):
        self.center_id = center_id
        self.radius = radius
        self._valid_nodes = None

    def _compute_valid_nodes(self, graph: nx.Graph):
        if self.center_id not in graph:
            self._valid_nodes = set()
            return
        # Calculate ego graph nodes
        self._valid_nodes = set(
            nx.ego_graph(graph, self.center_id, radius=self.radius).nodes()
        )

    def filter_node(self, graph: nx.Graph, node_id) -> bool:
        if self._valid_nodes is None:
            self._compute_valid_nodes(graph)
        return node_id in self._valid_nodes

    def filter_edge(self, graph: nx.Graph, u, v) -> bool:
        # If both nodes are valid, the edge is valid
        # (This assumes the induced subgraph includes all edges between valid nodes)
        if self._valid_nodes is None:
            self._compute_valid_nodes(graph)
        return u in self._valid_nodes and v in self._valid_nodes


class FavoriteWorkFilter(GraphFilter):
    """喜欢作品过滤器：保留喜欢作品及其直接关联女优。"""

    def __init__(self):
        self._valid_nodes: set[str] | None = None
        self._favorite_work_ids: set[int] | None = None

    def _load_favorite_work_ids(self) -> set[int]:
        if self._favorite_work_ids is not None:
            return self._favorite_work_ids

        from config import DATABASE
        from core.database.connection import get_connection
        from core.database.db_utils import attach_private_db, detach_private_db

        favorite_work_ids: set[int] = set()
        with get_connection(DATABASE, True) as conn:
            cursor = conn.cursor()
            try:
                attach_private_db(cursor)
                cursor.execute("SELECT work_id FROM priv.favorite_work")
                for (work_id,) in cursor.fetchall():
                    if work_id is not None:
                        favorite_work_ids.add(int(work_id))
            finally:
                detach_private_db(cursor)

        self._favorite_work_ids = favorite_work_ids
        return favorite_work_ids

    @staticmethod
    def _is_work_node(node_id: str, node_attr: dict) -> bool:
        return str(node_id).startswith("w") or node_attr.get("group") == "work"

    @staticmethod
    def _is_actress_node(node_id: str, node_attr: dict) -> bool:
        return str(node_id).startswith("a") or node_attr.get("group") == "actress"

    @staticmethod
    def _parse_work_id(node_id: str) -> int | None:
        s = str(node_id)
        if not s.startswith("w"):
            return None
        try:
            return int(s[1:])
        except ValueError:
            return None

    def _compute_valid_nodes(self, graph: nx.Graph) -> None:
        favorite_work_ids = self._load_favorite_work_ids()
        valid_nodes: set[str] = set()
        favorite_work_nodes: set[str] = set()

        # 1) 喜欢的作品节点
        for node_id, node_attr in graph.nodes(data=True):
            node_key = str(node_id)
            if not self._is_work_node(node_key, node_attr):
                continue
            work_id = self._parse_work_id(node_key)
            if work_id is not None and work_id in favorite_work_ids:
                favorite_work_nodes.add(node_key)
                valid_nodes.add(node_key)

        # 2) 与喜欢作品直接相连的女优节点
        for work_node in favorite_work_nodes:
            for neighbor in graph.neighbors(work_node):
                neighbor_key = str(neighbor)
                neighbor_attr = graph.nodes[neighbor]
                if self._is_actress_node(neighbor_key, neighbor_attr):
                    valid_nodes.add(neighbor_key)

        self._valid_nodes = valid_nodes

    def filter_node(self, graph: nx.Graph, node_id) -> bool:
        if self._valid_nodes is None:
            self._compute_valid_nodes(graph)
        return str(node_id) in self._valid_nodes

    def filter_edge(self, graph: nx.Graph, u, v) -> bool:
        if self._valid_nodes is None:
            self._compute_valid_nodes(graph)
        return str(u) in self._valid_nodes and str(v) in self._valid_nodes
