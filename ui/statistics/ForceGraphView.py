"""
1 NodeLayer 鼠标命中检测
2 NodeLayer.boundingRect

4 换一种积分器，运行更柔和

现在改成多进程版本，把模拟计算放到后台进程，而且精简，不要的全删除了
平滑缩放，后面再弄
"""


import sys,numba,os
from pathlib import Path
import logging

#----------------------------------------------------------
root_dir = Path(__file__).resolve().parents[2]  # 上两级
sys.path.insert(0, str(root_dir))
from ui.basic import ToggleSwitch
from config import ACTRESSIMAGES_PATH,WORKCOVER_PATH
from typing import Dict, Hashable,Tuple
import math
from collections import defaultdict
import random
from typing import List, Dict, Tuple, Optional,Any
import numpy as np
import networkx as nx
from multiprocessing import shared_memory
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsSimpleTextItem, QPushButton, QVBoxLayout, QWidget,
    QGraphicsRectItem, QHBoxLayout, QCheckBox, QLabel, QSlider, QFormLayout, QGraphicsItem, QGroupBox,
    QRadioButton,QGraphicsObject
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QBrush, QPen, QColor, QPainter,QFont,QFontMetrics,QStaticText,QImage,QWheelEvent,QTransform
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF,Signal,QObject,QLineF,QSize,QThread,Slot

import time
import functools
import uuid
from core.graph.simulation_process_main import get_global_simulation_process
from core.graph.graph import generate_graph,generate_random_graph,generate_similar_graph
from core.graph.graph_session import GraphViewSession
from ui.basic.Collapse import CollapsibleSection


def timeit(func):
    """装饰器：打印函数执行耗时"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        c=(end - start)*1000
        #logging.debug(f"⏱ {func.__name__} 执行耗时: {end - start:.4f} 秒")
        logging.info(f"⏱ {func.__name__} 执行耗时: {c:.4f} ms")
        return result
    return wrapper


class ReceiverThread(QThread):
    """
    后台接收线程：专门负责从 Pipe 中读取数据，解除 UI 线程阻塞。
    """
    message_received = Signal(dict)

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self._running = True

    def run(self):
        while self._running:
            if self.conn is None:
                break
            try:
                # Windows 上 Pipe 的 recv() 是阻塞的，这样很完美，不占用 CPU
                # 如果是 Linux/Mac，可能需要配合 poll(timeout) 使用
                if self.conn.poll(0.1): # 使用带超时的 poll 避免死锁并允许响应 stop
                    msg = self.conn.recv()
                    if isinstance(msg, dict):
                        self.message_received.emit(msg)
            except (EOFError, OSError, BrokenPipeError):
                break
            except Exception as e:
                print(f"ReceiverThread error: {e}")
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait()

class SimulationClient(QObject):
    '''负责管理视图与模拟进程的通信，单例模式
    产生一个视图就注册一个view_id, 启动后台线程接收消息,统一管理转发'''
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.conn = get_global_simulation_process()
        self.listeners = {} # view_id -> callback
        self._is_backend_ready = False
        self._msg_buffer = [] # 缓冲队列
        
        # 启动接收线程
        self.receiver_thread = ReceiverThread(self.conn)
        self.receiver_thread.message_received.connect(self._dispatch_message)
        self.receiver_thread.start()

    def register(self, view_id, callback):
        self.listeners[view_id] = callback

    def unregister(self, view_id):
        if view_id in self.listeners:
            del self.listeners[view_id]

    def send(self, msg: dict):
        if self._is_backend_ready:
            try:
                self.conn.send(msg)
            except (BrokenPipeError, OSError):
                pass
        else:
            self._msg_buffer.append(msg)

    def _dispatch_message(self, msg: dict):
        """主线程槽函数：分发消息给对应的 View"""
        # 优先处理系统级消息
        if msg.get("event") == "system_ready":
            print("收到后台就绪信号，开始发送缓冲消息...")
            self._is_backend_ready = True
            for buffered_msg in self._msg_buffer:
                try:
                    self.conn.send(buffered_msg)
                except (BrokenPipeError, OSError):
                    pass
            self._msg_buffer.clear()
            return

        view_id = msg.get("view_id")
        if view_id in self.listeners:
            self.listeners[view_id](msg)



def get_actress_image(actress_id:int)->QImage:
    """根据女优ID获取女优照片"""
    from core.database.connection import get_connection
    from config import DATABASE
    with get_connection(DATABASE,True) as conn:
        cursor = conn.cursor()
        q="""
        SELECT image_urlA FROM actress WHERE actress_id=?
        """
        cursor.execute(q,(actress_id,))
        imagepath = cursor.fetchone()[0]
        image = QImage(str(ACTRESSIMAGES_PATH/imagepath))
        return image

def get_work_image(work_id:int)->QImage:
    """根据女优ID获取女优照片"""
    from core.database.connection import get_connection
    from config import DATABASE
    with get_connection(DATABASE,True) as conn:
        cursor = conn.cursor()
        q="""
        SELECT image_url FROM work WHERE work_id=?
        """
        cursor.execute(q,(work_id,))
        imagepath = cursor.fetchone()[0]
        img = QImage(str(WORKCOVER_PATH/imagepath))
        w, h = img.width(), img.height()
        crop_x = w - h * 0.7
        crop_w = h * 0.7
        img = img.copy(int(crop_x), 0, int(crop_w), h)#裁剪
        img = img.scaled(
                QSize(140,200),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        return img

class RenderState:
    '''与图有关的信息'''
    def __init__(self, G: nx.Graph, pos_array, nodes, node_index, edges, neighbors, shm=None, n_nodes=0):
        self.G = G #原始图
        self.pos = pos_array #(N,2)[(123.1,234.1),(153.6,54.1),...]
        self.nodes = nodes
        self.node_index = node_index #节点索引，节点ID到索引的映射
        self.edges = edges #(E,2) [(1,2),(2,3),...]
        self.neighbors = neighbors #长度为N的列表，每个元素都是一个数组，存储该节点的邻居索引，没有邻居就是空数组
        self.shm = shm #共享内存对象，这个与self.pos是两个不同层面的引用
        self.n_nodes = n_nodes #节点数量

def compute_node_radii(G: nx.Graph, r_min=4, r_max=10):
    """根据度数向量化计算节点半径，线性映射到 [r_min, r_max]的整数"""
    """根据度数向量化计算节点半径，线性映射到 [r_min, r_max]的整数"""
    degrees = np.array([d for _, d in G.degree()], dtype=np.float32)# type: ignore[arg-type]
    if len(degrees) == 0:
        return np.array([], dtype=np.int32)

    d_min, d_max = degrees.min(), degrees.max()

    if d_min == d_max:  # 全部度相同
        value = int(round((r_min + r_max) / 2))
        radii = np.full(degrees.shape, value, dtype=np.int32)
    else:
        scaled = r_min + (degrees - d_min) / (d_max - d_min) * (r_max - r_min)
        radii = np.rint(scaled).astype(np.int32)
    return radii


class ForceGraphController(QObject):
    """
    Presenter (Controller): 处理业务逻辑、IPC 通信、共享内存管理。
    """
    graph_loaded = Signal(object, object) # (state, node_radii)
    frame_ready = Signal(float, bool)      # (elapsed, active)
    simulation_started = Signal()
    simulation_stopped = Signal()

    def __init__(self, view_id: str):
        super().__init__()
        self.view_id = view_id
        self.client = SimulationClient.instance()
        self.state = None
        self._trash_shms = []
        self._sim_active = False
        self._sim_params = {
            "many_strength": 10000.0,
            "link_k": 0.3,
            "link_distance": 30.0,
            "center_strength": 0.01,
        }
        self.client.register(self.view_id, self._on_sim_message)
        
        # 数据加载会话
        self.session = GraphViewSession()
        self.session.data_ready.connect(self._on_graph_data_ready)

    def _on_graph_data_ready(self, data: dict):
        cmd = data.get("cmd")
        if cmd == "load_graph":
            self.load_graph(data.get("graph"), modify=data.get("modify", False))

    def load_graph(self, G: nx.Graph, modify=False):
        if G is None: return
        logging.info(f"Controller: 加载图 {self.view_id}")
        
        # 1. 共享内存延迟清理
        if self.state and self.state.shm:
            self._trash_shms.append(self.state.shm)
            self.pause_simulation()

        n_nodes = G.number_of_nodes()
        scale = math.sqrt(n_nodes) * 25 + 150
        
        # 2. 计算位置 (保持原有逻辑)
        positions = {}
        if modify and self.state:
            # 这里的 self.state.G 可能和传入的 G 不完全一致，但逻辑上是找旧坐标
            for n in G.nodes():
                if 'pos' in G.nodes[n]:
                    positions[n] = G.nodes[n]['pos']
                else:
                    # 尝试从之前的 state 中找
                    if self.state and n in self.state.node_index:
                        idx = self.state.node_index[n]
                        positions[n] = (float(self.state.pos[idx,0]), float(self.state.pos[idx,1]))
            
            # 缺失点生成
            missing_nodes = [n for n in G.nodes() if n not in positions]
            if missing_nodes:
                existing_pos = list(positions.values())
                if not existing_pos:
                    for n in missing_nodes:
                        positions[n] = (random.uniform(-scale, scale), random.uniform(-scale, scale))
                else:
                    cx = sum(p[0] for p in existing_pos) / len(existing_pos)
                    cy = sum(p[1] for p in existing_pos) / len(existing_pos)
                    for n in missing_nodes:
                        positions[n] = (cx + random.uniform(-50, 50), cy + random.uniform(-50, 50))
        else:
            positions = {n: (random.uniform(-scale, scale), random.uniform(-scale, scale)) for n in G.nodes()}

        # 3. 创建共享内存
        shm = shared_memory.SharedMemory(create=True, size=n_nodes * 2 * np.float32().nbytes)
        shared_pos = np.ndarray((n_nodes, 2), dtype=np.float32, buffer=shm.buf)
        
        nodes = list(G.nodes())
        node_index = {n: i for i, n in enumerate(nodes)}
        for i, n in enumerate(nodes):
            shared_pos[i, :] = positions[n]

        edges = np.array([(node_index[u], node_index[v]) for u, v in G.edges()], dtype=np.int32)
        
        # 4. 构建邻居表
        neighbors_list = [[] for _ in range(n_nodes)]
        for u_idx, v_idx in edges:
            neighbors_list[u_idx].append(v_idx)
            neighbors_list[v_idx].append(u_idx)
        neighbors = [np.array(nb, dtype=np.int32) if nb else np.empty(0, dtype=np.int32) for nb in neighbors_list]

        # 5. 更新状态
        self.state = RenderState(G, shared_pos, nodes, node_index, edges, neighbors, shm, n_nodes)
        node_radii = compute_node_radii(G)
        
        # 6. 通知 View
        self.graph_loaded.emit(self.state, node_radii)
        
        # 7. 启动后台
        cmd = "little_load_graph" if modify else "load_graph"
        self.client.send({
            "cmd": cmd,
            "view_id": self.view_id,
            "shm_name": shm.name,
            "n_nodes": n_nodes,
            "edges": edges,
            "params": self._sim_params
        })
        self._sim_active = True

    def _on_sim_message(self, msg):
        event = msg.get("event")
        if event in ("graph_ready", "modify_graph"):
            for shm in self._trash_shms:
                try: shm.close(); shm.unlink()
                except: pass
            self._trash_shms.clear()#清空所有旧的共享内存
        
        if event == "tick":
            elapsed = float(msg.get("elapsed", 0.0))
            active = bool(msg.get("active", True))
            self._sim_active = active
            self.frame_ready.emit(elapsed, active)

    def pause_simulation(self):
        self._sim_active = False
        self.client.send({"cmd": "pause", "view_id": self.view_id})
        self.simulation_stopped.emit()

    def restart_simulation(self):
        self._sim_active = True
        self.client.send({"cmd": "restart", "view_id": self.view_id})
        self.simulation_started.emit()
    
    def resume_simulation(self):
        self._sim_active = True
        self.client.send({"cmd": "resume", "view_id": self.view_id})
        self.simulation_started.emit()

    def update_param(self, key, value):
        self._sim_params[key] = value
        self.client.send({"cmd": f"set_{key}", "view_id": self.view_id, "value": value})
        self.restart_simulation()

    def shutdown(self):
        self.client.unregister(self.view_id)
        self.client.send({"cmd": "close_view", "view_id": self.view_id})
        if self.state and self.state.shm:
            try: self.state.shm.close(); self.state.shm.unlink()
            except: pass
        for shm in self._trash_shms:
            try: shm.close(); shm.unlink()
            except: pass

    def _sync_pos_to_graph(self):
        if not self.state or not self.state.G: return
        for i, n in enumerate(self.state.nodes):
            self.state.G.nodes[n]['pos'] = (float(self.state.pos[i, 0]), float(self.state.pos[i, 1]))

    def add_node_runtime(self, node_id, **attrs):
        if not self.state: return
        self.pause_simulation()
        self._sync_pos_to_graph()
        self.state.G.add_node(node_id, **attrs)
        self.load_graph(self.state.G, modify=True)

    def remove_node_runtime(self, node_id):
        if not self.state or node_id not in self.state.G: return
        self.pause_simulation()
        self._sync_pos_to_graph()
        self.state.G.remove_node(node_id)
        self.load_graph(self.state.G, modify=True)

    def add_edge_runtime(self, u, v, **attrs):
        if not self.state: return
        self.pause_simulation()
        self._sync_pos_to_graph()
        self.state.G.add_edge(u, v, **attrs)
        self.load_graph(self.state.G, modify=True)

    def remove_edge_runtime(self, u, v):
        if not self.state: return
        self.pause_simulation()
        self._sync_pos_to_graph()
        if self.state.G.has_edge(u, v):
            self.state.G.remove_edge(u, v)
        self.load_graph(self.state.G, modify=True)
    
    def apply_graph_diff(self, changes: list):
        """
        响应 GraphManager 的增量更新信号
        """
        if not changes or not self.state or self.state.G is None:
            return

        print(f"Controller received {len(changes)} graph changes.")
        
        # 1. 暂停模拟并同步位置，保留物理状态
        self.pause_simulation()
        self._sync_pos_to_graph()
        
        G = self.state.G
        need_reload = False
        
        # 2. 批量应用变更到本地图对象
        for change in changes:
            op = change.get('op')
            
            if op == 'add_node':
                node_id = change['id']
                attrs = change.get('attr', {})
                if node_id not in G:
                    G.add_node(node_id, **attrs)
                    need_reload = True
                else:
                    G.nodes[node_id].update(attrs)
                    need_reload = True

            elif op == 'remove_node':
                node_id = change['id']
                if node_id in G:
                    G.remove_node(node_id)
                    need_reload = True

            elif op == 'add_edge':
                u, v = change['u'], change['v']
                attrs = change.get('attr', {})
                if not G.has_edge(u, v):
                    G.add_edge(u, v, **attrs)
                    need_reload = True
                else:
                    G.edges[u, v].update(attrs)

            elif op == 'remove_edge':
                u, v = change['u'], change['v']
                if G.has_edge(u, v):
                    G.remove_edge(u, v)
                    need_reload = True
        
        # 3. 如果有拓扑变更，执行热重载并重启模拟
        if need_reload:
            self.load_graph(G, modify=True)
            self.restart_simulation()
        else:
            if self._sim_active:
                self.restart_simulation()

    def set_dragging(self, index, dragging):
        self.client.send({"cmd": "set_dragging", "view_id": self.view_id, "index": int(index), "dragging": dragging})
        if dragging: self.restart_simulation()


class AsyncImageLoader(QObject):
    image_loaded = Signal()

    def __init__(self):
        super().__init__()
        self.cache = {}
        self.loading = set()

    def get_actress_image(self, actress_id):
        key = f"a{actress_id}"
        if key in self.cache:
            return self.cache[key]
        
        if key not in self.loading:
            self.loading.add(key)
            threading.Thread(target=self._load_actress, args=(actress_id,), daemon=True).start()
        
        return None

    def get_work_image(self, work_id):
        key = f"w{work_id}"
        if key in self.cache:
            return self.cache[key]
        
        if key not in self.loading:
            self.loading.add(key)
            threading.Thread(target=self._load_work, args=(work_id,), daemon=True).start()
        
        return None

    def _load_actress(self, actress_id):
        try:
            img = get_actress_image(actress_id)
            self.cache[f"a{actress_id}"] = img
            self.image_loaded.emit()
        except Exception as e:
            logging.info(f"Async load error: {e}")
        finally:
            self.loading.discard(f"a{actress_id}")

    def _load_work(self, work_id):
        try:
            img = get_work_image(work_id)
            self.cache[f"w{work_id}"] = img
            self.image_loaded.emit()
        except Exception as e:
            logging.info(f"Async load error: {e}")
        finally:
            self.loading.discard(f"w{work_id}")

global_image_loader = AsyncImageLoader()


class NodeLayer(QGraphicsObject):
    """
    高性能绘制所有节点的自定义图层，直接从 RenderState.pos 中读取坐标。
    这一层只管怎么画、怎么动、怎么响应鼠标，不去推导图的结构
    """
    nodePressed = Signal(int)
    nodeDragged = Signal(int)
    nodeReleased = Signal(int)
    nodeLeftClicked = Signal(int)
    nodeRightClicked = Signal(int)
    nodeHovered = Signal(int)
    paint_time=Signal(float)
    fps=Signal(float)

    def __init__(self, state:RenderState,show_radius,parent=None):
        super().__init__(parent)
        self.state = state
        # 连接全局图片加载器的信号
        global_image_loader.image_loaded.connect(self.update)
        self.center_node_id=None#视图中心节点ID，如果有，就把这个节点永久染色
        self.edge_color=QColor("#D5D5D5")
        self.edge_dim_color=QColor("#F7F7F7")
        self.base_color = QColor("#5C5C5C")#基础的颜色
        self.dim_color = QColor("#DEDEDE")#未选中的颜色，更加的浅
        self.hover_color = QColor("#8F6AEE")# 悬停颜色，紫色
        self.show_image=True
        self.side_width_base=1.0
        self.side_width_factor=1.0
        
        self.show_radius_base=np.array(show_radius, dtype=np.float32)
        self.radius_factor=1.0

        self.textshreshold_base=0.7
        self.textshreshold_factor=1.0
        
        self.setZValue(1)  # 确保在边上方

        self.labels=None
        self.label_min_scale = 0.75
        
        self._static_text_cache: Dict[str, Tuple[QStaticText,float]] = {}# 缓存静态文本与宽度
        self.font = QFont("Microsoft YaHei", 5)
        self.font_metrics = QFontMetrics(self.font)
        self.font_height = self.font_metrics.height()

        N = self.state.pos.shape[0]
        self.neighbor_mask = np.zeros(N, dtype=bool)

        self.visible_indices = np.array([], dtype=int) #可见节点的索引[1,2,3,...]
        self.visible_edges = np.array([], dtype=int)   #可见边的索引每个里面是点的索引对,[(1,2),(2,3),...]

        node_dict=dict(self.state.G.nodes(data=True))
        first_node_id = next(iter(node_dict))

        if self.labels is None and node_dict[first_node_id].get("label", None) is None:
            self.labels = [n for n in self.state.G.nodes()]
        else:
            self.labels = [data.get("label", None) for _, data in self.state.G.nodes(data=True)]
        self._init_static_text_cache()

        #交互相关
        self.dragging = False
        self.setCursor(Qt.ArrowCursor)# type: ignore[arg-type]
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)# type: ignore[arg-type]
        self.hover_index = -1
        self.setAcceptHoverEvents(True)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)# type: ignore[arg-type]
        self.setFlag(QGraphicsItem.ItemIsMovable, False)# type: ignore[arg-type]

        #动画相关
        self._hover_step = 0.1
        self._hover_global = 0.0
        self.last_hover_index = -1
        self._last_neighbor_mask = None
        self.last_dim_edges=None  #为了渐变效果用，记录上一次的非相关边
        self.last_highlight_edges=None  #为了渐变效果用，记录上一次的相关边

        self.update_factor()
        self._bounding_rect = None

        self.frame_count = 0
        self.last_fps_time = time.perf_counter()
        self.current_fps = 0.0

    def update_visible_mask(self):
        """更新可见性self.visible_indices,self.visible_edges
        包括节点和边的,每次计算后调用，每次滚轮缩放后调用，每次拖动图面调用，切换图时调用"""
        pos = self.state.pos
        N = pos.shape[0]
        if N == 0:
            node_visible_mask = np.zeros(0, dtype=bool)
            return
        scene = self.scene()
        views = scene.views() if scene is not None else []
        if views:
            v = views[0]
            rect_scene = v.mapToScene(v.viewport().rect()).boundingRect()
            visible_rect = self.mapRectFromScene(rect_scene)
        else:
            visible_rect = self.boundingRect()

        margin_x = 50#visible_rect.width() * 0.1
        margin_y = 50#visible_rect.height() * 0.1
        visible_rect = visible_rect.adjusted(-margin_x, -margin_y, margin_x, margin_y)
        xs = pos[:, 0]
        ys = pos[:, 1]
        rs = self.show_radius
        node_visible_mask = (
            (xs + rs >= visible_rect.left())
            & (xs - rs <= visible_rect.right())
            & (ys + rs >= visible_rect.top())
            & (ys - rs <= visible_rect.bottom())
        )

        self.visible_indices = np.nonzero(node_visible_mask)[0]

        edges = getattr(self.state, "edges", None)
        if edges is not None and len(edges) > 0:
            edge_mask = node_visible_mask[edges[:, 0]] | node_visible_mask[edges[:, 1]]
            self.visible_edges = self.state.edges[edge_mask]

    def paint(self, painter: QPainter, option, widget=None):
        '''加速方案
        1批量画边
        2将节点缓存到 QPixmap 中，减少 drawEllipse 调用，这个会很模糊
        3缩小到一定程度时不画文字
        4屏幕检测，在屏幕外的不画
        5文本缓存宽度，避免重复计算

        实际渲染发生在_on_render_tick中
        '''
        start: float = time.perf_counter()

        self.draw_edges(painter)
        self.draw_nodes_and_text(painter)
        if self.show_image:
            self.draw_images(painter)

        #self.draw_bounding_rect(painter)

        elapsed: float = (time.perf_counter() - start) * 1000.0
        self.paint_time.emit(elapsed)
        self.update_fps()
        
    def draw_edges(self, painter: QPainter):
        #现在还有一个问题就是切换图时，那些有的渐变就不需要画
        pos = self.state.pos
        visible_edges = self.visible_edges
        if len(visible_edges) > 0:
            hover: int = self.hover_index
            if hover == -1:#未有悬停节点
                if self._hover_global<=0:#默认绘图
                    painter.setPen(QPen(self.edge_color, self.side_width))
                    src = pos[visible_edges[:, 0]]
                    dst = pos[visible_edges[:, 1]]
                    lines = [QLineF(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(src, dst)]
                    if lines:
                        painter.drawLines(lines)
                else:
                    t = float(self._hover_global)
                    color = self._mix_color(self.edge_color, self.edge_dim_color, t)
                    painter.setPen(QPen(color, self.side_width))
                    if self.last_dim_edges is not None and len(self.last_dim_edges) > 0:
                        src = pos[self.last_dim_edges[:, 0]]# type: ignore[arg-type]
                        dst = pos[self.last_dim_edges[:, 1]]# type: ignore[arg-type]
                        lines = [QLineF(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(src, dst)]
                        if lines:
                            painter.drawLines(lines)

                    color = self._mix_color(self.edge_color, self.hover_color, t)
                    painter.setPen(QPen(color, self.side_width))
                    src = pos[self.last_highlight_edges[:, 0]]# type: ignore[arg-type]
                    dst = pos[self.last_highlight_edges[:, 1]]# type: ignore[arg-type]
                    lines = [QLineF(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(src, dst)]
                    if lines:
                        painter.drawLines(lines)
            else:#有悬停节点
                ve_src = visible_edges[:, 0]
                ve_dst = visible_edges[:, 1]
                edge_highlight_mask = (ve_src == hover) | (ve_dst == hover)
                highlight_edges = visible_edges[edge_highlight_mask]
                dim_edges = visible_edges[~edge_highlight_mask]
                self.last_dim_edges = dim_edges
                self.last_highlight_edges = highlight_edges

                dim_edge_color = QColor(self.edge_color)
                dim_edge_color.setAlpha(80)
                if len(dim_edges) > 0:#画非相关边
                    t = float(self._hover_global)
                    color = self._mix_color(self.edge_color, self.edge_dim_color, t)
                    painter.setPen(QPen(color, self.side_width))
                    src = pos[dim_edges[:, 0]]
                    dst = pos[dim_edges[:, 1]]
                    lines = [QLineF(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(src, dst)]
                    if lines:
                        painter.drawLines(lines)
                if len(highlight_edges) > 0:#画悬停点相关边
                    t = float(self._hover_global)
                    color = self._mix_color(self.edge_color, self.hover_color, t)
                    #hover_edge_color = QColor("#A855F7")# 悬停边颜色
                    painter.setPen(QPen(color, self.side_width))
                    src = pos[highlight_edges[:, 0]]
                    dst = pos[highlight_edges[:, 1]]
                    lines = [QLineF(x1, y1, x2, y2) for (x1, y1), (x2, y2) in zip(src, dst)]
                    if lines:
                        painter.drawLines(lines)
        
    def draw_nodes_and_text(self, painter: QPainter):
        # ----------------------------画圆----------------------------
        # 优化：预计算颜色和画笔，批量绘制，减少状态切换和Python计算开销
        scene: QGraphicsScene = self.scene()
        views = scene.views() if scene is not None else []
        pos = self.state.pos
        t = float(self._hover_global)
        
        # Determine center index if center_node_id is set
        center_index = -1
        if hasattr(self, 'center_node_id') and self.center_node_id is not None and self.center_node_id in self.state.node_index:
            center_index = self.state.node_index[self.center_node_id]

        # 准备画笔
        brush_base = QBrush(self.base_color)
        
        # 分组逻辑
        group_base = None
        group_dim = None
        group_hover = None
        group_highlight = None
        
        brush_dim = None
        brush_hover = None
        brush_highlight = QBrush(QColor("#FFD700")) # Gold for highlight
        
        # 预计算颜色
        if self.hover_index != -1:
            # 正在悬停或过渡到悬停
            # 1. 悬停点颜色
            c_hover_target = self._mix_color(self.base_color, self.hover_color, t)
            brush_hover = QBrush(c_hover_target)
            
            # 2. 暗淡点颜色
            c_dim_target = self._mix_color(self.base_color, self.dim_color, t)
            brush_dim = QBrush(c_dim_target)
            
            # 3. 邻居点颜色 -> base_color (brush_base)
            
            if self.neighbor_mask is not None and self.neighbor_mask.shape[0] == pos.shape[0]:
                self._last_neighbor_mask = self.neighbor_mask
                # 只有可见节点才参与绘制
                vis = self.visible_indices
                if len(vis) > 0:
                    # 悬停点
                    is_hover = (vis == self.hover_index)
                    
                    # 优先判定 Hover，如果是 Hover 则忽略 Center 身份
                    # Center 身份判定：是 center 且不是 hover
                    is_center = (vis == center_index) & (~is_hover)
                    
                    # 邻居点 (排除悬停点和中心点)
                    is_neighbor = self.neighbor_mask[vis] & (~is_hover) & (~is_center)
                    
                    # 其他点 (暗淡)
                    is_dim = ~(is_hover | is_neighbor | is_center)
                    
                    group_hover = vis[is_hover]
                    group_highlight = vis[is_center]
                    group_base = vis[is_neighbor]
                    group_dim = vis[is_dim]
            else:
                # 异常情况回退
                group_base = self.visible_indices
                
        else:
            # 无悬停，或者从悬停恢复
            if t <= 0.0:
                # 完全无悬停状态
                vis = self.visible_indices
                if len(vis) > 0:
                    is_center = (vis == center_index)
                    is_base = ~is_center
                    
                    group_highlight = vis[is_center]
                    group_base = vis[is_base]
            else:
                # 正在恢复到无悬停 (使用 last_*)
                c_hover_target = self._mix_color(self.base_color, self.hover_color, t)
                brush_hover = QBrush(c_hover_target)
                
                c_dim_target = self._mix_color(self.base_color, self.dim_color, t)
                brush_dim = QBrush(c_dim_target)
                
                vis = self.visible_indices
                if len(vis) > 0:
                    is_hover = (vis == self.last_hover_index)
                    
                    # 即使是恢复状态，Center也应该保持高亮
                    is_center = (vis == center_index) & (~is_hover)
                    
                    if self._last_neighbor_mask is not None and self._last_neighbor_mask.shape[0] == pos.shape[0]:
                        is_neighbor = self._last_neighbor_mask[vis] & (~is_hover) & (~is_center)
                    else:
                        is_neighbor = np.zeros(len(vis), dtype=bool)
                        
                    is_dim = ~(is_hover | is_neighbor | is_center)
                    
                    group_hover = vis[is_hover]
                    group_highlight = vis[is_center]
                    group_base = vis[is_neighbor]
                    group_dim = vis[is_dim]

        painter.setPen(Qt.NoPen)# type: ignore[arg-type]

        # 批量绘制
        # 1. Base (邻居或普通)
        if group_base is not None and len(group_base) > 0:
            painter.setBrush(brush_base)
            for i in group_base:
                x, y = pos[i]
                r = self.show_radius[i]
                painter.drawEllipse(QPointF(x, y), int(r), int(r))

        # 2. Dim (暗淡)
        if group_dim is not None and len(group_dim) > 0:
            if brush_dim is None: brush_dim = brush_base # Fallback
            painter.setBrush(brush_dim)
            for i in group_dim:
                x, y = pos[i]
                r = self.show_radius[i]
                painter.drawEllipse(QPointF(x, y), int(r), int(r))
                
        # 3. Highlight (永久高亮/中心点)
        if group_highlight is not None and len(group_highlight) > 0:
            painter.setBrush(brush_highlight)
            for i in group_highlight:
                x, y = pos[i]
                r = self.show_radius[i] * 1.2 # Slightly larger
                painter.drawEllipse(QPointF(x, y), int(r), int(r))

        # 4. Hover (悬停/高亮)
        if group_hover is not None and len(group_hover) > 0:
            if brush_hover is None: brush_hover = brush_base # Fallback
            painter.setBrush(brush_hover)
            for i in group_hover:
                x, y = pos[i]
                r = self.show_radius[i] * 1.1 # 放大
                painter.drawEllipse(QPointF(x, y), int(r), int(r))

        # ---------------------画文字-------------------------
        # 性能
        # LOD 当缩放过小时不绘制文本
        # 缓存文字的静态文本，避免重复创建
        # 体验
        # 当缩放在0.7-1时透明度变化
        # 在选中非选中的时候文字的颜色缓缓变化

        scale = 1.0
        if views:
            t = views[0].transform()
            scale = t.m11()

        if scale > self.textshreshold_off:
            prev_text_aa = painter.testRenderHint(QPainter.TextAntialiasing)# type: ignore[arg-type]
            if scale < self.textshreshold_show:#当缩放比例小于1.5时，关闭文本抗锯齿
                painter.setRenderHint(QPainter.TextAntialiasing, False)# type: ignore[arg-type]
                factor = (scale - self.textshreshold_off) / (self.textshreshold_show - self.textshreshold_off)#这个factor是计算透明度的
            else:
                factor = 1.0
            base_alpha = int(255 * factor)
            
            # 优化：批量绘制文本，复用前面计算的分组
            painter.setFont(self.font)
            color_text = QColor("#5C5C5C")
            
            # 1. Base Alpha Group (Neighbors + Hover if not hovering)
            # 包含 group_base 和 (group_hover 如果 hover_index == -1)
            
            # 准备画笔
            color_text.setAlpha(base_alpha)
            pen_base = QPen(color_text)
            painter.setPen(pen_base)
            
            if group_base is not None and len(group_base) > 0:
                for i in group_base:
                    # 检查缓存
                    text = str(self.labels[i])# type: ignore[arg-type]
                    cache_item = self._static_text_cache.get(text)
                    if cache_item is None: continue
                    static_text, w = cache_item
                    
                    x, y = pos[i]
                    r = self.show_radius[i]
                    painter.drawStaticText(QPointF(x - w / 2, y + r), static_text)
            
            if self.hover_index == -1 and group_hover is not None and len(group_hover) > 0:
                 # hover_index == -1 时，group_hover 是 last_hover_index，也用 base_alpha
                 for i in group_hover:
                    text = str(self.labels[i])# type: ignore[arg-type]
                    cache_item = self._static_text_cache.get(text)
                    if cache_item is None: continue
                    static_text, w = cache_item
                    x, y = pos[i]
                    r = self.show_radius[i]
                    painter.drawStaticText(QPointF(x - w / 2, y + r), static_text)

            # 绘制 group_highlight (文字永不暗淡 -> base_alpha)
            # 放在这里使用 pen_base (base_alpha)
            if group_highlight is not None and len(group_highlight) > 0:
                painter.setPen(pen_base) # 确保使用 base_alpha
                for i in group_highlight:
                    text = str(self.labels[i])
                    cache_item = self._static_text_cache.get(text)
                    if cache_item is None: continue
                    static_text, w = cache_item
                    x, y = pos[i]
                    r = self.show_radius[i] * 1.2
                    painter.drawStaticText(QPointF(x - w / 2, y + r), static_text)

            # 2. Dim Alpha Group (暗淡)
            # 使用计算好的 dim alpha
            t_hover = float(self._hover_global)
            fade = 1.0 - 0.7 * t_hover
            alpha_dim = int(base_alpha * fade)
            color_text.setAlpha(alpha_dim)
            pen_dim = QPen(color_text)
            painter.setPen(pen_dim)

            # 绘制 group_dim
            if group_dim is not None and len(group_dim) > 0:
                for i in group_dim:
                    text = str(self.labels[i])# type: ignore[arg-type]
                    cache_item = self._static_text_cache.get(text)
                    if cache_item is None: continue
                    static_text, w = cache_item
                    x, y = pos[i]
                    r = self.show_radius[i]
                    painter.drawStaticText(QPointF(x - w / 2, y + r), static_text)

            painter.setRenderHint(QPainter.TextAntialiasing, prev_text_aa)# type: ignore[arg-type]

        if self.hover_index != -1:# 绘制选中节点的文字（无视普通 LOD 规则）
            i = self.hover_index
            x, y = pos[i]
            r = self.show_radius[i]
            text = str(self.labels[i])# type: ignore[arg-type]
            t = float(self._hover_global)
            font = QFont(self.font)
            base_size = self.font.pointSizeF()
            if base_size <= 0:
                base_size = float(self.font.pointSize())

            # 选中文字比普通大一截；缩小时用 1/scale 抵消视图缩放，保持屏幕上大小基本不变

            target_size = base_size *(1+t * 2.0) 

            if 0.0 < scale <= 1.0:
                size_factor = 1.0 / scale 
            else:
                size_factor = 1.0 / (scale*2.0) +0.5

            font.setPointSizeF(target_size * size_factor)

            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(text)
            rect = fm.boundingRect(text)
            color = QColor("#5C5C5C")
            painter.setPen(QPen(color))
            painter.setFont(font)
            # 在普通文字的基础上向下平移一段，使屏幕上的距离大致恒定
            # 这里按“一个鼠标高度”近似，用字体高度作为基准
            offset_y = (self.font_height * (0.2*t+1)) / scale
            y_base = y + r - rect.top() + offset_y
            painter.drawText(QPointF(x - w / 2, y_base), text)

    def draw_images(self, painter: QPainter):
        pos = self.state.pos
        scene = self.scene()
        views = scene.views() if scene is not None else []
        scale=1.0
        if views:
            t = views[0].transform()
            scale = t.m11()
        #---------------------------绘图片---------------------------
        #当hovered在节点上时，显示封面，或者女优照片
        if self.hover_index != -1 and not self.dragging:
            i = self.hover_index
            x, y = pos[i]
            r = self.show_radius[i]
            nodename=str(self.state.nodes[i])
            if nodename.startswith("a"):
                actress_id=int(nodename[1:])
                actress_image = global_image_loader.get_actress_image(actress_id)
                if actress_image and not actress_image.isNull():
                    img_w_screen = 180.0
                    img_h_screen = 180.0
                    img_w = img_w_screen / scale
                    img_h = img_h_screen / scale

                    rect = QRectF(x  - img_w * 0.5, y-r- img_h-20/scale, img_w, img_h)
                    painter.drawImage(rect, actress_image)
            elif nodename.startswith("w"):
                work_id=int(nodename[1:])
                work_image = global_image_loader.get_work_image(work_id)
                if work_image and not work_image.isNull():
                    img_w_screen = 140
                    img_h_screen = 200
                    img_w = img_w_screen / scale
                    img_h = img_h_screen / scale

                    rect = QRectF(x  - img_w * 0.5, y-r- img_h-20/scale, img_w, img_h)
                    painter.drawImage(rect, work_image)

    def draw_bounding_rect(self, painter: QPainter):
        br = self.boundingRect()
        if not br.isNull():
            painter.setPen(QPen(QColor("#FF0000"), 0.5, Qt.DashLine))# type: ignore[arg-type]
            painter.setBrush(Qt.NoBrush)# type: ignore[arg-type]
            painter.drawRect(br)

    def reset(self, state:RenderState, show_radius, labels=None):
        '''重置这个绘图器'''
        self.state = state
        self.show_radius_base = np.array(show_radius, dtype=np.float32)
        self.radius_factor = 1.0
        self.labels = labels
        node_dict = dict(self.state.G.nodes(data=True))
        if node_dict:
            first_node_id = next(iter(node_dict))
            if self.labels is None and node_dict[first_node_id].get("label", None) is None:
                self.labels = [n for n in self.state.G.nodes()]
            else:
                self.labels = [data.get("label", None) for _, data in self.state.G.nodes(data=True)]
        self._static_text_cache.clear()
        self._init_static_text_cache()
        N = self.state.pos.shape[0]
        self.neighbor_mask = np.zeros(N, dtype=bool)
        self.dragging = False
        self.hover_index = -1
        self.last_hover_index = -1
        self._last_neighbor_mask = None
        self.last_dim_edges = None
        self.last_highlight_edges = None
        self.update_factor()
        self._bounding_rect = None

    def update_factor(self):
        self.side_width=self.side_width_base*self.side_width_factor
        self.show_radius=self.show_radius_base*self.radius_factor#显示圆的半径
        self.textshreshold_off=self.textshreshold_base*self.textshreshold_factor
        self.textshreshold_show=self.textshreshold_off*1.5


    def _init_static_text_cache(self):
        if self.labels is None:
            return
        cache = self._static_text_cache
        # 确保使用正确的字体来计算尺寸
        # 如果 self.font 没有设置 PointSize 或 PixelSize，可能需要检查
        # 假设 self.font 已经是最终渲染时使用的字体
        
        for label in self.labels:
            text = str(label)
            if text not in cache:
                st = QStaticText(text)
                st.prepare(QTransform(), self.font)  # 关键：指定字体进行准备
                cache[text] = (st, st.size().width())

    def _mix_color(self, c1: QColor, c2: QColor, t: float) -> QColor:
        if t <= 0.0:
            return c1
        if t >= 1.0:
            return c2
        r1, g1, b1, a1 = c1.getRgb()# type: ignore[arg-type]
        r2, g2, b2, a2 = c2.getRgb()# type: ignore[arg-type]
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        a = int(a1 + (a2 - a1) * t)
        return QColor(r, g, b, a)

    def advance_hover(self):
        if self.hover_index != -1:
            target = 1.0
        else:
            target = 0.0
        step = self._hover_step
        if target > self._hover_global:
            self._hover_global = min(1.0, self._hover_global + step)
        elif target < self._hover_global:
            self._hover_global = max(0.0, self._hover_global - step)

    def boundingRect(self) -> QRectF:
        '''必须实现的接口'''
        if self._bounding_rect is not None:
            return self._bounding_rect
        if self.state.pos.shape[0] == 0:
            return QRectF()
        xs = self.state.pos[:, 0]
        ys = self.state.pos[:, 1]

        min_x = float(np.min(xs)*3-100)
        max_x = float(np.max(xs)*3+100)
        min_y = float(np.min(ys)*3-100)
        max_y = float(np.max(ys)*3+100)
        self._bounding_rect=QRectF(min_x, min_y, max_x - min_x, max_y - min_y)


        return self._bounding_rect

    #直接点击后释放是跳转，点上去不松开然后移动后松开不跳转，释放节点
    #这一层的事件应该只解决事件的判断与发射信号，不应该处理事件的逻辑

    def mousePressEvent(self, event):
        pos = self.state.pos
        
        if pos.shape[0] == 0:
            super().mousePressEvent(event)
            return

        click = np.array([event.pos().x(), event.pos().y()])

        visible_indices = self.visible_indices
        if visible_indices is None or len(visible_indices) == 0:
            self.selected_index = None
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)# type: ignore[arg-type]
            super().mousePressEvent(event)
            return

        pos_visible = pos[visible_indices]
        dist2_visible = np.sum((pos_visible - click)**2, axis=1)
        local_hit = np.argmin(dist2_visible)
        hit_index = int(visible_indices[local_hit])#找到离点击最近的点

        if dist2_visible[local_hit] < (self.show_radius[hit_index])**2:
            self.selected_index = hit_index
            self.drag_offset = pos[hit_index] - click
            self.hover_index = hit_index
            
            self.update()
            self.nodePressed.emit(hit_index)
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)# type: ignore[arg-type]
            event.accept() # 显式接受事件，确保成为 Grabber，从而接收 Release 事件
        else:
            #print("未选中某节点，进入拖动图面模式")
            self.selected_index = None
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)# type: ignore[arg-type]
            event.ignore() # 未命中则忽略，让 View 处理拖拽
            #QApplication.restoreOverrideCursor()
        
        # super().mousePressEvent(event) # 如果已经 accept 或 ignore，通常不需要调 super，除非需要 QGraphicsItem 的默认行为（如选择）
        # 这里为了保险，如果选中了，调用 super 可能有助于处理选中状态，但因为我们要手动控制 grab，accept 更重要。
        # QGraphicsItem 的默认 mousePressEvent 如果 ItemIsSelectable 会尝试 setSelected。
        if self.selected_index is not None:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selected_index is not None:
            #print("节点正在被拖动")
            new_pos = np.array([event.pos().x(), event.pos().y()]) + self.drag_offset
            self.state.pos[self.selected_index] = new_pos#在拖动时直接改共享内存的pos的位置就行了
            self.nodeDragged.emit(self.selected_index)
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)# type: ignore[arg-type]
            self.update()

    def hoverMoveEvent(self, event):
        pos = self.state.pos
        
        if pos.shape[0] == 0:
            super().hoverMoveEvent(event)
            return

        p = np.array([event.pos().x(), event.pos().y()])

        visible_indices = self.visible_indices
        if visible_indices is None or len(visible_indices) == 0:
            self.selected_index = None
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)# type: ignore[arg-type]
            super().hoverMoveEvent(event)
            return

        pos_visible = pos[visible_indices]
        dist2_visible = np.sum((pos_visible - p)**2, axis=1)
        local_hit = np.argmin(dist2_visible)
        hit_index = int(visible_indices[local_hit])#找到离点击最近的点

        if dist2_visible[local_hit] < (self.show_radius[hit_index])**2:
            if hit_index != self.hover_index:
                self.hover_index = hit_index
                self.last_hover_index = hit_index
                self.nodeHovered.emit(hit_index)

            self.update()
        else:
            if self.hover_index != -1:
                self.last_hover_index = self.hover_index
                self.hover_index = -1
                self.nodeHovered.emit(-1)
                self.update()
        super().hoverMoveEvent(event)

    def mouseReleaseEvent(self, event):
        print(f"释放节点{self.hover_index}")
        if not self.dragging:
            if self.hover_index != -1:
                if event.button() == Qt.LeftButton:
                    self.nodeLeftClicked.emit(self.hover_index)
                if event.button() == Qt.RightButton:
                    self.nodeRightClicked.emit(self.hover_index)
                    print(f"右键点击节点{self.hover_index}")

        self.dragging = False
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)# type: ignore[arg-type]
        index = self.selected_index
        self.nodeReleased.emit(index)
        self.selected_index = None
        self.setCursor(Qt.ArrowCursor)# type: ignore[arg-type]
        
        super().mouseReleaseEvent(event)

    def update_fps(self):
        self.frame_count += 1
        now = time.perf_counter()
        if now - self.last_fps_time >= 1.0:  # 每秒更新一次
            self.current_fps = self.frame_count / (now - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = now
            self.fps.emit(self.current_fps)

class ForceView(QGraphicsView):
    '''负责管理视图与模拟'''
    c_time=Signal(float)
    paint_time=Signal(float)
    scale_changed = Signal(float)
    fps=Signal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QColor("#FFFFFF"))
        self.setRenderHint(QPainter.Antialiasing, True)# type: ignore[arg-type]
        self.setRenderHint(QPainter.TextAntialiasing, True)# type: ignore[arg-type]
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)# type: ignore[arg-type]
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)# type: ignore[arg-type]
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)# type: ignore[arg-type]
        self.setDragMode(QGraphicsView.ScrollHandDrag)# type: ignore[arg-type]
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)# type: ignore[arg-type]

        self.scale_factor = 1.0
        self.axis_items = []
        self._render_active = False 

        # 核心：持有 Controller
        self.view_id = str(uuid.uuid4())#创建视图的时候自动分配uuid
        self.controller = ForceGraphController(self.view_id)
        
        # 信号连接
        self.controller.graph_loaded.connect(self._on_graph_loaded)
        self.controller.frame_ready.connect(self._on_frame_ready)
        
        self.nodelayer = None 
        self.timer_setting()
        
        # 设置场景范围
        rect = QRectF(-5000, -5000, 10000, 10000)
        self._scene.setSceneRect(rect)
    
    @property
    def session(self):
        return self.controller.session

    def load_graph(self, G: Optional[nx.Graph] = None, modify=False):
        self.controller.load_graph(G, modify)

    def _on_graph_loaded(self, state, node_radii):
        self.state = state # View 也保留一份 state 引用用于交互
        
        if self.nodelayer is None:
            self.nodelayer = NodeLayer(state, node_radii)
            if hasattr(self, 'center_node_id'):
                self.nodelayer.center_node_id = self.center_node_id
            self._scene.addItem(self.nodelayer)
            # 连接 NodeLayer 交互信号
            self.nodelayer.nodePressed.connect(self._on_node_pressed)
            self.nodelayer.nodeDragged.connect(self._on_node_dragged)
            self.nodelayer.nodeReleased.connect(self._on_node_released)
            self.nodelayer.nodeLeftClicked.connect(self._on_node_clicked)
            self.nodelayer.nodeRightClicked.connect(self._on_node_right_clicked)
            self.nodelayer.nodeHovered.connect(self._on_node_hovered)
            self.nodelayer.paint_time.connect(self.paint_time.emit)
            self.nodelayer.fps.connect(self.fps.emit)
        else:
            self.nodelayer.reset(state, node_radii)
            if hasattr(self, 'center_node_id'):
                self.nodelayer.center_node_id = self.center_node_id
            self.nodelayer.update_visible_mask()
            
        # 自动适配视图
        QTimer.singleShot(100, lambda: self.fitInView(self.get_content_rect(), Qt.KeepAspectRatio))# type: ignore[arg-type]

    def _on_frame_ready(self, elapsed, active):
        self.c_time.emit(elapsed)
        if active:
            if self.nodelayer: self.nodelayer.update_visible_mask()
            self._request_render_activity()

    def timer_setting(self):
        self._render_timer = QTimer(self)#固定16ms渲染一次
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._on_render_tick)

        self._idle_timer = QTimer(self)#用于在模拟结束后停止渲染
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(1000)
        self._idle_timer.timeout.connect(self._maybe_stop_render_timer)

    def closeEvent(self, event):
        self.controller.shutdown()
        super().closeEvent(event)
    
    def _ensure_render_timer_running(self):
        if not self._render_active:
            self._render_timer.start()
            self._render_active = True

    def _request_render_activity(self):
        self._ensure_render_timer_running()
        self._idle_timer.start()

    def _on_render_tick(self):
        if self.nodelayer:
            self.nodelayer.advance_hover()
            self.nodelayer.update()

    def _maybe_stop_render_timer(self):
        if (not self.controller._sim_active
            and self.nodelayer 
            and not self.nodelayer.dragging
            and self.nodelayer.hover_index == -1):
            # print(f"view_id:{self.view_id}:停止渲染")
            self._render_timer.stop()
            self._render_active = False




    def wheelEvent(self, event):
        '''这个通过滚轮控制缩放'''
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)# type: ignore[arg-type]

        zoom_in = event.angleDelta().y() > 0
        factor: float = 1.15 if zoom_in else 1 / 1.15
        
        # 使用变换矩阵获取当前缩放，比 self.scale_factor 更可靠
        current_scale: float = self.transform().m11()
        new_scale: float = current_scale * factor

        # 放宽缩放限制 (0.01 ~ 100)
        if 0.1 < new_scale < 10:
            self.scale(factor, factor)
            self.scale_factor = new_scale
            self.scale_changed.emit(new_scale)
        event.accept()  # 阻止事件向上传递

    def get_content_rect(self) -> QRectF:
        """获取当前节点分布的实际边界矩形"""
        if self.state.pos.shape[0] == 0:
            return QRectF()
        
        xs = self.state.pos[:, 0]
        ys = self.state.pos[:, 1]
        min_x, max_x = np.min(xs), np.max(xs)
        min_y, max_y = np.min(ys), np.max(ys)
        
        width = max_x - min_x
        height = max_y - min_y
        
        # 留一点边距，比如 5%
        margin_x = width * 0.1
        margin_y = height * 0.1
        
        return QRectF(min_x - margin_x, min_y - margin_y, 
                      width + 2 * margin_x, height + 2 * margin_y)

    def show_coordinate_sys(self,state):
        '''显示坐标轴'''
        if state == Qt.CheckState.Checked:
            print("添加坐标轴")
            pen = QPen(QColor(0, 0, 255))  # 蓝色
            pen.setWidth(2)
            x_axis = QGraphicsLineItem(0, 0, 500, 0)
            x_axis.setPen(pen)
            self._scene.addItem(x_axis)
            pen = QPen(QColor(255, 0, 0))  # 红色
            pen.setWidth(2)
            y_axis = QGraphicsLineItem(0, 0, 0, 500)
            y_axis.setPen(pen)
            self._scene.addItem(y_axis)
            self.axis_items.append(x_axis)
            self.axis_items.append(y_axis)
        else:
            print("删除坐标轴")
            for item in self.axis_items:
                self._scene.removeItem(item)
            self.axis_items=[]
    
    def set_manybodyfstrength(self,num):
        self.controller.update_param("many_strength", float(num))

    def set_centerfstrength(self,num):
        self.controller.update_param("center_strength", float(num) * 0.001)

    def set_linkfstrength(self,num):
        self.controller.update_param("link_strength", float(num) * 0.01)

    def set_linklength(self,num):
        self.controller.update_param("link_distance", float(num))

    def set_sidewidthfactor(self,num:float):
        '''设置线宽系数'''
        print(f"设置线宽系数为{num}")
        if self.nodelayer is not None:
            self.nodelayer.side_width_factor=num
            self.nodelayer.update_factor()
            self.nodelayer.update()

    def set_radiusfactor(self,num:float):
        '''设置圆半径系数'''
        print(f"设置圆半径系数为{num}")
        if self.nodelayer is not None:
            self.nodelayer.radius_factor=num
            self.nodelayer.update_factor()
            self.nodelayer.update()

    def set_textshresholdfactor(self,num:float):
        '''设置文本显示阈值系数'''
        print(f"设置文本显示阈值系数为{num}")
        #传进来是0.1-10
        if self.nodelayer is not None:
            self.nodelayer.textshreshold_factor=num
            self.nodelayer.update_factor()
            self.nodelayer.update()

    def resizeEvent(self, event):
        if self._render_active and self.nodelayer is not None:
            self.nodelayer.update_visible_mask()
        super().resizeEvent(event)

    def scrollContentsBy(self, dx, dy):
        """
        重写滚动事件，用于处理鼠标滚轮滚动。
        当鼠标滚轮滚动时，场景会根据滚动方向和距离进行缩放。
        """
        super().scrollContentsBy(dx, dy)
        if self.nodelayer is not None:
            self.nodelayer.update_visible_mask()

    def _on_node_hovered(self, index):
        '''
        当鼠标悬停在节点上时调用，更新节点的邻居掩码。
        邻居掩码用于渲染时突出显示节点的邻居。是一个布尔数组，
        其中 True 表示对应节点是悬停节点的邻居，False 表示不是。
        前面的部分应当放在nodelayer中去解决的
        '''
        if self.nodelayer is not None and hasattr(self, "state"):
            N = self.state.pos.shape[0]
            if index < 0 or index >= N:
                self.nodelayer.neighbor_mask = np.zeros(N, dtype=bool)
            else:
                neighbors = getattr(self.state, "neighbors", None)
                if neighbors is not None:
                    mask = np.zeros(N, dtype=bool)
                    neigh = neighbors[index]
                    if hasattr(neigh, "size") and neigh.size > 0:
                        mask[neigh] = True
                    mask[index] = False
                    self.nodelayer.neighbor_mask = mask
        self._request_render_activity()

    def _on_node_pressed(self, *args):
        pass

    def _on_node_released(self, *args):
        if args:
            index = args[0]
            if index is not None:
                self.controller.set_dragging(index, False)

    def _on_node_clicked(self, index):
        if not hasattr(self, "state") or index < 0 or index >= len(self.state.nodes):
            return
        nodename = str(self.state.nodes[index])
        if nodename.startswith("a"):
            from ui.navigation.router import Router
            Router.instance().push("single_actress", actress_id=int(nodename[1:]))
            print(f"跳转女优_id{nodename[1:]}")
        elif nodename.startswith("w"):
            from ui.navigation.router import Router
            Router.instance().push("work", work_id=int(nodename[1:]))
            print(f"跳转作品_id{nodename[1:]}")

    def _on_node_right_clicked(self,index):
        if not hasattr(self, "state") or index < 0 or index >= len(self.state.nodes):
            return
        nodename = str(self.state.nodes[index])
        if nodename.startswith("a"):
            from ui.navigation.router import Router
            Router.instance().push("actress_edit", actress_id=int(nodename[1:]))
        elif nodename.startswith("w"):
            from ui.navigation.router import Router
            Router.instance().push("work_edit", work_id=int(nodename[1:]))


    def _on_node_dragged(self, *args):
        if args:
            index = args[0]
            if index is not None:
                self.controller.set_dragging(index, True)
        self._request_render_activity()

    def _restart_simulation(self):
        self.controller.restart_simulation()

    def add_node_runtime(self, node_id, **attrs):
        """运行时动态添加节点"""
        self.controller.add_node_runtime(node_id, **attrs)

    def remove_node_runtime(self, node_id):
        """运行时动态删除节点"""
        self.controller.remove_node_runtime(node_id)
        
    def on_graph_diff(self, changes: list):
        """响应 GraphManager 的增量更新信号"""
        self.controller.apply_graph_diff(changes)

    def add_edge_runtime(self, u, v, **attrs):
        """运行时动态添加边"""
        self.controller.add_edge_runtime(u, v, **attrs)
    
    def remove_edge_runtime(self, u, v):
        """运行时动态删除边"""
        self.controller.remove_edge_runtime(u, v)

    def _pause_simulation(self):
        self.controller.pause_simulation()

    def _resume_simulation(self):
        self.controller.resume_simulation()

    @Slot(bool)
    def show_image(self,show:bool):
        self.nodelayer.show_image=show


class ClickableSlider(QSlider):
    def __init__(self, orientation=Qt.Horizontal, parent=None):# type: ignore[arg-type]
        super().__init__(orientation, parent)
        style = """
    QSlider::groove:horizontal {
        height: 4px;
        background: #d0d0d0;
        margin: 0px;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #5c6bc0;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }
    QSlider::groove:vertical {
        width: 4px;
        background: #d0d0d0;
        margin: 0px;
        border-radius: 2px;
    }
    QSlider::handle:vertical {
        background: #5c6bc0;
        width: 14px;
        height: 14px;
        margin: 0 -5px;
        border-radius: 7px;
    }
    """
        self.setStyleSheet(style)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:# type: ignore[arg-type]
            if self.orientation() == Qt.Horizontal:# type: ignore[arg-type]
                ratio = event.position().x() / max(1, self.width())
            else:
                ratio = 1.0 - event.position().y() / max(1, self.height())
            ratio = float(max(0.0, min(1.0, ratio)))
            value = self.minimum() + int(round(ratio * (self.maximum() - self.minimum())))
            self.setValue(value)
        super().mousePressEvent(event)


class ForceViewControlWidget(QWidget):
    '''控制面板+view的容器'''
    def __init__(self, parent=None):
        super().__init__(parent)

        mainlayout = QVBoxLayout(self)

        self.container = QWidget(self)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        mainlayout.addWidget(self.container)

        #G = generate_similar_graph()
        self.view = ForceView(parent=self.container)
        self.container_layout.addWidget(self.view)

        from ui.basic import IconPushButton
        self.settings_button = IconPushButton(iconpath="settings.svg",color="#5C5C5C",parent=self)

        self.panel = QWidget(self)

        self.panel.setObjectName("my_panel")  # ← 关键：设置唯一名称

        self.panel.setStyleSheet(
            "#my_panel {"
            "    background-color: #fdfdfd; "
            "    border: 1px solid #cccccc; "
            "    border-radius: 6px;"
            "}"
)
        self.panel.setVisible(False)
        panel_layout = QVBoxLayout(self.panel)

        self.label_cal = QLabel()
        self.label_paint = QLabel()

        effect_section = CollapsibleSection("效果", self.panel)
        effect_form = QFormLayout()

        self.manybodyfstrength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.manybodyfstrength.setMinimum(10)
        self.manybodyfstrength.setMaximum(10000)
        self.manybodyfstrength.setValue(50)

        self.centerfstrength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.centerfstrength.setMinimum(1)
        self.centerfstrength.setMaximum(200)
        self.centerfstrength.setValue(1)

        self.linkfstrength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.linkfstrength.setMinimum(1)
        self.linkfstrength.setMaximum(200)
        self.linkfstrength.setValue(20)

        self.linklength = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.linklength.setMinimum(10)
        self.linklength.setMaximum(80)
        self.linklength.setValue(40)

        effect_form.addRow("斥力强度", self.manybodyfstrength)
        effect_form.addRow("中心力强度", self.centerfstrength)
        effect_form.addRow("连接力强度", self.linkfstrength)
        effect_form.addRow("连接距离", self.linklength)
        effect_section.addLayout(effect_form)

        display_section = CollapsibleSection("显示", self.panel)
        display_form = QFormLayout()
        self.show_image=ToggleSwitch(width=48,height=24)
        self.show_image.setChecked(True)
        self.show_image.toggled.connect(self.view.show_image)
        self.textfadeshreshold = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.textfadeshreshold.setMinimum(10)
        self.textfadeshreshold.setMaximum(1000)
        self.textfadeshreshold.setValue(100)

        self.nodesize = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.nodesize.setMinimum(10)
        self.nodesize.setMaximum(300)
        self.nodesize.setValue(100)

        self.linkwidth = ClickableSlider(Qt.Horizontal)  # type: ignore[arg-type]
        self.linkwidth.setMinimum(10)
        self.linkwidth.setMaximum(300)
        self.linkwidth.setValue(100)


        self.show_coordinate_sys = QCheckBox("显示坐标轴", self.panel)
        self.show_coordinate_sys.setChecked(False)
        
        display_form.addRow("显示图片",self.show_image)
        display_form.addRow("文字渐隐", self.textfadeshreshold)
        display_form.addRow("节点大小", self.nodesize)
        display_form.addRow("连线宽度", self.linkwidth)

        display_section.addLayout(display_form)

        self.btn_restart = QPushButton("Restart", self.panel)
        self.btn_pause = QPushButton("Pause", self.panel)
        self.btn_resume = QPushButton("Resume", self.panel)
        self.btn_fitinview=QPushButton("适配视图", self.panel)
        self.btn_add_node = QPushButton("加点", self.panel)
        self.btn_remove_node=QPushButton("减点", self.panel)
        self.btn_add_edge = QPushButton("加边", self.panel)
        self.btn_remove_edge=QPushButton("减边", self.panel)

        self.radio_graph_all = QRadioButton("总图", self.panel)
        self.radio_graph_favorite = QRadioButton("片关系图", self.panel)
        self.radio_graph_test = QRadioButton("2000点图", self.panel)
        self.radio_graph_all.setChecked(True)
        graph_type_layout = QHBoxLayout()

        graph_type_layout.addWidget(self.radio_graph_all)
        graph_type_layout.addWidget(self.radio_graph_favorite)
        graph_type_layout.addWidget(self.radio_graph_test)

        effect_form.addRow("图类型", graph_type_layout)

        test_section = CollapsibleSection("测试", self.panel)

        self.label_scale = QLabel()
        self.view.scale_changed.connect(lambda s: self.label_scale.setText(f"{s:.2f}"))
        test_section.addWidget(self.btn_fitinview)
        
        # 使用自定义的 get_content_rect 替代 itemsBoundingRect
        self.btn_fitinview.clicked.connect(lambda: self.view.fitInView(self.view.get_content_rect(), Qt.KeepAspectRatio))# type: ignore[arg-type]
        
        test_section.addWidget(self.btn_restart)
        test_section.addWidget(self.btn_pause)
        test_section.addWidget(self.btn_resume)
        test_section.addWidget(self.show_coordinate_sys)

        test_section.addWidget(self.btn_add_node)
        test_section.addWidget(self.btn_remove_node)
        test_section.addWidget(self.btn_add_edge)
        test_section.addWidget(self.btn_remove_edge)

        self.btn_add_node.clicked.connect(self.ontest)
        self.btn_remove_node.clicked.connect(lambda:self.view.remove_node_runtime("c200"))
        self.btn_add_edge.clicked.connect(lambda:self.view.add_edge_runtime(1,11))
        self.btn_remove_edge.clicked.connect(self.ontest2)


        self.label_fps = QLabel()
        self.view.fps.connect(lambda s: self.label_fps.setText(f"{s:.2f}"))



        fromlayout=QFormLayout()
        fromlayout.addRow("tick消耗",self.label_cal)
        fromlayout.addRow("paint消耗",self.label_paint)
        fromlayout.addRow("当前缩放",self.label_scale)
        fromlayout.addRow("当前帧率",self.label_fps)
        test_section.addLayout(fromlayout)

        run_layout = QHBoxLayout()
        panel_layout.addLayout(run_layout)

        panel_layout.addWidget(effect_section)
        panel_layout.addWidget(display_section)
        panel_layout.addWidget(test_section)

        effect_section.toggled.connect(self._on_section_toggled)
        display_section.toggled.connect(self._on_section_toggled)
        test_section.toggled.connect(self._on_section_toggled)



        self.show_coordinate_sys.checkStateChanged.connect(self.view.show_coordinate_sys)
        self.manybodyfstrength.valueChanged.connect(self.view.set_manybodyfstrength)
        self.centerfstrength.valueChanged.connect(self.view.set_centerfstrength)
        self.linkfstrength.valueChanged.connect(self.view.set_linkfstrength)
        self.linklength.valueChanged.connect(self.view.set_linklength)
        self.linkwidth.valueChanged.connect(lambda x: self.view.set_sidewidthfactor(float(x)/100.0))

        self.view.c_time.connect(lambda c: self.label_cal.setText(f"{c:.3f}ms"))
        self.view.paint_time.connect(lambda c: self.label_paint.setText(f"{c:.3f}ms"))
        self.nodesize.valueChanged.connect(lambda x: self.view.set_radiusfactor(float(x)/100.0))
        self.textfadeshreshold.valueChanged.connect(lambda x:self.view.set_textshresholdfactor(float(x)/100.0))

        self.btn_restart.clicked.connect(self.view._restart_simulation)
        self.btn_pause.clicked.connect(self.view._pause_simulation)
        self.btn_resume.clicked.connect(self.view._resume_simulation)
        self.radio_graph_favorite.toggled.connect(
            lambda checked: self._switch_graph("favorite") if checked else None
        )
        self.radio_graph_all.toggled.connect(
            lambda checked: self._switch_graph("all") if checked else None
        )
        self.radio_graph_test.toggled.connect(
            lambda checked: self._switch_graph("test") if checked else None
        )

        self.settings_button.clicked.connect(self._toggle_panel)

        self.settings_button.raise_()
        self.panel.raise_()

    def ontest(self):
        self.view.add_node_runtime("c200")
        self.view.add_edge_runtime(1,"c200")

    def ontest2(self):
        self.view.remove_node_runtime("c200")
        self.view.remove_edge_runtime(1,"c200")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_panel_geometry()

    def _update_panel_geometry(self) -> None:
        rect = self.rect()
        if rect.isEmpty():
            return
        margin = 10
        offset_x = 30
        offset_y = 30
        btn_size: QSize = self.settings_button.sizeHint()
        self.settings_button.move(
            max(margin, rect.width() - btn_size.width() - margin - offset_x),
            margin + offset_y,
        )
        if self.panel.isVisible():
            panel_width: int = min(250, max(0, rect.width() - 2 * margin))
            panel_height: int = self.panel.sizeHint().height()
            self.panel.resize(panel_width, panel_height)
            self.panel.move(
                max(margin, rect.width() - panel_width - margin-offset_x),
                btn_size.height() + 2 * margin+offset_y,
            )
            self.panel.raise_()
            self.settings_button.raise_()

    def _on_section_toggled(self, checked: bool):
        if not self.panel.isVisible():
            return
        self.panel.adjustSize()
        self._update_panel_geometry()

    def _toggle_panel(self):
        if self.panel.isVisible():
            self.panel.setVisible(False)
        else:
            self.panel.setVisible(True)
            self.panel.adjustSize()
            self._update_panel_geometry()
            self.panel.raise_()
            self.settings_button.raise_()

    def _switch_graph(self, mode: str):
        from core.graph.graph_manager import GraphManager
        manager = GraphManager.instance()

        # 无论切换到哪个模式，先尝试断开信号连接，避免重复连接或错误接收
        try:
            manager.graph_diff_signal.disconnect(self.view.on_graph_diff)
        except (TypeError, RuntimeError):
            pass # 之前未连接，忽略错误

        if mode == "favorite":
            G = manager.get_graph()
            # 仅在 favorite 模式下连接增量更新信号
            manager.graph_diff_signal.connect(self.view.on_graph_diff)
        elif mode == "all":
            G = generate_similar_graph()
        else:
            G = generate_random_graph(2001,1)
        self.view.load_graph(G)

    def load_graph(self,G):
        self.view.load_graph(G)

def main():
    from core.graph.graph_filter import EgoFilter
    from core.graph.graph_manager import GraphManager

    get_global_simulation_process()
    app = QApplication(sys.argv)

    # 1. 显式初始化 GraphManager，确保数据已加载
    manager = GraphManager.instance()
    if not manager._initialized:
        manager.initialize()

    window = QMainWindow()
    window.setWindowTitle("ForceView - Ego Graph (Actress ID 100)")
    window.resize(1000, 700)

    central_widget = ForceViewControlWidget()
    window.setCentralWidget(central_widget)
    
    view_session = central_widget.view.session
    #central_widget.view.center_node_id = "a100"
    
    # 2. 设置过滤器并加载
    #view_session.set_filter(EgoFilter(center_id="a100", radius=2))
    view_session.reload()

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    print("当前文件:", __file__)
    print("当前目录:", os.path.dirname(__file__))
    target_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    print("目标路径:", target_path)
    print("路径是否存在:", os.path.exists(target_path))
    main()

