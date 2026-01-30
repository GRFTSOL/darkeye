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

class PassThroughFilter(GraphFilter):
    """Default filter that includes everything."""
    def filter_node(self, graph: nx.Graph, node_id) -> bool:
        return True

    def filter_edge(self, graph: nx.Graph, u, v) -> bool:
        return True

class EgoFilter(GraphFilter):
    """Filter that includes nodes within a certain radius of a center node."""
    def __init__(self, center_id: str, radius: int = 1):
        self.center_id = center_id
        self.radius = radius
        self._valid_nodes = None

    def _compute_valid_nodes(self, graph: nx.Graph):
        if self.center_id not in graph:
            self._valid_nodes = set()
            return
        # Calculate ego graph nodes
        self._valid_nodes = set(nx.ego_graph(graph, self.center_id, radius=self.radius).nodes())

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
