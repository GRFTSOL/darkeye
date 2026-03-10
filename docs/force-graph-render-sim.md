# 力导向图：渲染与模拟系统

本文档描述当前力导向图（Force-Directed Graph）的**渲染**与**模拟**系统做了什么，以及移植到 C++、去除多进程时的架构与图数据传递格式建议。

---

## 一、现有系统概览

系统分为三块：

| 模块 | 文件 | 职责 |
|------|------|------|
| 进程入口 | `simulation_process_main.py` | 启动并持有**全局唯一**的模拟子进程，对外暴露 Pipe 的 parent 端 |
| 模拟核心 | `simulation_worker.py` | 子进程内：接收命令、维护多视图的物理状态、每帧 tick 力导向、写回共享内存 |
| 视图与渲染 | `ForceGraphView.py` | 主进程：图加载、IPC 客户端、共享内存创建、Qt 场景/节点层绘制、交互 |

数据流简要：

- **图数据**：主进程用 `networkx.Graph`，加载时转为 `RenderState`（节点顺序、边索引、邻居表等），并创建 **pos 的共享内存**。
- **IPC**：主进程通过 `Pipe.send()` 发送命令（如 `load_graph`、`pause`、`set_dragging`）；子进程通过同一 Pipe 回发事件（`system_ready`、`graph_ready`、`tick`）。
- **位置同步**：子进程直接写入 **共享内存** 中的 `pos (N×2 float32)`；主进程的 `NodeLayer` 直接读同一块内存绘制，无需再拷贝。

---

## 二、各模块在做什么

### 2.1 `simulation_process_main.py`：进程入口

- **作用**：提供“全局单例”的模拟进程。
- **行为**：
  - `get_global_simulation_process()` 首次调用时：`Pipe()` 建父子连接，`Process(target=_worker_entry, args=(child_conn,))` 启动子进程，子进程执行 `simulation_process_main(conn)`。
  - 之后调用返回已有的 `parent_conn`；若子进程已死则重新创建进程与 Pipe。
- **不负责**：具体模拟逻辑、消息协议细节，只负责“有一个子进程 + 一根 Pipe”。

---

### 2.2 `simulation_worker.py`：模拟核心（子进程）

#### 2.2.1 数据结构

- **PhysicsState**
  - `pos`: `(N, 2) float32`，**与主进程共享内存**，力导向结果写在这里。
  - `vel`: `(N, 2) float32`，速度，进程内私有。
  - `mass`: `(N,) float32`，默认 1。
  - `dragging`: `(N,) bool`，拖拽固定节点。
  - `edges`: `(E, 2) int32`，边表（节点索引对），由 `load_graph` 等命令设置。

- **Force 体系**
  - `CenterForce`：把节点拉向中心 `(cx, cy)`，强度可调。
  - `LinkForce`：弹簧力，目标长度 `distance`，刚度 `k`。
  - `ManyBodyForce`：斥力。小图用 block 版、较大图用 Numba 并行版；可选 Barnes-Hut（当前大图仍用暴力）。

- **Simulation**
  - 持有 `PhysicsState` 和多个 `Force`；每步 `tick()`：依次 `force.apply(alpha)` 更新速度，再 `integrate()` 用速度更新 `pos`（考虑 `velocity_decay`、`max_disp`、`dragging`）。
  - 带冷却：`alpha` 随 tick 衰减，速度足够小且 alpha 足够小时置 `_active = False`。

#### 2.2.2 进程主循环

- **收命令**：`conn.poll()` 非空则 `conn.recv()`，按 `cmd` 和 `view_id` 分发：
  - `load_graph` / `little_load_graph`：创建/复用 `SimContext`，用 `shm_name` 挂上共享内存得到 `pos`，用 `n_nodes`、`edges`、`params` 建 `PhysicsState` 和 `Simulation`（many/link/center 三力），然后 `sim.start()`，回发 `graph_ready` 或 `modify_graph`。
  - `close_view`：删对应 session，关 shm。
  - `pause` / `restart` / `resume`：调 sim 对应方法。
  - `set_*`：改某力的参数或 `dragging[index]`。
- **tick**：遍历所有 session，对 `sim.active()` 的按间隔（约 16ms）调用 `sim.tick()`，并通过 `conn.send({"event": "tick", "view_id", "elapsed", "active"})` 回传。
- **无活跃模拟时**：间隔发 `tick` 且 `active: False`，或 `sleep(0.001)` 避免空转。

总结：子进程只做“多视图的力导向模拟 + 写共享 pos”，不负责渲染和业务图数据（如 node 的 label、业务 ID）。

---

### 2.3 `ForceGraphView.py`：视图与渲染（主进程）

#### 2.3.1 通信与状态

- **ReceiverThread**：单独线程里对 `conn.poll(0.1)` 后 `recv()`，收到 dict 后通过 Qt 信号 `message_received` 转到主线程。
- **SimulationClient**（单例）：维护 `view_id -> callback`；`send(msg)` 若后端未就绪则缓冲，收到 `system_ready` 后重放缓冲并标记就绪；收到带 `view_id` 的消息则分发给对应 callback。
- **ForceGraphController**（每个视图一个）：
  - 持有 `RenderState`（见下），通过 `SimulationClient` 注册、发命令。
  - `load_graph(G)`：计算初始 pos、创建 **pos 的 SharedMemory**、建 `RenderState`、算 `node_radii`、`graph_loaded.emit(state, node_radii)`，然后 `client.send({cmd: "load_graph"|"little_load_graph", view_id, shm_name, n_nodes, edges, params})`。
  - 增量/改图用 `little_load_graph`，拓扑变更时先 `_sync_pos_to_graph()` 再 `load_graph(G, modify=True)`。
  - 拖拽：通过 `set_dragging(index, True/False)` 发到子进程；拖拽时直接写 `state.pos[selected_index]`（即共享内存），子进程读同一块。

#### 2.3.2 图与渲染状态

- **RenderState**
  - `G`：原始 `nx.Graph`（用于业务、label、同步回写 pos）。
  - `pos`：`(N, 2) float32`，与子进程**共享内存**的视图。
  - `nodes`：节点顺序列表；`node_index`：节点 ID → 索引。
  - `edges`：`(E, 2) int32` 边索引；`neighbors`：每节点邻居索引列表（用于悬停高亮）。
  - `shm`、`n_nodes`。

- **NodeLayer**（QGraphicsObject）
  - 只负责“怎么画、怎么动、怎么响应鼠标”：从 `state.pos` 读坐标，不推导图结构。
  - **绘制**：根据视口算 `visible_indices` / `visible_edges`，先画边（普通/高亮/暗淡），再按分组画节点圆、文字、悬停时的图片。
  - **交互**：命中检测（到各可见节点距离）、press/drag/release 时写 `state.pos` 并发 `set_dragging`，发出 `nodePressed` 等信号给 ForceView。
  - **LOD**：文字根据缩放显隐/透明度；半径、线宽可调系数。

- **ForceView**（QGraphicsView）
  - 持有 Controller、Scene、NodeLayer；`controller.graph_loaded` → `_on_graph_loaded`（创建或 reset NodeLayer）；`controller.frame_ready` → `_on_frame_ready`（更新可见性、请求渲染）。
  - 固定 16ms 的 `_render_timer` 驱动 `NodeLayer.update()`；模拟不活跃且无拖拽/悬停时，用 `_idle_timer` 停掉渲染定时器以省电。

整体上：**主进程 = 图数据 + 共享内存创建 + 渲染 + 交互；子进程 = 纯物理模拟 + 写共享 pos**。

---

## 三、当前 Python→子进程的“图”传递方式

- **节点位置**：主进程创建 `SharedMemory(create=True, size=n_nodes*2*sizeof(float32))`，把初始 pos 写入，把 `shm.name` 和 `n_nodes` 发给子进程；子进程 `SharedMemory(name=shm_name)` 后 `np.ndarray(..., buffer=shm.buf)` 得到同一块内存。之后子进程只写 `pos`，主进程只读。
- **拓扑**：通过 Pipe 传字典，例如：
  - `edges`：list of `[u_idx, v_idx]`（节点在 `nodes` 列表中的下标），子进程转成 `(E, 2) int32`。
  - `n_nodes`：整数。
  - `params`：`many_strength`、`link_strength`、`link_distance`、`center_strength` 等。
- 不传：节点 ID、label、业务属性；子进程只认“索引 0..N-1”和边表。

---

## 四、移植到 C++ 与去除多进程



### 4.2 去除多进程后的架构选项



- **方案 B：模拟与渲染都在 C++（Qt C++ 或 QML）**
  - Python 只做业务：从 DB 建 nx 图、过滤、拼“图数据”，通过**一次调用**把图传给 C++ 插件/子库；C++ 内部既做力导向又做 OpenGL/Scene Graph 渲染。
  - **C++ 端不用、也不依赖 nx**：C++ 只接收“扁平的数值数据”（节点数、边表索引、初始坐标），见下文「方案 B 下的 Python→C++ 传递」。

---

### 4.3 方案 B 下：Python（nx）怎样把图传给 C++（C++ 不用 nx）

思路：**在 Python 里把 nx 图“拍扁”成 C++ 能用的几块内存，再通过 pybind11 一次性传过去**。C++ 侧只有数组和数字，没有任何图库依赖。

1. **在 Python 里从 nx 得到与当前一致的结构**
   - 节点顺序：`nodes = list(G.nodes())`，长度 `n_nodes`。
   - 节点 ID→索引：`node_index = {n: i for i, n in enumerate(nodes)}`。
   - 边表（索引对）：`edges = np.array([(node_index[u], node_index[v]) for u, v in G.edges()], dtype=np.int32)`，形状 `(E, 2)`。
   - 初始坐标：和现在一样按 `nodes` 顺序算一维 pos，例如 `pos = np.zeros((n_nodes, 2), dtype=np.float32)`，然后按业务/随机/布局填好。

2. **通过 pybind11 暴露给 C++ 的接口（示例）**
   - 一次调用传全图；拓扑 + 坐标必传，**每个节点对应的 label、业务 id、颜色**与 `nodes` 顺序一致（索引 0..N-1），一并传入，例如：
     ```cpp
     // C++ 侧：只认 n_nodes、边索引、pos、以及按节点顺序的 label/id/color，不认 nx
     void set_graph(uint32_t n_nodes,
                    py::array_t<int32_t> edges,      // (E,2) 边索引对
                    py::array_t<float> pos,          // (N,2) 坐标
                    py::list labels,                 // 长度 N，节点显示名
                    py::object node_ids,              // 长度 N，业务 ID（可 list 或 array，类型由业务定）
                    py::array_t<uint8_t> colors);   // (N,4) RGBA 或 (N,3) RGB，每节点一色
     ```
   - Python 调用方（伪代码）：
     ```python
     nodes = list(G.nodes())
     n_nodes = len(nodes)
     node_index = {n: i for i, n in enumerate(nodes)}
     edges = np.array([(node_index[u], node_index[v]) for u, v in G.edges()], dtype=np.int32)
     pos = np.zeros((n_nodes, 2), dtype=np.float32)
     # 按 nodes 顺序：每个节点一个 label、一个 id、一个颜色
     labels = [G.nodes[n].get("label", str(n)) for n in nodes]
     node_ids = [n for n in nodes]   # 或 G.nodes[n]["id"] 等业务 ID
     colors = np.zeros((n_nodes, 4), dtype=np.uint8)  # RGBA
     for i, n in enumerate(nodes):
         c = G.nodes[n].get("color", "#5C5C5C")
         colors[i] = hex_to_rgba(c)   # 自行实现 "#RRGGBB" -> (r,g,b,a)
     # ... 填充 pos（随机或从 G.nodes[n]['pos'] 等）...
     cpp_graph_plugin.set_graph(n_nodes, edges, pos, labels, node_ids, colors)
     ```
   - C++ 在 `set_graph` 里：根据 `n_nodes`、`edges`、`pos` 建内部图结构；**按索引 i 存 label[i]、node_id[i]、color[i]**，渲染时画文字用 label、画圆用 color，点击时把 index 或 node_id 回传 Python。**完全不需要 nx**。

3. **每节点属性约定（label / 业务 id / 颜色）**
   - 与 `nodes` 顺序严格一致，索引 i 对应第 i 个节点：
     - **label**：`list[str]` 或 `list[bytes]`，长度 N，用于节点旁显示的文字。
     - **业务 id**：与 Python 业务一致即可（如字符串 ID、整数 ID），类型可用 `py::list` 或 numpy 一维数组，长度 N；点击回调时 C++ 把该 index 或对应的 id 回传 Python，便于做路由/编辑等。
     - **颜色**：`(N, 4) uint8` RGBA 或 `(N, 3)` RGB，每行一个节点；C++ 渲染节点圆、高亮等用此颜色。

4. **小结（方案 B）**
   - Python：用 nx 做图构建、过滤、业务；最后一步是 **nx → nodes + node_index + edges + pos + labels + node_ids + colors**（均按同一节点顺序）。
   - 传过去的是：`n_nodes`、`edges`（E×2 int32）、`pos`（N×2 float32），以及 **每节点一个 label、一个业务 id、一个颜色**（格式见上）。
   - C++：只实现“接收这些数组 + 力导向 + 渲染”；用索引 0..N-1 对应 label/id/color，不依赖任何 Python 图库。

---

## 五、图数据从 Python 到 C++ 的传输格式

目标：在去掉多进程的前提下，把“图”从 Python（nx）交给 C++ 力导向引擎：节点数、边表、初始 pos，以及可选参数。**方案 A 和方案 B 都使用本节同一套数据格式**；方案 B 时由 Python 在传图前把 nx 转成这些数组再一次性传入 C++。

### 5.1 最小必要数据（与当前子进程一致）

- `n_nodes`: uint32
- `edges`: 长度为 2*E 的 int32 数组，每两条为 (src_index, dst_index)
- `pos`: 长度为 n_nodes*2 的 float32，布局 [x0,y0, x1,y1, ...]

这样 C++ 端与当前 PhysicsState 一致，无需节点 ID 或 label。

### 5.2 每节点属性：label、业务 id、颜色（方案 B 渲染必传）

若 C++ 负责绘制节点文字与颜色（方案 B），需再传与 **nodes 顺序一致** 的三种数据，索引 i 对应同一节点：

| 属性 | 类型 | 长度/形状 | 说明 |
|------|------|-----------|------|
| **label** | `list[str]` 或可转为 C++ 字符串的序列 | N | 节点显示名，渲染时绘在节点旁 |
| **业务 id** | `list` 或一维数组（类型由业务定，如 str/int） | N | 点击等回调时回传 Python，用于路由、编辑等 |
| **颜色** | `(N, 4) uint8` RGBA 或 `(N, 3)` RGB | N×4 或 N×3 | 每节点一色，C++ 画圆/高亮用 |

约定：**三者与 pos 的节点顺序一致**，即 `label[i]`、`node_id[i]`、`color[i]` 与 `pos` 第 i 个节点对应。Python 侧从 nx 按 `nodes = list(G.nodes())` 顺序填好再传即可。



### 5.4 增量/修改（modify_graph）

- 当前 `little_load_graph` 是“全量替换”边表 + 同一块 pos 续用（仅主进程侧保留原 shm，子进程侧重新 from_compact）。
- 在 C++ 单进程方案中可改为：
  - **全量**：`set_graph(n_nodes, edges, pos)` 覆盖。
  - **增量**（可选）：`add_node(index)`, `remove_node(index)`, `add_edge(u,v)`, `remove_edge(u,v)`，并在 C++ 内维护节点索引映射或标记“脏”区域；实现复杂，可二期再做，首版用全量替换即可与现有行为一致。

---

## 六、小结

| 项目 | 当前实现 | 建议（移植 C++ 且去多进程） |
|------|----------|------------------------------|
| 进程模型 | 主进程(UI+图+渲染) + 子进程(模拟) | 单进程，C++ 模拟库 + Python UI/渲染 |
| 图/拓扑 | Pipe 传 dict（edges list + n_nodes） | NumPy 数组经 pybind11 传（或二进制块） |
| 位置 pos | 共享内存（主建、子写、主读） | 单块内存，C++ 写、Python 读（或反之一致约定） |
| 渲染 | Python NodeLayer 读 state.pos | 不变，仍读同一块 pos |
| 交互 | 主进程写 pos、发 set_dragging | 主进程写 pos（或调 C++ set_dragging），同一块 pos 给 C++ tick |

这样可以在保留现有渲染与交互的前提下，把力导向核心迁到 C++，并去掉多进程与共享内存，图数据用“NumPy 数组（或简单二进制）”从 Python 传到 C++ 即可。



高性能绘文本方案多通道距离场 (MSDF - Multi-channel SDF)
矢量路径 (Path)