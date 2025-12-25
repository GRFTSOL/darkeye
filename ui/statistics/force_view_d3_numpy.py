

#----------------------------------------------------------
import sys,numba
import math
from collections import defaultdict
import random
from typing import List, Dict, Tuple, Optional,Any
import numpy as np
import networkx as nx
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsSimpleTextItem, QPushButton, QVBoxLayout, QWidget,QGraphicsRectItem,QHBoxLayout,QCheckBox,QLabel,QSlider,QFormLayout,QGraphicsItem
)
from PySide6.QtGui import QBrush, QPen, QColor, QPainter,QFont,QFontMetrics
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF,Signal,QObject

import time
import functools
def timeit(func):
    """装饰器：打印函数执行耗时"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        etime=(end - start)*1000
        print(f"⏱ {func.__name__} 执行耗时: {etime:.1f} ms")
        return result
    return wrapper


#现在弄向化的版本，计算与显示分离，多了一步同步
#d3.js很强，就js的效率，2000个节点依然有20帧也就是消耗50ms

#800个节点20ms

#用四叉树算法的移植效率600个节点比暴力算要强了,即使是python那种慢如狗的递归

#现在的问题就是效率不够高

#目前400个节点，10ms
#目前600个节点，20ms
#目前700个节点，25ms
#目前800个节点，40ms
#目前1000个节点，45ms


class SimulationState:
    """统一的物理状态存储，用于各个 Force 共享访问"""
    def __init__(self, G: nx.Graph,positions,scale:int):
        self.G = G
        self.nodes = list(G.nodes())
        self.node_index = {n: i for i, n in enumerate(self.nodes)}
        self.edges = np.array(
            [(self.node_index[u], self.node_index[v]) for u, v in G.edges()],
            dtype=np.int32
        )

        N = len(self.nodes)
        #(N,2)
        self.pos = np.array([positions[n] for n in self.G.nodes()], dtype=np.float32) * scale
        #(N,2)
        self.vel = np.zeros((N, 2), dtype=np.float32)
        #(N)
        self.mass = np.ones(N, dtype=np.float32)
        #(N)
        self.dragging=np.zeros(N, dtype=bool)
        
        deg = dict(G.degree())
        #(N)
        self.degree = np.array([deg[n] for n in self.nodes], dtype=np.float32)
        #(N)
        self.radii=np.ones(N, dtype=np.float32)#这个是碰撞半径
        # 假设 degree 已经是 numpy 数组
        #min_radius = 4.0
        #max_radius = 12.0

        # 线性映射 degree -> 半径
        #deg_min, deg_max = self.degree.min(), self.degree.max()
        #if deg_max > deg_min:
        #    self.radii = min_radius + (self.degree - deg_min) / (deg_max - deg_min) * (max_radius - min_radius)

class NodeLayer(QObject,QGraphicsItem):
    """
    高性能绘制所有节点的自定义图层，直接从 SimulationState.pos 中读取坐标。
    """
    nodePressed = Signal(int)  # 发出被点击节点的索引
    nodeDragged = Signal(int, float, float)  # index, new_x, new_y
    nodeReleased = Signal(int)  # index
    def __init__(self, state:SimulationState,show_radius,labels=None, default_radius=50, color="#66ccff",parent=None):
        QObject.__init__(self, parent)  # 先初始化 QObject
        QGraphicsItem.__init__(self)    # 再初始化 QGraphicsItem
        self.state = state  # SimulationState
        self.default_radius = default_radius
        self.color = QColor(color)
        self.edge_color=QColor("#cccccc")
        self.setZValue(1)  # 确保在边上方
        self.show_raidus=show_radius
        self.labels=labels
        node_dict=dict(self.state.G.nodes(data=True))
        first_node_id = next(iter(node_dict))
        if self.labels is None and node_dict[first_node_id].get("label", None) is None:
            self.labels = [str(n) for n in self.state.G.nodes()]
        else:
            self.labels = [data.get("label", None) for _, data in self.state.G.nodes(data=True)]
        
        # 当前选中节点
        self.selected_index = None
        self.dragging = False#判断鼠标是否正在拖动
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)  # 可选

    def boundingRect(self) -> QRectF:
        # 必须返回覆盖全部节点的矩形
        if self.state.pos.shape[0] == 0:
            return QRectF()
        x_min, y_min = np.min(self.state.pos, axis=0)
        x_max, y_max = np.max(self.state.pos, axis=0)
        r = self.default_radius
        return QRectF(x_min - r, y_min - r, (x_max - x_min) + 2*r, (y_max - y_min) + 2*r)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(QPen(Qt.black, 0.4))
        painter.setBrush(QBrush(self.color))
        pos = self.state.pos

        edges = getattr(self.state, "edges", None)
        if edges is not None and len(edges) > 0:
            painter.setPen(QPen(self.edge_color, 0.5))
            src = pos[edges[:, 0]]
            dst = pos[edges[:, 1]]
            for (x1, y1), (x2, y2) in zip(src, dst):
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        font = QFont("Microsoft YaHei", 6)
        metrics = QFontMetrics(font)
        height = metrics.height()
        painter.setFont(font)
        for i, ((x, y), r) in enumerate(zip(pos, self.show_raidus)):
            painter.drawEllipse(QPointF(x, y), r, r)#绘制节点

        painter.setPen(QPen(QColor("#000000")))  # 道奇蓝
        for i, ((x, y), r) in enumerate(zip(pos, self.show_raidus)):
            text = str(self.labels[i])#+"|"+str(x)+","+str(y)
            width = metrics.horizontalAdvance(text)
            # 文本位置在圆的右上角偏移
            painter.drawText(QPointF(x-width/2, y + r + height), text)

    #直接点击后释放是跳转，点上去不松开然后移动后松开不跳转，释放节点
    def mousePressEvent(self, event):
        pos = self.state.pos
        click = np.array([event.pos().x(), event.pos().y()])#目前这个好像有点bug，可能会点不到

        dist2 = np.sum((pos - click)**2, axis=1)
        hit_index = np.argmin(dist2)
        if dist2[hit_index] < (self.show_raidus[hit_index] * 1.5)**2:
            print(f"选中某节点{hit_index}")
            self.selected_index = hit_index
            self.state.dragging[hit_index]=True
            self.drag_offset = pos[hit_index] - click
            #self.setCursor(Qt.PointingHandCursor)
            self.update()
            self.nodePressed.emit(hit_index)
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        else:
            print("未选中某节点，进入拖动图面模式")
            self.selected_index = None
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)
            #QApplication.restoreOverrideCursor()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selected_index is not None:
            print("节点正在被拖动")
            new_pos = np.array([event.pos().x(), event.pos().y()]) + self.drag_offset
            self.state.pos[self.selected_index] = new_pos
            self.nodeDragged.emit(self.selected_index, *new_pos)
            self.dragging = True
            self.update()

    def mouseReleaseEvent(self, event):
        if self.dragging:
            print("释放节点为自由状态")
        else:
            print("跳转节点")
        self.dragging = False
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.nodeReleased.emit(self.selected_index)
        self.selected_index=None
        self.state.dragging[self.selected_index]=False
        
        #QApplication.restoreOverrideCursor()
        super().mouseReleaseEvent(event)

# ------------------------------
# Barnes-Hut Quadtree
# ------------------------------
# A simple Barnes-Hut style quadtree for many-body acceleration.
# This is a minimal implementation sufficient for ManyBodyForce.compute_force_on
# 现在一个叶子节点最多一个点，
#这个要弄向量化，面向对象递归计算的效率太低了



class QuadTreeNode:
    def __init__(self, bbox: QRectF,state:SimulationState):
        self.bbox = bbox  # QRectF(x,y,w,h)
        self.state=state
        self.children = [None, None, None, None]  # NW, NE, SW, SE
        self.particle: int = -1  # 存储单个粒子的index从0开始,-1代表无粒子
        self.total_mass = 0.0
        self.cm=np.zeros(2) 


    def is_leaf(self):
        return self.children[0] is None

    def subdivide(self):
        x, y, w, h = self.bbox.x(), self.bbox.y(), self.bbox.width(), self.bbox.height()
        hw, hh = w / 2.0, h / 2.0
        self.children = [
            QuadTreeNode(QRectF(x, y, hw, hh),self.state),             # NW
            QuadTreeNode(QRectF(x + hw, y, hw, hh),self.state),        # NE
            QuadTreeNode(QRectF(x, y + hh, hw, hh),self.state),        # SW
            QuadTreeNode(QRectF(x + hw, y + hh, hw, hh),self.state),   # SE
        ]
        self.total_mass = 0.0
        self.cm=np.zeros(2)

    def contains(self, x, y):
        return self.bbox.contains(QPointF(x, y))

    def insert(self, index:int):
        #x, y = self.state.pos[index:0], self.state.pos[index:1]
        pos=self.state.pos[index]
        mass=self.state.mass[index]
        if self.particle ==-1 and self.is_leaf():#是叶子节点而且是空的
            self.particle = index
            self.total_mass = mass
            self.cm=mass*pos#后面统一修正
            return
        if self.is_leaf() and self.particle != -1:#是叶子节点但是满的
            # subdivide and re-insert existing particle
            existing = self.particle
            self.particle = -1
            self.subdivide()
            self._put_into_child(existing)#将老节点放进去
            
        # put new particle into proper child
        self._put_into_child(index)#分裂后将新添加的放到正确的位置上
        # update mass & center sums
        self.total_mass += mass
        self.cm=mass*pos

    def _put_into_child(self, index:int):
        x, y = self.state.pos[index,0], self.state.pos[index,1]
        for child in self.children:
            if child.bbox.contains(QPointF(x, y)):
                child.insert(index)
                #这里要不要更新质量与质心
                #self.total_mass += node.mass
                #self.cm_x += x * node.mass
                #self.cm_y += y * node.mass
                return
        # fallback: put into first child if none contains (edge case)
        #点在边上时候
        nearest = min(self.children, key=lambda c: _dist_point_rect(x, y, c.bbox))
        nearest.insert(index)
        #这个有问题，当点在边界的时候
        #self.total_mass += node.mass
        #self.cm_x += x * node.mass
        #self.cm_y += y * node.mass

    def finalize(self):
        # normalize center of mass
        if self.is_leaf():#是叶子而且有质量
            if self.total_mass > 0:
                self.cm /= self.total_mass
        # finalize children
        else:
            #先计算子节点的
            self.total_mass = 0.0
            self.cm=np.zeros(2) 
            for c in self.children:
                #对子叶节点计算一圈
                c.finalize()
                self.cm=self.cm+c.cm*c.total_mass
                self.total_mass+=c.total_mass#质量加起来
            if self.total_mass > 0:
                self.cm /= self.total_mass


def _dist_point_rect(px, py, rect: QRectF):
    # distance from point to rectangle center (used for fallback)
    cx = rect.x() + rect.width() / 2.0
    cy = rect.y() + rect.height() / 2.0
    return math.hypot(px - cx, py - cy)


class Force:
    def initialize(self,state:SimulationState): pass
    def apply(self, nodes, alpha): pass

class CenterForce(Force):
    '''O(n)'''
    def __init__(self, cx=0.0, cy=0.0, strength=0.1):
        self.cx = cx
        self.cy = cy
        self.strength = strength

    def initialize(self,state):
        self.state = state  # 共享 SimulationState

    
    def apply(self, alpha: float):
        s = self.state
        center = np.array([self.cx, self.cy], dtype=float)

        # 计算每个节点到中心的偏移向量
        delta = center - s.pos  # (N,2)
        # 速度更新
        s.vel += delta * (self.strength * alpha)

class LinkForce(Force):
    '''这个在连接少的时候消耗是很少的'''
    def __init__(self, k=0.02, distance=30.0):
        self.k = k
        self.distance = distance

    def initialize(self,state):
        # nodes not needed here, links already hold node refs
        self.state=state
    

    def apply(self, alpha: float):

        src = self.state.edges[:, 0]
        dst = self.state.edges[:, 1]

        p1 = self.state.pos[src]
        p2 = self.state.pos[dst]
        delta = p2 - p1
        dist = np.linalg.norm(delta, axis=1, keepdims=True) + 1e-6
        force = (dist - self.distance) / dist * self.k * alpha
        f = delta * force
        np.add.at(self.state.vel, src, f)#两个点各自受力
        np.add.at(self.state.vel, dst, -f)

class ManyBodyForce(Force):
    """Repulsive force. Modes:
       - mode='brute' : O(N^2) pairwise repulsion
       - mode='barnes' : Barnes-Hut approximate via QuadTree
       这个是最消耗时间的，需要大量的优化
    """
    def __init__(self, strength=100.0, theta=0.6,mode="brute"):
        self.strength = strength
        self.theta = theta
        self.theta2=theta*theta
        self.root=None#这个是给点建立的树
        self.mode=mode

    def initialize(self,state):
        self.state=state

    def apply(self, alpha: float):
        N = self.state.pos.shape[0]
        if N<2000:
            # 位置差矩阵 (N,N,2)
            delta = self.state.pos[:, None, :] - self.state.pos[None, :, :]
            # 距离平方矩阵 (N,N)
            dist2 = np.sum(delta**2, axis=-1) + 1e-6
            # 避免自己对自己产生力
            np.fill_diagonal(dist2, np.inf)
            # 斥力大小: F = k * m_i * m_j / dist2
            force_scalar = self.strength * (self.state.mass[:, None] * self.state.mass[None, :]) / dist2
            # force 矩阵: shape (N,N,2)
            force_vec = force_scalar[..., None] * (delta / np.sqrt(dist2)[..., None])
            # 总力: 对每个节点求和
            total_force = np.sum(force_vec, axis=1)
            # 更新速度
            self.state.vel += total_force * alpha
        else:#使用Barnes-Hut四叉树计算,不知道为什么，这个计算效率非常的低
            self.root = self._build_quadtree()#这个建树似乎有大问题
            #print(self.root.children[0].total_mass)
            start=time.perf_counter()
            for i in range(N):
                fx, fy = self._compute_force_barnes_on_iterative(self.root, i)
                self.state.vel[i,0] += fx * alpha
                self.state.vel[i,1] += fy * alpha
            print((time.perf_counter() - start) * 1000.0)  # 转成ms

    
    def _build_quadtree(self)->QuadTreeNode:
        '''建四叉树'''
        #计算点集的最大外框
        rect = compute_bounding_box_numpy(self.state.pos)
        margin = 20
        bbox = QRectF(rect.x() - margin, rect.y() - margin, rect.width() + 2*margin, rect.height() + 2*margin)
        
        root = QuadTreeNode(bbox,self.state)#这里建树
        for i in range(self.state.pos.shape[0]):
            root.insert(i)
        root.finalize()
        return root

    def _compute_force_barnes_on_iterative(self, root: QuadTreeNode, target: int) -> Tuple[float, float]:
        """迭代版本，避免递归开销"""
        distance_max2 = 90000
        fx_total, fy_total = 0.0, 0.0
        stack = [root]
        
        target_pos = self.state.pos[target]  # 预先获取目标位置
        
        while stack:
            node = stack.pop()
            
            if node.total_mass == 0:
                continue
                
            # 如果是叶子节点且包含目标粒子，跳过
            if node.is_leaf() and node.particle == target:
                continue
                
            dx, dy = node.cm - target_pos
            dist2 = dx*dx + dy*dy + 1e-6
            
            s = max(node.bbox.width(), node.bbox.height())
            
            # Barnes-Hut criterion
            if node.is_leaf() or (s*s / self.theta2 < dist2):
                if dist2 > distance_max2:
                    continue
                dist = math.sqrt(dist2)  # 比hypot快
                force = self.strength * node.total_mass / dist2
                fx_total -= force * (dx / dist)
                fy_total -= force * (dy / dist)
            else:
                # 将子节点加入栈（逆序以保证处理顺序）
                for child in reversed(node.children):
                    stack.append(child)
                    
        return fx_total, fy_total

    def _compute_force_barnes_on(self, root: QuadTreeNode, target:int)-> Tuple[float, float]:
        #不知道为什么这个效率非常的低
        # recursively compute approximate repulsion on target
        distance_max2=90000#最大计算斥力距离，当距离超过这个时不计算距离

        def recurse(node: QuadTreeNode)->Tuple[float, float]:
            if node.total_mass == 0:#当节点为空时
                return 0.0, 0.0
            # If this leaf and contains exactly p (or single particle), ignore self,自己与自己没有斥力
            if node.is_leaf() and (node.particle == target ):
                return 0.0, 0.0
            
            dx, dy =node.cm-self.state.pos[target]
            dist2=dx*dx+dy*dy+1e-6#防止除以0的错误

            s = max(node.bbox.width(), node.bbox.height())
            # Barnes-Hut criterion，符合这个规则的就当作一个质点处理
            if  node.is_leaf() or s*s /self.theta2 < dist2 :
                if dist2>distance_max2:#当距离太远的时候直接不计算
                    return 0.0, 0.0
                # treat node as single body
                dist = math.hypot(dx, dy) + 1e-6
                force = self.strength * node.total_mass / dist2
                return -force * (dx / dist), -force * (dy / dist)
            else:#不符合迭代每个子节点计算每块的力加起来
                fx = fy = 0.0
                for c in node.children:
                    cfx, cfy = recurse(c)
                    fx += cfx; fy += cfy
                return fx, fy
        return recurse(root)

class CollisionForce(Force):
    """Collision (prevent overlap) using quadtree visit and local corrections (D3-style).
    1.暴力计算
    2.四叉树加速
    3.哈希网格在600个节点以上时比暴力计算更快，而且没有numba加速
    """
    def __init__(self, radius=20, strength=1.0, iterations=1,mode="brute"):

        self.strength = strength
        self.iterations = iterations
        self.radius=radius
        self.mode=mode

    def initialize(self,state):
        self.state=state
        self.state.radii=self.state.radii*self.radius

    @timeit
    def apply(self, alpha: float):
        pos = self.state.pos    # (N,2)
        vel = self.state.vel    # (N,2)
        radii = self.state.radii  # (N)

        N = pos.shape[0]
        if N < 2:
            return  # 少于两个节点，不用计算
        if N<600:#小于600个节点时暴力计算更快
            for _ in range(self.iterations):
                # 1. 位置差矩阵 (N,N,2)
                delta = pos[:, None, :] - pos[None, :, :]  

                # 2. 距离平方矩阵 (N,N)
                dist2 = np.sum(delta**2, axis=-1) + 1e-9  

                # 3. 半径和矩阵
                r_sum = radii[:, None] + radii[None, :]

                # 4. 碰撞掩码（上三角避免重复）
                mask = (dist2 < r_sum**2) & (np.triu(np.ones((N, N), dtype=bool), 1))

                if not np.any(mask):
                    break  # 没有碰撞，提前退出

                # 5. 实际距离
                dist = np.sqrt(dist2[mask])
                overlap = (r_sum[mask] - dist) / dist * 0.5 * self.strength * alpha

                # 6. 位移向量
                dx = delta[:,:,0][mask] * overlap
                dy = delta[:,:,1][mask] * overlap

                # 7. 索引
                i_idx, j_idx = np.where(mask)

                # 8. 更新速度
                np.add.at(vel[:,0], i_idx, dx)
                np.add.at(vel[:,0], j_idx, -dx)
                np.add.at(vel[:,1], i_idx, dy)
                np.add.at(vel[:,1], j_idx, -dy)
        else:#于600时使用网格哈希加速
            apply_gridhash_numba(pos, vel, radii, N, alpha, self.iterations, self.strength,1024,32)


def apply_gridhash_numba(pos, vel, radii, N, alpha, iterations, strength, max_cells, max_per_cell):
    max_r = np.max(radii)
    cell_size = max_r * 2.0

    grid_counts = np.zeros(max_cells, dtype=np.int32)
    grid_cells = -np.ones((max_cells, max_per_cell), dtype=np.int32)

    for it in range(iterations):
        grid_counts[:] = 0
        # --- 填充网格 ---
        for i in range(N):
            gx = int(pos[i,0] // cell_size)
            gy = int(pos[i,1] // cell_size)
            cell_idx = ((gx*31 + gy) % max_cells + max_cells) % max_cells
            count = grid_counts[cell_idx]
            if count < max_per_cell:
                grid_cells[cell_idx, count] = i
                grid_counts[cell_idx] += 1

        # --- 遍历节点 ---
        for i in range(N):
            xi, yi = pos[i,0], pos[i,1]
            ri = radii[i]
            gx = int(xi // cell_size)
            gy = int(yi // cell_size)
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    cx = gx + dx
                    cy = gy + dy
                    cell_idx = ((cx*31 + cy) % max_cells + max_cells) % max_cells
                    count = grid_counts[cell_idx]
                    for k in range(count):
                        j = grid_cells[cell_idx,k]
                        if j <= i:
                            continue
                        dxn = xi - pos[j,0]
                        dyn = yi - pos[j,1]
                        dist2 = dxn*dxn + dyn*dyn
                        rj = radii[j]
                        rsum = ri + rj
                        if dist2 < rsum*rsum and dist2 > 1e-9:
                            dist = np.sqrt(dist2)
                            overlap = (rsum - dist) / dist * 0.5 * strength * alpha
                            offset_x = dxn * overlap
                            offset_y = dyn * overlap
                            vel[i,0] += offset_x
                            vel[i,1] += offset_y
                            vel[j,0] -= offset_x
                            vel[j,1] -= offset_y



def compute_bounding_box_numpy(pos) -> QRectF:
    """使用NumPy加速计算外接矩形"""

    min_coords = np.min(pos, axis=0)
    max_coords = np.max(pos, axis=0)
    
    return QRectF(
        min_coords[0], min_coords[1],
        max_coords[0] - min_coords[0],
        max_coords[1] - min_coords[1]
    )

# ------------------------------
# Simulation controller
# ------------------------------
class Simulation:
    def __init__(self, G: nx.Graph,positions,scale):#包括图，初始位置与放大系数

        self.forces: Dict[str, Force] = {}
        self.state=SimulationState(G,positions,scale)#这个状态只在开始时运行一次

        # physics params
        self.alpha = 1.0
        self.alpha_decay = 0.03
        self.alpha_min = 0.001

        self.velocity_decay = 0.6  # similar to d3.velocityDecay
        self.dt = 0.1     #模拟时间间隔
        self.max_disp = 40.0#每次模拟最大位移距离

        # internal
        self._active = False

    def add_force(self, name: str, force: Force):
        self.forces[name] = force
        force.initialize(self.state)

    def remove_force(self, name: str):
        if name in self.forces:
            del self.forces[name]


    def tick(self):
        '''单步模拟核心函数'''
        if self.alpha <= self.alpha_min:
            self._active = False
            return
        # apply each force in turn (each modifies node.vx/vy)
        for f in list(self.forces.values()):
            f.apply(self.alpha)#现在的思路就是力只更新速度，位移统一更新
        # integrate velocities -> positions

        total_speed=self.integrate()
        # cool down
        self.alpha *= (1.0 - self.alpha_decay)
        avg_speed = total_speed / max(1, len(self.state.nodes))
        if avg_speed < 0.01 and self.alpha < 0.05:
            self._active = False

    def integrate(self):
        """向量化的节点积分更新"""
        pos = self.state.pos      # (N, 2)
        vel = self.state.vel      # (N, 2)
        dragging = self.state.dragging  # (N,) bool 数组

        # === 参数 ===
        dt = self.dt
        decay = self.velocity_decay
        max_disp = self.max_disp
        tug = 0.05

        # === 速度衰减 ===
        vel *= decay  # 所有节点同时乘以衰减系数

        # === 普通节点（非拖拽）===
        moving_mask = ~dragging
        if np.any(moving_mask):
            # 位移
            disp = vel[moving_mask] * dt  # (M, 2)
            disp_len = np.linalg.norm(disp, axis=1)

            # 限制最大位移
            too_far = disp_len > max_disp
            if np.any(too_far):
                scale = (max_disp / disp_len[too_far])[:, None]
                disp[too_far] *= scale
                vel[moving_mask][too_far] = disp[too_far] / dt

            # 更新位置
            pos[moving_mask] += disp

        # === 拖拽中的节点 ===
        #if np.any(dragging):
        #    pass
            #拖拽节点：不施加物理偏移
            # 拖拽节点：只施加少量物理偏移
            #disp_drag = vel[dragging] * dt * tug
            #pos[dragging] += disp_drag

        # === 计算整体速度大小（用于判断稳定性）===
        total_speed = np.sum(np.abs(vel))
        return total_speed

    def start(self):
        self._active = True

    def stop(self):
        self._active = False

    def pause(self):
        self._active = False

    def resume(self):
        if self.alpha > self.alpha_min:
            self._active = True

    def restart(self):
        self.alpha = 1.0
        self._active = True

    def active(self):
        return self._active

# ------------------------------
# A QGraphicsView that uses Simulation
# ------------------------------
class ForceView(QGraphicsView):
    c_time=Signal(float)
    def __init__(self, G: Optional[nx.Graph] = None, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self.node_items = {}
        self.edges = []
        self.scale_factor=1
        self.axis_items=[]
        self.show_quadtree=False#默认不显示
        
        # build graph
        self.G = G if G is not None else nx.fast_gnp_random_graph(800, 0.003)
        # get positions via networkx spring layout (precompute)
        #初始布局的计算
        positions = nx.spring_layout(self.G, k=0.1, iterations=50, seed=42)
        positions =nx.fruchterman_reingold_layout(self.G, pos=positions, dim=2, scale=1.0, center=None, iterations=50)
        scale = 400.0
        
        self.simulation = Simulation(self.G,positions,scale)#把计算的出的初始位置也输入进去
        # add forces
        self.many = ManyBodyForce(strength=800.0, theta=0.6,mode="brute")
        self.simulation.add_force("manybody", self.many)
        self.link = LinkForce(k=0.2, distance=40.0)
        self.simulation.add_force("link", self.link)
        self.center = CenterForce(0.0, 0.0, strength=0.01)
        self.simulation.add_force("center", self.center)
        #self.collide = CollisionForce(radius=20.0, strength=2.0, iterations=1,mode="brute")
        #self.simulation.add_force("collide", self.collide)

        self.nodelayer=NodeLayer(self.simulation.state,compute_node_radii(self.G))
        self.scene.addItem(self.nodelayer)
        self.nodelayer.nodePressed.connect(self.simulation.restart)
        self.nodelayer.nodeDragged.connect(self.simulation.restart)
        self.nodelayer.nodeReleased.connect(self.simulation.restart)

        # timer-driven ticks
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(16)

        # 动态帧控制参数
        self._target_frame_time = 16  # 目标帧间隔(ms) ≈ 60 FPS
        self._min_interval = 10
        self._max_interval = 100

        self.simulation.start()
        # set initial scene rect once
        self._update_scene_rect(init=True)
    
    
    def _on_timer(self):
        
        start = time.perf_counter()

        if self.show_quadtree:
            self._clear_quadtree_visuals()

        # === 执行一次物理模拟 ===
        if self.simulation.active():
            self.simulation.tick()

        self.nodelayer.update()
        elapsed = (time.perf_counter() - start) * 1000.0  # 转成ms
        self.c_time.emit(elapsed)

        #更新要显示的内容
        if self.show_quadtree:
            self._draw_quadtree_simple(self.many.root)

    def _update_scene_rect(self, init=False):
        rect = self.scene.itemsBoundingRect()
        if init:
            if rect.width() < 10 or rect.height() < 10:
                rect = QRectF(-400, -300, 800, 600)
            rect = rect.adjusted(-200, -200, 200, 200)
            self.scene.setSceneRect(rect)
        else:
            # do not constantly reset rect to avoid view jumping; optionally expand if node leaves
            current = self.scene.sceneRect()
            need_expand = False
            for n in self.node_items.values():
                p = n.pos()
                if not current.contains(p):
                    need_expand = True
                    break
            if need_expand:
                new_rect = current.adjusted(-400, -400, 400, 400)
                self.scene.setSceneRect(new_rect)

    def _clear_quadtree_visuals(self):
        """清除之前绘制的四叉树框"""
        # 保存需要保留的items（节点和边）
        items_to_remove = []
        for item in self.scene.items():
            if isinstance(item, QGraphicsRectItem):  # 移除矩形框
                items_to_remove.append(item)
        
        # 清除场景并重新添加需要保留的items
        for item in items_to_remove:
            self.scene.removeItem(item)

    def _draw_quadtree_simple(self, node: QuadTreeNode, max_depth=8, depth=0):
        """简化版四叉树绘制，限制深度"""
        if node is None or depth > max_depth:
            return
        #print("绘制四叉树")
        
        # 绘制当前节点框
        rect_item = QGraphicsRectItem(node.bbox)
        color = QColor(255, 100, 100, 100)  # 半透明红色
        pen = QPen(color, 1.0)
        rect_item.setPen(pen)
        rect_item.setZValue(-10)
        self.scene.addItem(rect_item)
        
        # 递归绘制子节点
        if node.children:
            for child in node.children:
                self._draw_quadtree_simple(child, max_depth, depth + 1)

    def wheelEvent(self, event):
        '''这个可以缩放'''
        #print(f"Scene Rect: {self.sceneRect()}")  # 场景范围
        #print(f"Viewport Size: {self.viewport().size()}")  # 视口大小
        #print(f"Current Scale: {self.scale_factor}")  # 当前缩放
        
        # 计算实际可移动范围
        #scene_rect = self.sceneRect()
        #view_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        
        #print(f"实际可视区域: {view_rect}")
        self.fit_to_nodes(self.simulation.state.pos)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        zoom_in = event.angleDelta().y() > 0
        factor = 1.15 if zoom_in else 1 / 1.15
        new_scale = self.scale_factor * factor
        if 0.1 < new_scale < 10:
            self.scale(factor, factor)
            self.scale_factor = new_scale
        event.accept()  # 阻止事件向上传递

    def fit_to_nodes(self, nodes_pos):
        """根据节点位置设置场景范围"""
        if len(nodes_pos) == 0:
            return
            
        # 计算边界
        min_x, min_y = np.min(nodes_pos, axis=0)
        max_x, max_y = np.max(nodes_pos, axis=0)
        
        # 计算宽度和高度
        width = max_x - min_x
        height = max_y - min_y
        
        # 添加边距（20%的边距）
        margin_x = width * 0.2
        margin_y = height * 0.2
        
        scene_rect = QRectF(min_x - margin_x, min_y - margin_y, 
                        width + 2 * margin_x, height + 2 * margin_y)
        
        self.scene.setSceneRect(scene_rect)
        print(f"根据节点设置场景范围: {scene_rect}")

    def set_show_quadtree(self,state):
        
        if state == Qt.CheckState.Checked:
            self.show_quadtree = True
        else:
            self.show_quadtree = False
            print(f"改变状态为{state}")

    def show_coordinate_sys(self,state):
        '''显示坐标轴'''
        
        if state == Qt.CheckState.Checked:
            print("添加坐标轴")
            pen = QPen(QColor(0, 0, 255))  # 蓝色
            pen.setWidth(2)
            x_axis = QGraphicsLineItem(0, 0, 500, 0)
            x_axis.setPen(pen)
            self.scene.addItem(x_axis)
            pen = QPen(QColor(255, 0, 0))  # 红色
            pen.setWidth(2)
            y_axis = QGraphicsLineItem(0, 0, 0, 500)
            y_axis.setPen(pen)
            self.scene.addItem(y_axis)
            self.axis_items.append(x_axis)
            self.axis_items.append(y_axis)
        else:
            print("删除坐标轴")
            for item in self.axis_items:
                self.scene.removeItem(item)
            self.axis_items=[]
    
    def set_manybodyfstrength(self,num):
        self.many.strength=num
        self.simulation.restart()

    def set_centerfstrength(self,num):
        self.center.strength=num*0.001
        self.simulation.restart()

    def set_linkfstrength(self,num):
        self.link.k=num*0.01
        self.simulation.restart()

    def set_linklength(self,num):
        self.link.distance=num
        self.simulation.restart()

    def set_collision_ridius(self,num):
        ones_arr = np.ones_like(self.simulation.state.radii)
        self.simulation.state.radii=ones_arr*num
        self.simulation.restart()


def compute_node_radii(G: nx.Graph, r_min=4, r_max=10):
    """根据度数向量化计算节点半径，线性映射到 [r_min, r_max]"""
    degrees = np.array([d for _, d in G.degree()], dtype=np.float32)
    if len(degrees) == 0:
        return np.array([], dtype=np.float32)

    d_min, d_max = degrees.min(), degrees.max()

    if d_min == d_max:  # 全部度相同
        radii = np.full_like(degrees, (r_min + r_max) / 2)
    else:
        radii = r_min + (degrees - d_min) / (d_max - d_min) * (r_max - r_min)
    return radii

# ------------------------------
# Demo main
# ------------------------------

#分布生成随机图
def generate_random_connections(mean: float) -> int:
    """生成符合泊松分布的连接数量（用指数分布近似）"""
    # JS 中的：-Math.log(1 - Math.random()) * mean
    return round(-math.log(1 - random.random()) * mean)

def generate_random_graph(node_number=200, mean=1)-> nx.Graph:
    """根据 JS 逻辑生成随机图"""
    G = nx.Graph()

    # 添加节点
    for i in range(1, node_number + 1):
        G.add_node(i)

    # 随机生成边
    for i in range(1, node_number + 1):
        num_connections = generate_random_connections(mean)
        for _ in range(num_connections):
            target = random.randint(1, node_number)
            if target != i:
                G.add_edge(i, target)

    return G

def generate_graph()->nx.graph:
    '''产生无向图'''
    
    from core.database.connection import get_connection
    from config import DATABASE
    conn=get_connection(DATABASE,True)
    cursor = conn.cursor()

    q1="""
SELECT 
actress_id,
(SELECT cn FROM actress_name WHERE actress_id=actress.actress_id)AS name
FROM
actress
"""
    cursor.execute(q1)
    actresses = cursor.fetchall()
    q2="""
SELECT 
work_id,
serial_number
FROM
work
"""
    cursor.execute(q2)
    works = cursor.fetchall()

    cursor.execute("SELECT work_id, actress_id FROM work_actress_relation")
    relations = cursor.fetchall()

    cursor.close()
    conn.close()

    #添加图
    G=nx.Graph()
            # 添加女优节点
    for aid, name in actresses:
        G.add_node(
            f"a{aid}",  # 避免与作品 id 冲突
            label=name,
            title=f"女优: {name}",
            group="actress",
            color="#ff99cc"
        )
                # 添加作品节点
    for wid, title in works:
        G.add_node(
            f"w{wid}",
            label=title,
            title=f"作品: {title}",
            group="work",
            color="#99ccff",
            shape="box"
        )

    # 添加边（参演关系）
    for wid, aid in relations:
        G.add_edge(f"a{aid}", f"w{wid}")
    return G


def generate_similar_graph()->nx.Graph:
    '''计算两两作品间的相似度，产生图，相似度高于阈值的连接'''

    from scipy.sparse import lil_matrix
    from sklearn.metrics.pairwise import cosine_similarity

    #从数据库获取作品及其标签
    from core.database.connection import get_connection
    from core.database.db_utils import attach_private_db,detach_private_db
    from config import DATABASE
    conn=get_connection(DATABASE,True)
    cursor = conn.cursor()
    attach_private_db(cursor)

    q1="""
SELECT 
wtr.work_id,
wtr.tag_id
FROM
work_tag_relation wtr
JOIN priv.favorite_work fw ON fw.work_id=wtr.work_id
"""
    cursor.execute(q1)
    work_tags_list= cursor.fetchall()

    q2="""
SELECT 
w.work_id,
w.serial_number
FROM
work w
JOIN priv.favorite_work fw ON fw.work_id=w.work_id
"""
    cursor.execute(q2)
    works = cursor.fetchall()

    detach_private_db(cursor)
    cursor.close()
    conn.close()

    # work_tags_list 示例：[(1,5),(1,2),(2,5),(2,3)]
    # 先把 work_id 和 tag_id 映射到连续索引
    work_ids = sorted({w for w, t in work_tags_list})
    tag_ids = sorted({t for w, t in work_tags_list})

    # 建立 id -> index 映射  ,由于work_id，tag_id不连续
    work_id_to_idx = {w:i for i,w in enumerate(work_ids)}
    tag_id_to_idx = {t:i for i,t in enumerate(tag_ids)}

    # 构建稀疏矩阵
    row_idx = []
    col_idx = []

    for work_id, tag_id in work_tags_list:
        row_idx.append(work_id_to_idx[work_id])
        col_idx.append(tag_id_to_idx[tag_id])

    data = np.ones(len(row_idx))  # 值全为1，表示作品拥有该标签
    from scipy.sparse import csr_matrix
    # csr_matrix(shape=(num_works, num_tags))
    X = csr_matrix((data, (row_idx, col_idx)), shape=(len(work_ids), len(tag_ids)))

    print("稀疏矩阵形状:", X.shape)
    print("非零元素数量:", X.nnz)

    # 计算相似度矩阵
    sim_matrix = cosine_similarity(X)  # 或者使用 jaccard_distance_matrix
    print("相似度矩阵形状:", sim_matrix.shape)

    # 根据阈值构建图的边
    threshold = 0.6
    edges = []

    num_works = len(work_ids)
    for i in range(num_works):
        for j in range(i + 1, num_works):  # 只取上三角，避免重复
            sim = sim_matrix[i, j]
            if sim > threshold:
                edges.append((work_ids[i], work_ids[j], sim))  # (作品A, 作品B, 相似度)


    G = nx.Graph()

    for wid, title in works:
        G.add_node(
            f"w{wid}",
            label=title,
            title=f"作品: {title}",
            group="work",
            color="#99ccff",
            shape="box"
        )

    for a, b, sim in edges:
        G.add_edge(f"w{a}", f"w{b}", weight=sim)

    components = list(nx.community.greedy_modularity_communities(G))
    print("发现子图数量:", len(components))

    # 遍历每个子图
    for comp in components:
        if len(comp) <= 2:
            continue  # 小于2个节点没必要处理

        subG = G.subgraph(comp)

        # 找出中心节点（你可以改用其他中心性算法）
        centrality = nx.degree_centrality(subG)
        center_node = max(centrality, key=centrality.get)

        # 删除所有不含中心节点的边
        for u, v in list(subG.edges()):
            if center_node not in (u, v):
                G.remove_edge(u, v)

        print(f"子图 {comp} → 中心节点 {center_node}，保留星形结构")

    return G

def main():
    app = QApplication(sys.argv)
    w = QWidget()
    view = ForceView(generate_similar_graph())#
    # controls
    btn_restart = QPushButton("Restart")
    btn_restart.clicked.connect(view.simulation.restart)
    btn_pause = QPushButton("Pause")
    btn_pause.clicked.connect(view.simulation.pause)
    btn_resume = QPushButton("Resume")
    btn_resume.clicked.connect(view.simulation.resume)
    show_quadtree=QCheckBox("显示四叉树")
    show_quadtree.setChecked(False)
    show_quadtree.checkStateChanged.connect(view.set_show_quadtree)

    show_coordinate_sys=QCheckBox("显示坐标轴")
    show_coordinate_sys.setChecked(False)
    show_coordinate_sys.checkStateChanged.connect(view.show_coordinate_sys)

    label1=QLabel()

    manybodyfstrength=QSlider(Qt.Horizontal)
    manybodyfstrength.setMinimum(10)
    manybodyfstrength.setMaximum(10000)
    manybodyfstrength.setValue(50)
    manybodyfstrength.valueChanged.connect(view.set_manybodyfstrength)

    centerfstrength=QSlider(Qt.Horizontal)
    centerfstrength.setMinimum(1)
    centerfstrength.setMaximum(200)
    centerfstrength.setValue(1)
    centerfstrength.valueChanged.connect(view.set_centerfstrength)

    linkfstrength=QSlider(Qt.Horizontal)
    linkfstrength.setMinimum(1)
    linkfstrength.setMaximum(200)
    linkfstrength.setValue(20)
    linkfstrength.valueChanged.connect(view.set_linkfstrength)

    linklength=QSlider(Qt.Horizontal)
    linklength.setMinimum(10)
    linklength.setMaximum(80)
    linklength.setValue(40)
    linklength.valueChanged.connect(view.set_linklength)

    collision_ridius=QSlider(Qt.Horizontal)
    collision_ridius.setMinimum(10)
    collision_ridius.setMaximum(80)
    collision_ridius.setValue(20)
    collision_ridius.valueChanged.connect(view.set_collision_ridius)


    container = QWidget()
    mainlayout = QHBoxLayout(container)
    mainlayout.addWidget(view)
    vlayout=QFormLayout()
    vlayout.addRow("计算单帧消耗",label1)

    vlayout.addRow("斥力强度",manybodyfstrength)
    vlayout.addRow("中心力强度",centerfstrength)
    vlayout.addRow("连接力强度",linkfstrength)
    vlayout.addRow("连接距离",linklength)
    vlayout.addRow("碰撞半径",collision_ridius)

    vlayout.addRow("",btn_restart)
    vlayout.addRow("",btn_pause)
    vlayout.addRow("",btn_resume)
    vlayout.addRow("",show_quadtree)
    vlayout.addRow("",show_coordinate_sys)
    mainlayout.addLayout(vlayout)
    view.c_time.connect(lambda c:label1.setText(f"{c:.2f}毫秒"))

    w.setLayout(mainlayout)
    #w.setCentralWidget(container)
    w.resize(1000, 700)
    w.show()
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
    #generate_similar_graph()