from PySide6.QtCore import QObject, Signal
import networkx as nx
from .graph_manager import GraphManager
from .graph_filter import GraphFilter, PassThroughFilter

class GraphViewSession(QObject):
    """
    Session layer between GraphManager (Global Data) and ForceView (UI).
    Handles filtering and data synchronization.
    """
    # Emitted when graph data is ready to be displayed/updated
    # payload: {"cmd": "load_graph", "graph": nx.Graph, "modify": bool} 
    # or {"cmd": "update_graph", "diff": list} (future support)
    data_ready = Signal(dict) 

    def __init__(self):
        super().__init__()
        self._filter: GraphFilter = PassThroughFilter()
        self.manager = GraphManager.instance()
        self.manager.graph_diff_signal.connect(self._on_global_diff)

        
    
    def set_filter(self, new_filter: GraphFilter):
        """Set a new filter and trigger a full reload."""
        self._filter = new_filter


    def reload(self):
        """Pull data from Global Graph, apply filter, and notify UI."""
        G = self.manager.G
        if G is None:
            return

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
                    
        self.data_ready.emit({"cmd": "load_graph", "graph": sub_G, "modify": False})

    def _on_global_diff(self, diff_list: list):
        """Handle incremental updates from GraphManager."""
        # For now, to ensure consistency, we just reload the filtered graph.
        # Efficient incremental filtering can be implemented here later.
        self.reload()
