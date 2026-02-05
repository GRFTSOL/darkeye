# 模拟核心，会开一个新的进程，从程序运行开始
# 现在这个性能已经足够强了，不需要再优化了，2000个节点60帧无压力，还可以开多核，并行计算，后面还可以GPU

import numpy as np
import networkx as nx
import math, time, numba
from typing import Dict
from multiprocessing import Process, Pipe, shared_memory
from typing import Optional
from numpy.typing import NDArray
import logging
logger = logging.getLogger("simulation")

class PhysicsState:
    """统一的物理状态存储，用于各个 Force 共享访问,其中pos是与renderstate共享内存"""
    """
    - edges : (E, 2) int32 通过命令增量维护
    - pos : (N, 2) float32(共享内存)
    - vel : (N, 2) float32
    - mass : (N,) float32
    - dragging : (N,) bool (通过管道传输拖动状态)
    """
    edges: NDArray[np.int32]
    pos: NDArray[np.float32]
    vel: NDArray[np.float32]
    mass: NDArray[np.float32]
    dragging: NDArray[np.bool_]
    def __init__(self):
        # 初始化时不分配内存，等待 from_compact 方法分配
        pass

    @classmethod
    def from_compact(cls, n_nodes: int, edges: np.ndarray, pos_array: np.ndarray) -> "PhysicsState":
        obj = cls.__new__(cls)
        obj.edges = np.array(edges, dtype=np.int32)# type: ignore[arg-type]
        obj.pos = pos_array# type: ignore[arg-type]
        obj.vel = np.zeros((n_nodes, 2), dtype=np.float32)# type: ignore[arg-type]
        obj.mass = np.ones(n_nodes, dtype=np.float32)# type: ignore[arg-type]
        obj.dragging = np.zeros(n_nodes, dtype=bool)# type: ignore[arg-type]
        return obj

class Force:
    def initialize(self,state:PhysicsState): pass
    def apply(self, alpha): pass

class CenterForce(Force):
    '''O(n)'''
    def __init__(self, cx=0.0, cy=0.0, strength=0.1):
        self.cx = cx
        self.cy = cy
        self.strength = strength

    def initialize(self,state):
        self.state = state  # 共享 PhysicsState

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
        if len(self.state.edges) == 0:
            return

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



@numba.njit(fastmath=True, nogil=True, cache=True, parallel=True)
def manybody_parallel_kernel(pos, mass, vel, strength, alpha, cutoff2):
    '''这个多核的并行真的是太暴力的'''
    N = pos.shape[0]
    
    # 强制外层循环并行化
    for i in numba.prange(N):
        # 将频繁读取的变量放入寄存器
        xi = pos[i, 0]
        yi = pos[i, 1]
        mi = mass[i]
        
        # 局部变量累加，避免频繁写回内存导致的 Cache Miss
        fx_sum = 0.0
        fy_sum = 0.0
        
        for j in range(N):
            if i == j:
                continue
            
            dx = xi - pos[j, 0]
            dy = yi - pos[j, 1]
            dist2 = dx * dx + dy * dy + 1e-6
            
            if dist2 < cutoff2:
                # 只有计算 i 受到的力
                s = strength * mi * mass[j] / dist2
                invd = 1.0 / math.sqrt(dist2)
                
                fx_sum += s * dx * invd * alpha
                fy_sum += s * dy * invd * alpha
        
        # 最终一次性更新速度数组
        vel[i, 0] += fx_sum
        vel[i, 1] += fy_sum

def _warmup_manybody_parallel():
    p = np.zeros((10, 2), dtype=np.float32)
    m = np.ones(10, dtype=np.float32)
    v = np.zeros_like(p)
    manybody_parallel_kernel(p, m, v, 1.0, 1.0, 1e6)

@numba.njit(fastmath=True,nogil=True,cache=True)
def manybody_block_kernel(pos, mass, vel, strength, alpha, cutoff2, block):
    N = pos.shape[0]
    for i0 in range(0, N, block):
        i1 = i0 + block
        if i1 > N:
            i1 = N
        for j0 in range(0, N, block):
            j1 = j0 + block
            if j1 > N:
                j1 = N
            for i in range(i0, i1):
                xi = pos[i, 0]
                yi = pos[i, 1]
                mi = mass[i]
                for j in range(j0, j1):
                    if i0 == j0 and i >= j:
                        continue
                    dx = xi - pos[j, 0]
                    dy = yi - pos[j, 1]
                    dist2 = dx * dx + dy * dy + 1e-6
                    if dist2 >= cutoff2:
                        continue
                    mj = mass[j]
                    s = strength * mi * mj / dist2
                    invd = 1.0 / math.sqrt(dist2)
                    fx = s * dx * invd * alpha
                    fy = s * dy * invd * alpha
                    vel[i, 0] += fx
                    vel[i, 1] += fy
                    vel[j, 0] -= fx
                    vel[j, 1] -= fy
                    vel[j, 0] -= fx
                    vel[j, 1] -= fy

def _warmup_manybody_block_kernel():
    pos = np.zeros((4, 2), dtype=np.float32)
    mass = np.ones(4, dtype=np.float32)
    vel = np.zeros_like(pos)
    strength = 1.0
    alpha = 1.0
    cutoff2 = 1e6
    block = 2
    manybody_block_kernel(pos, mass, vel, strength, alpha, cutoff2, block)

class ManyBodyForce(Force):
    """Repulsive force. Modes:
       - mode='brute' : O(N^2) pairwise repulsion
       - mode='barnes' : Barnes-Hut approximate via QuadTree
       这个是最消耗时间的，需要大量的优化
       现在这个计算已经不是瓶颈了，还可以用GPU优化，还可以更快
    """
    def __init__(self, strength=100.0, theta=0.6,mode="brute"):
        self.strength = strength
        self.theta = theta
        self.theta2=theta*theta
        self.mode=mode

    def initialize(self,state):
        self.state=state

    def apply(self, alpha: float):
        N = self.state.pos.shape[0]
        if N<2000:#目前不知道多少情况下是brute force更快，可能几万以下都是numba暴力计算更快
            manybody_block_kernel(
                self.state.pos,
                self.state.mass,
                self.state.vel,
                self.strength,
                alpha,
                40000.0,
                256
            )
        elif N<10000:#10000以下用并行算法
            manybody_parallel_kernel(
                self.state.pos,
                self.state.mass,
                self.state.vel,
                self.strength,
                alpha,
                40000.0
            )
        else:#四叉树加速
            pass

# ------------------------------
# Simulation controller
# ------------------------------
class SimContext:
    def __init__(self, sim, shm, forces):
        self.sim = sim
        self.shm = shm
        self.forces = forces
        self.last_tick_time = time.perf_counter()


class Simulation:
    '''模拟主类，负责模拟的运行,但是tick的速度是要另外手动调用的，数据在PhysicsState中'''
    def __init__(self, state: PhysicsState):

        self.forces: Dict[str, Force] = {}
        self.state = state

        # physics params
        self.alpha = 1.0
        self.alpha_decay = 0.01
        self.alpha_min = 0.001

        self.velocity_decay = 0.75  # similar to d3.velocityDecay
        self.dt = 0.1     #模拟时间间隔
        self.max_disp = 15.0#每次模拟最大位移距离

        # internal
        self._active = False
        self._first_started_time = None
        self._cooldown_delay = 150 #开始运行300次tick后正常冷却
        self._tick_count = 0#记录运行次数

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
        # cool down（首次运行的前 300 次 tick 不冷却）
        self._tick_count += 1

        if (
            self._first_started_time is not None
            and self._tick_count >= self._cooldown_delay
        ):
            self.alpha *= (1.0 - self.alpha_decay)
        avg_speed = total_speed / max(1, self.state.pos.shape[0])
        if avg_speed<0.01 and self.alpha < 0.01:
            # print("速度过慢，停止模拟")
            self._active = False

    def integrate(self):
        '''这个换一种积分方式，应该可以更加的柔和'''
        pos = self.state.pos      # (N, 2)
        vel = self.state.vel      # (N, 2)
        dragging = self.state.dragging  # (N,) bool 数组

        dt = self.dt
        decay = self.velocity_decay
        max_disp = self.max_disp

        vel *= decay

        moving_mask = ~dragging
        if np.any(moving_mask):
            v_moving = vel[moving_mask]
            speed = np.linalg.norm(v_moving, axis=1)

            too_far = speed * dt > max_disp
            if np.any(too_far):
                scale = (max_disp / (speed[too_far] * dt))[:, None]
                v_moving[too_far] *= scale

            disp = v_moving * dt
            pos[moving_mask] += disp

        total_speed = np.sum(np.abs(vel))
        return total_speed

    def start(self):
        self._active = True
        if self._first_started_time is None:
            self._first_started_time = time.perf_counter()

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


def simulation_process_main(conn):
    logger.info("Sim进程启动")

    _warmup_manybody_parallel()
    logger.info("预热numba完毕")
    
    # 发送系统就绪信号
    try:
        conn.send({"event": "system_ready"})
    except Exception:
        pass

    sessions = {} # {view_id: SimContext}

    running = True
    last_msg_time = time.perf_counter()
    tick_interval = 0.016
    
    # 用于空闲时发送tick false的计时
    last_idle_tick_time = time.perf_counter()

    while running:
        while conn.poll():#当管道中有消息时
            msg = conn.recv()
            if not isinstance(msg, dict):
                continue
            
            view_id = msg.get("view_id", "default") # 获取view_id，如果没有则默认为"default"
            cmd = msg.get("cmd")
            
            if cmd in ("stop", "shutdown"):
                running = False
                break
            
            elif cmd in ("init_graph", "reload_graph", "load_graph","little_load_graph"):
                # 如果该view_id已经存在，先清理旧的
                if view_id in sessions:
                    old_ctx = sessions[view_id]
                    if old_ctx.sim:
                        old_ctx.sim.stop()
                    if old_ctx.shm:
                        try:
                            old_ctx.shm.close()
                        except FileNotFoundError:
                            pass
                    del sessions[view_id]

                shm_name = msg.get("shm_name")
                n_nodes = int(msg.get("n_nodes", 0))
                edges_data = msg.get("edges")
                
                if shm_name is None or n_nodes <= 0 or edges_data is None:
                    continue

                edges_arr = np.array(edges_data, dtype=np.int32)
                try:
                    shm = shared_memory.SharedMemory(name=shm_name)
                except FileNotFoundError:
                    # 如果共享内存不存在，可能是已经关闭了，这里不做处理直接跳过
                    continue
                    
                shared_pos = np.ndarray((n_nodes, 2), dtype=np.float32, buffer=shm.buf)
                state = PhysicsState.from_compact(n_nodes, edges_arr, shared_pos)
                sim = Simulation(state)
                params = msg.get("params", {})
                many_strength = params.get("many_strength", 10.0)
                link_k = params.get("link_k", 0.3)
                link_distance = params.get("link_distance", 20.0)
                center_strength = params.get("center_strength", 0.5)

                many = ManyBodyForce(strength=many_strength, theta=0.6, mode="brute")
                sim.add_force("manybody", many)
                link = LinkForce(k=link_k, distance=link_distance)
                sim.add_force("link", link)
                center = CenterForce(0.0, 0.0, strength=center_strength)
                sim.add_force("center", center)
                
                forces = {
                    "manybody": many,
                    "link": link,
                    "center": center
                }
                
                ctx = SimContext(sim, shm, forces)
                sessions[view_id] = ctx


                sim.start()
                if cmd=="little_load_graph":
                    conn.send({"event": "modify_graph", "view_id": view_id})
                else:
                    conn.send({"event": "graph_ready", "view_id": view_id})
                last_msg_time = time.perf_counter()
            
            elif cmd == "close_view":
                if view_id in sessions:
                    ctx = sessions[view_id]
                    if ctx.sim:
                        ctx.sim.stop()
                    if ctx.shm:
                        try:
                            ctx.shm.close()
                        except FileNotFoundError:
                            pass
                    del sessions[view_id]

            # 针对特定view的操作
            elif view_id in sessions:
                ctx = sessions[view_id]
                sim = ctx.sim
                forces = ctx.forces
                
                if cmd == "restart" and sim is not None:
                    sim.restart()
                elif cmd == "pause" and sim is not None:
                    sim.pause()
                elif cmd == "resume" and sim is not None:
                    sim.resume()
                elif cmd == "set_many_strength" and "manybody" in forces:
                    forces["manybody"].strength = float(msg.get("value", forces["manybody"].strength))
                elif cmd == "set_center_strength" and "center" in forces:
                    forces["center"].strength = float(msg.get("value", forces["center"].strength))
                elif cmd == "set_link_strength" and "link" in forces:
                    forces["link"].k = float(msg.get("value", forces["link"].k))
                elif cmd == "set_link_distance" and "link" in forces:
                    forces["link"].distance = float(msg.get("value", forces["link"].distance))
                elif cmd == "set_dragging" and sim is not None:
                    index = msg.get("index", -1)
                    dragging = bool(msg.get("dragging", False))
                    if 0 <= index < sim.state.dragging.shape[0]:
                        sim.state.dragging[index] = dragging

        if not running:
            break

        now = time.perf_counter()
        any_active = False
        
        # 遍历所有session进行模拟
        for v_id, ctx in list(sessions.items()):
            sim = ctx.sim
            if sim is not None and sim.active():
                any_active = True
                modify = getattr(ctx, 'modify', False)
                
                start = None
                if sim._tick_count < 200 and not modify:
                    start = now
                    sim.tick()
                elif (now - ctx.last_tick_time) >= tick_interval:
                    start = now
                    sim.tick()
                    ctx.last_tick_time = now
                
                if start is not None:
                    elapsed = (time.perf_counter() - start) * 1000.0
                    conn.send({"event": "tick", "view_id": v_id, "elapsed": elapsed, "active": True})
                    last_msg_time = time.perf_counter()
            else:
                 # 如果不活跃，也需要偶尔发送tick状态，但频率低一些
                 # 这里我们只在全局idle检查中处理，或者针对每个view单独处理
                 pass

        if not any_active:
            if time.perf_counter() - last_idle_tick_time > 0.5:
                # 广播所有不活跃的view状态，或者简单地发一个全局idle?
                # 为了兼容性，最好还是针对每个view发送，或者前端处理
                # 这里简化处理：如果有view存在，就轮询发送
                for v_id, ctx in sessions.items():
                    if not ctx.sim.active():
                         conn.send({"event": "tick", "view_id": v_id, "active": False})
                last_idle_tick_time = time.perf_counter()
            time.sleep(0.001)

    # 清理所有session
    for ctx in sessions.values():
        if ctx.shm is not None:
            try:
                ctx.shm.close()
            except FileNotFoundError:
                pass
