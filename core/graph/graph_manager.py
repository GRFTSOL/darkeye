import logging
from collections import defaultdict
from itertools import combinations
from typing import Optional
from threading import Lock
from PySide6.QtCore import QObject, Signal

from core.graph.text_parser import parse_wikilinks
from core.database.query import (
    get_active_workid_by_serialnumber,
    get_actress_from_work_id,
    get_serial_number_map,
    get_work_notes_rows,
    get_work_series_rows,
    get_work_ids_for_series,
    get_most_recent_work_for_graph_sync,
    get_recent_work_notes_rows,
)

"""
### 方案一：基于元数据的“硬关联” (Metadata Linking)
利用数据库中已有的结构化数据，建立明确的逻辑连接。

1. 导演/监督 (Director) :
   
   - 逻辑 : 同一个导演的作品通常具有相似的拍摄手法、叙事风格或题材偏好。
   - 实现 : 遍历所有作品，将 director 字段相同的作品两两相连（或连接到一个虚拟的“导演节点”）。
   - 价值 : 发现特定风格（如“第一人称视角大师”、“剧情向导演”）的作品群。
2. 系列/企划 (Series/Franchise) :
   
   - 逻辑 : 很多作品属于同一个系列（例如“全员逃走中”、“24小时不准笑”等）。
   - 实现 : 需要从 cn_title 或 jp_title 中提取系列名（通常在标题前缀或后缀），或者依赖刮削元数据中的系列字段。
   - 价值 : 这是最强的关联之一，用户通常希望看完一部接着看该系列的下一部。
3. 时间线轨迹 (Chronological Chain) :
   
   - 逻辑 : 针对同一个女优，将其作品按 release_date 排序，建立 Work A -> Work B -> Work C 的 有向边 。
   - 价值 : 在图中展示女优的“职业生涯路径”，观察其风格随时间的演变。
### 方案二：基于文本语义的“软关联” (Semantic Similarity)
目前您已有基于标签 (Tag) 的相似度（ generate_similar_graph ），但这比较粗糙。

1. 简介语义嵌入 (Story Embeddings) :
   
   - 逻辑 : 标签只能描述属性（如“OL”、“人妻”），但无法描述具体的剧情走向（如“上司来家里做客”、“意外发生”）。
   - 实现 : 使用轻量级 NLP 模型（如 sentence-transformers 或 fasttext ），将 cn_story (简介) 转化为 高维向量 ，计算两部作品向量的 余弦相似度 。
   - 价值 : 能发现“剧情内核相似”但“标签未必完全重合”的作品。例如发现所有“在电车上发生意外”的故事，即使它们标签打得乱七八糟。
2. 标题关键词聚类 :
   
   - 逻辑 : 提取标题中的高频非标签词汇（如特定地点、特定职业名词）。
   - 实现 : TF-IDF 算法提取关键词，共享罕见关键词的作品建立连接。
   
### 方案三：基于视觉的“视觉关联” (Visual Similarity)
利用封面图挖掘关系。

1. 封面风格相似度 (Cover Similarity) :
   - 逻辑 : 有些作品封面构图、色调极其相似，可能出自同一时期或同一企划。
   - 实现 : 使用计算机视觉模型（如 CLIP, ResNet）提取 cover_image 的特征向量，计算相似度。
   - 价值 : 对于“看图选片”的用户，这能推荐视觉冲击力相似的作品。

### 方案四：外部数据引入 (External Recommendations)
如果本地数据有限，可以引入外部智慧。

1. 协同过滤推荐 (Collaborative Filtering) :
   - 逻辑 : 爬取大型网站（如 JavLibrary, DMM）的“买了此片的人也买了...”数据。
   - 实现 : 这是一个额外的爬虫任务，将外部的推荐关系直接存为图的边。

"""


class GraphManager(QObject):
    """单例模式，图管理器管理总图，当有数据变动时，通过信号通知视图更新，长周期实例"""

    _instance: Optional["GraphManager"] = None
    _lock = Lock()

    # 信号定义：发送增量更新操作列表
    # Payload structure: List[Dict]
    # [{'op': 'add_node', 'id': 'w1', 'attr': {...}}, {'op': 'add_edge', 'u': 'w1', 'v': 'w2', 'attr': {...}}, ...]
    graphDiffSignal = Signal(list)
    initializationFinished = Signal()
    # 内部信号：用于在主线程中执行信号连接
    _connectSignalsRequested = Signal()

    """
    这里维护总图G，所有节点和边都在G中，
    然后可以输出子图，node的结构为
    G.add_node(f"w{wid}", label=title, group="work")
    边的结构
    G.add_edge(f"a{aid}", f"w{wid}")
    """

    def __init__(self):
        super().__init__()
        if GraphManager._instance is not None:
            raise RuntimeError(
                "GraphManager is a singleton class, use instance() method instead."
            )
        self.G = None
        self._initialized = False
        self._initializing = False

        # 连接内部信号到处理函数（在主线程中执行）
        self._connectSignalsRequested.connect(self._connect_signals_handler)

    @classmethod
    def instance(cls) -> "GraphManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self):
        """
        初始化图：异步启动后台线程加载数据
        """
        if self._initialized or self._initializing:
            logging.info("GraphManager已经初始化.")
            return

        logging.info("后台初始化 GraphManager")
        self._initializing = True

        import threading

        thread = threading.Thread(target=self._initialize_impl, daemon=True)
        thread.start()

    def _initialize_impl(self):
        """
        后台初始化逻辑
        """
        try:
            logging.info("开始初始化图")

            # 1. 获取基图 (包含 Works, Actresses, 和 Work-Actress 关系)
            # 基图中的节点ID格式：
            # 作品: "w{work_id}"
            # 女优: "a{actress_id}"
            # 2.从story数据中解析[[xxx]]的引用关系，这种关系是作品之间的连接关系，代表两部作品之间要么是类似的作品，要么是上下部之间的关系。
            # 3.解析作品tag之间的关系，发现连接
            # 4.自然语言处理作品的文本，发现连接，后面两步很困难，先不做
            # 5.图形处理发现作品封面的相似点，发现连接

            from core.graph.graph import generate_graph

            self.G = generate_graph()

            # 2. 从数据库加载 notes 并解析 [[]] 引用，叠加到基图中
            self._augment_with_story_relations()
            self._augment_with_series_relations()

            self._initialized = True

            # 连接信号必须在主线程执行，否则会触发 "Cannot create children for a parent
            # that is in a different thread"。使用信号槽机制将 connect 投递到主线程。
            self._connectSignalsRequested.emit()

            logging.info(
                f"Graph initialized. Nodes: {self.G.number_of_nodes()}, Edges: {self.G.number_of_edges()}"
            )
            self.initializationFinished.emit()

        except Exception as e:
            logging.error(f"GraphManager initialization failed: {e}")
            # 即使失败也标记为完成，避免死锁等待，或者需要一个 failed 信号
            self._initialized = True  # 标记为已完成（虽然是失败的）以允许后续逻辑继续
            self.initializationFinished.emit()
        finally:
            self._initializing = False

    def _augment_with_story_relations(self):
        """
        从数据库加载数据，解析story中的 [[]] 引用，并在基图上添加引用关系边
        """
        rows = get_work_notes_rows()
        logging.info(
            f"Loaded {len(rows)} works with stories from database for augmentation."
        )

        # 缓存 serial_number -> work_id 的映射，避免重复查询数据库
        serial_map = get_serial_number_map()

        for row in rows:
            source_work_id = row[0]
            source_serial = row[1]
            notes = row[2]

            # 构造符合基图规范的 Source 节点 ID (w + work_id)
            source_node_id = f"w{source_work_id}"

            # 仅当基图中存在该节点时才处理（generate_graph 应该包含了所有作品）
            if not self.G.has_node(source_node_id):
                continue

            # 解析引用
            links = parse_wikilinks(notes)
            if not links:
                continue

            for target_serial, alias in links:
                # 查找目标作品的 work_id
                target_work_id = serial_map.get(target_serial)

                if target_work_id is None:
                    # 尝试补救查询（不纳入软删除作品）
                    target_work_id = get_active_workid_by_serialnumber(target_serial)

                if target_work_id:
                    # 构造 Target 节点 ID
                    target_node_id = f"w{target_work_id}"

                    # 确保目标节点也在图中
                    if self.G.has_node(target_node_id):
                        # 避免自环
                        if source_node_id != target_node_id:
                            # 检查边是否存在
                            if not self.G.has_edge(source_node_id, target_node_id):
                                # 添加边，标记类型为 'reference' 以区别于参演关系
                                self.G.add_edge(
                                    source_node_id, target_node_id, type="reference"
                                )
                                # logging.debug(f"Added reference edge: {source_serial} -> {target_serial}")

    def _augment_with_series_relations(self):
        """
        把同 series_id 的作品在无向图上两两相连（clique）。

        边属性 type 为 ``series``，与 story 引用的 ``reference``、参演边区分。
        若两作品间已有任意无向边则跳过，不覆盖已有 type。
        """
        rows = get_work_series_rows()
        by_series: dict[int, list[int]] = defaultdict(list)
        for work_id, series_id in rows:
            by_series[series_id].append(work_id)

        added = 0
        groups_with_pair = 0
        for _, work_ids in by_series.items():
            work_ids = sorted(set(work_ids))
            if len(work_ids) < 2:
                continue
            groups_with_pair += 1
            for w_a, w_b in combinations(work_ids, 2):
                u, v = f"w{w_a}", f"w{w_b}"
                if u == v:
                    continue
                if not self.G.has_node(u) or not self.G.has_node(v):
                    continue
                if self.G.has_edge(u, v):
                    continue
                self.G.add_edge(u, v, type="series")
                added += 1
        logging.info(
            "Series augmentation: %d series groups with 2+ works, added %d edges.",
            groups_with_pair,
            added,
        )

    @staticmethod
    def _normalize_graph_series_id(series_id_raw) -> Optional[int]:
        """与库内系列边规则一致：有效系列须为整数且 > 1。"""
        if series_id_raw is None:
            return None
        try:
            sid = int(series_id_raw)
        except (TypeError, ValueError):
            return None
        if sid <= 1:
            return None
        return sid

    def _remove_series_edges_incident_to_work(
        self, work_id: int, changes: list
    ) -> None:
        """删除与某作品节点关联的、``type=series`` 的无向边，并记录 diff。"""
        nid = f"w{work_id}"
        if not self.G.has_node(nid):
            return
        for u, v, data in list(self.G.edges(nid, data=True)):
            if data.get("type") != "series":
                continue
            if self.G.has_edge(u, v):
                self.G.remove_edge(u, v)
                changes.append({"op": "remove_edge", "u": u, "v": v})

    def _rebuild_series_edges_for_series_id(
        self, series_id: int, changes: list
    ) -> None:
        """按当前库数据重建某 ``series_id`` 下作品间的 series 边（先剥旧再添全连接）。
        包括从无到有以及改变系列
        """
        work_ids = get_work_ids_for_series(series_id)
        nodes_w = {f"w{w}" for w in work_ids}

        edges_to_drop: set[tuple[str, str]] = set()
        for nid in nodes_w:
            if not self.G.has_node(nid):
                continue
            for u, v, data in self.G.edges(nid, data=True):
                if data.get("type") != "series":
                    continue
                edges_to_drop.add(tuple(sorted((u, v))))

        for u, v in edges_to_drop:
            if self.G.has_edge(u, v):
                self.G.remove_edge(u, v)
                changes.append({"op": "remove_edge", "u": u, "v": v})

        if len(work_ids) < 2:
            return

        for w_a, w_b in combinations(sorted(set(work_ids)), 2):
            u, v = f"w{w_a}", f"w{w_b}"
            if not self.G.has_node(u) or not self.G.has_node(v):
                continue
            if self.G.has_edge(u, v):
                continue
            self.G.add_edge(u, v, type="series")
            changes.append(
                {"op": "add_edge", "u": u, "v": v, "attr": {"type": "series"}}
            )

    def _sync_series_edges_from_latest_work(self, changes: list) -> None:
        """依据 ``update_time`` 最新的一条作品：软删则去掉其 series 边；否则重建其所属系列。"""
        row = get_most_recent_work_for_graph_sync()
        if row is None:
            return
        work_id, _serial, _notes, series_id_raw, is_deleted = row
        if is_deleted != 0:#作品被软删除，去掉其系列边与节点，节点是另外被删除了
            self._remove_series_edges_incident_to_work(work_id, changes)
            return

        sid = self._normalize_graph_series_id(series_id_raw)
        if sid is None:#作品没有series_id，去掉其系列边
            self._remove_series_edges_incident_to_work(work_id, changes)
            return
        #重建作品的系列边与节点
        self._rebuild_series_edges_for_series_id(sid, changes)

    def get_graph(self):
        """
        获取图对象，对外使用的只读接口
        """
        if not self._initialized:
            self.initialize()
        return self.G

    def reload(self):
        """
        重新加载图，深度重建图结构
        """
        self._initialized = False
        self.initialize()

    def prune_soft_deleted_work_nodes(self, *, emit_diff: bool = True) -> None:
        """从内存图 G 中移除已软删除的作品节点（及其边）。不重建整张图。"""
        if self.G is None or not self._initialized:
            return

        from core.database.connection import get_connection
        from config import DATABASE

        with get_connection(DATABASE, True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT work_id FROM work WHERE IFNULL(is_deleted, 0) = 1")
            deleted_ids = [row[0] for row in cur.fetchall()]

        removed = False
        with self._lock:
            for wid in deleted_ids:
                nid = f"w{wid}"
                if self.G.has_node(nid):
                    self.G.remove_node(nid)
                    removed = True

        if removed and emit_diff:
            self.graphDiffSignal.emit([{"op": "prune_soft_deleted"}])

    def _connect_signals_handler(self):
        """
        在主线程中处理信号连接，由 _connectSignalsRequested 信号触发
        """
        from controller.global_signal_bus import global_signals

        global_signals.workDataChanged.connect(self.update_recent_changes)
        logging.info("绑定 workDataChanged -> update_recent_changes")

    def update_recent_changes(self, limit: int = 3):
        """
        增量更新：按 ``update_time`` 最新的一条作品同步系列边（软删去边 / 否则重建该系列）；
        并获取最近更新的 limit 条作品，重建引用关系与女优-作品关系。
        """
        if not self._initialized:
            self.initialize()
            return
        logging.info(f"更新图关系")
        self.prune_soft_deleted_work_nodes(emit_diff=True)

        rows = get_recent_work_notes_rows(limit)
        if not rows:
            return

        serial_map = get_serial_number_map()
        changes = []

        logging.info(f"更新图根据最近 {len(rows)} 条作品的关系")

        with self._lock:
            for row in rows:
                source_work_id = row[0]
                source_serial = row[1]
                notes = row[2]
                source_node_id = f"w{source_work_id}"

                # 1. 作品节点检查与创建
                if not self.G.has_node(source_node_id):
                    self.G.add_node(source_node_id, label=source_serial, group="work")
                    logging.debug(f"添加新节点: {source_node_id}")
                    changes.append(
                        {
                            "op": "add_node",
                            "id": source_node_id,
                            "attr": {"label": source_serial, "group": "work"},
                        }
                    )

                # 2. 引用边 (type='reference')：仅当有 notes 时处理
                if notes:
                    out_edges = list(self.G.edges(source_node_id, data=True))
                    for u, v, data in out_edges:
                        if data.get("type") == "reference":
                            self.G.remove_edge(u, v)
                            changes.append({"op": "remove_edge", "u": u, "v": v})
                            logging.debug(f"删除引用边: {u} -> {v}")

                    links = parse_wikilinks(notes)
                    for target_serial, alias in links:
                        target_work_id = serial_map.get(target_serial)
                        if target_work_id is None:
                            target_work_id = get_active_workid_by_serialnumber(
                                target_serial
                            )

                        if target_work_id:
                            target_node_id = f"w{target_work_id}"

                            if not self.G.has_node(target_node_id):
                                self.G.add_node(
                                    target_node_id, label=target_serial, group="work"
                                )
                                changes.append(
                                    {
                                        "op": "add_node",
                                        "id": target_node_id,
                                        "attr": {
                                            "label": target_serial,
                                            "group": "work",
                                        },
                                    }
                                )
                                logging.debug(f"添加新节点: {target_node_id}")

                            if (
                                source_node_id != target_node_id
                                and not self.G.has_edge(source_node_id, target_node_id)
                            ):
                                self.G.add_edge(
                                    source_node_id, target_node_id, type="reference"
                                )
                                changes.append(
                                    {
                                        "op": "add_edge",
                                        "u": source_node_id,
                                        "v": target_node_id,
                                        "attr": {"type": "reference"},
                                    }
                                )
                                logging.debug(
                                    f"更新引用边: {source_serial} -> {target_serial}"
                                )

                # 3. 女优-作品边：按 DB 同步
                actress_list = get_actress_from_work_id(source_work_id)
                if actress_list is None:
                    actress_list = []

                work_edges = list(self.G.edges(source_node_id, data=True))
                for u, v, data in work_edges:
                    other = v if u == source_node_id else u
                    if other.startswith("a"):
                        self.G.remove_edge(u, v)
                        changes.append({"op": "remove_edge", "u": u, "v": v})
                        logging.debug(f"删除女优边: {u} -> {v}")

                for item in actress_list:
                    aid = item.get("actress_id")
                    name = item.get("actress_name") or ""
                    actress_node_id = f"a{aid}"
                    if not self.G.has_node(actress_node_id):
                        self.G.add_node(
                            actress_node_id,
                            label=name,
                            group="actress",
                        )
                        changes.append(
                            {
                                "op": "add_node",
                                "id": actress_node_id,
                                "attr": {"label": name, "group": "actress"},
                            }
                        )
                        logging.debug(f"添加新女优节点: {actress_node_id}")
                    if not self.G.has_edge(actress_node_id, source_node_id):
                        self.G.add_edge(actress_node_id, source_node_id)
                        changes.append(
                            {
                                "op": "add_edge",
                                "u": actress_node_id,
                                "v": source_node_id,
                                "attr": {},
                            }
                        )
                        logging.debug(
                            f"添加女优边: {actress_node_id} -> {source_node_id}"
                        )

            self._sync_series_edges_from_latest_work(changes)

        if changes:
            logging.info(f"图更新完成，共 {len(changes)} 个变更操作")
            self.graphDiffSignal.emit(changes)
        else:
            logging.info("图增量更新完成。无拓扑变更。")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    root_dir = Path(__file__).resolve().parents[2]  # 上两级
    sys.path.insert(0, str(root_dir))
    # 配置日志
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("开始测试 GraphManager...")

    # 获取单例
    manager = GraphManager.instance()

    # 初始化
    manager.initialize()

    # 获取图
    G = manager.get_graph()

    print(f"\n图统计信息:")
    print(f"总节点数: {G.number_of_nodes()}")
    print(f"总边数: {G.number_of_edges()}")

    # 打印一些示例数据
    if G.number_of_nodes() > 0:
        print("\n前5个节点:")
        for node_id in list(G.nodes())[:5]:
            print(f"ID: {node_id}, Data: {G.nodes[node_id]}")

    if G.number_of_edges() > 0:
        print("\n前5条边:")
        for u, v, data in list(G.edges(data=True))[:5]:
            print(f"{G.nodes[u].get('label')} -> {G.nodes[v].get('label')}: {data}")

    print("\n测试完成。")
