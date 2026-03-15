# 图模块架构 (core/graph)

本文档描述关系图（ForceView）的整体架构，包括图数据生成、过滤系统、绘制系统与业务逻辑。

---

## 1. 整体数据流

```
数据库 (actress / work / work_actress_relation / work story)
        ↓
graph.py（图数据生成）
        ↓
GraphManager（单例，维护总图 G）
        ↓ graph_diff_signal（增量变更时）
GraphViewSession（过滤层，维护子图 sub_G）
        ↓ data_ready（全量） / diff_changed（增量）
ForceDirectedViewWidget（编排层）
        ↓ setGraph / apply_diff_runtime
ForceViewOpenGL（C++ 力导向绘制）
        ↓ 节点点击 / 悬停
Router 跳转、ImageOverlayWidget 封面/头像
```

---

## 2. 分层职责

### 2.1 图数据生成 (`graph.py`)

| 函数 | 说明 |
|------|------|
| `generate_graph()` | **主入口**。从数据库拉取女优、作品、参演关系，构造 NetworkX 无向图。节点：`a{actress_id}`（女优）、`w{work_id}`（作品）；边：参演关系。 |
| `generate_random_graph()` | 测试用，泊松分布随机图。 |
| `generate_similar_graph()` | 基于标签余弦相似度构建作品相似图（当前未接入 GraphManager 主流程）。 |

节点属性示例：`label`（名称/番号）、`group`（`"actress"` / `"work"`）。边可带 `type`（如 `"reference"` 表示 story 引用）。

### 2.2 总图管理 (`graph_manager.py`)

- **单例**：`GraphManager.instance()`，全局唯一。
- **职责**：
  - 后台线程初始化：调用 `generate_graph()` 得到基图，再通过 `_augment_with_story_relations()` 解析作品简介中的 `[[]]` 引用，添加 `type='reference'` 的边。
  - 维护总图 `G`，对外只读接口 `get_graph()`。
  - 监听 `work_data_changed`（GlobalSignalBus），对最近变更的作品做增量更新（节点/边的增删），并发出 **`graph_diff_signal`**，payload 为操作列表：`add_node` / `del_node` / `add_edge` / `remove_edge` 等。
- **信号**：`graph_diff_signal`、`initialization_finished`。

### 2.3 过滤系统 (`graph_filter.py`)

| 类 | 说明 |
|----|------|
| `GraphFilter` | 抽象基类，定义 `filter_node(graph, node_id)` 与 `filter_edge(graph, u, v)`。 |
| `EmptyFilter` | 全部过滤掉。 |
| `PassThroughFilter` | 全部保留（默认）。 |
| `EgoFilter` | 以指定节点为中心、给定半径内的 ego 子图，用于「片关系图」等场景。 |

扩展新视图时，可实现新的 `GraphFilter` 子类。

### 2.4 会话/业务层 (`graph_session.py`)

- **GraphViewSession**：每个视图一个实例，介于 GraphManager 与 UI 之间。
- **职责**：
  - 持有当前 `GraphFilter`，从 GraphManager 取总图 `G`，经 `apply_filter(G)` 得到子图 `sub_G`。
  - **全量加载**：`new_load()` → 计算 sub_G → 发出 `data_ready`，payload 含 `{"cmd": "load_graph", "graph": sub_G, "modify": False}`。
  - **增量更新**：订阅 `graph_diff_signal`，在 `_on_global_diff` 中按当前 filter 重算 sub_G，与旧 sub_G 做 diff，发出 **`diff_changed`**（仅会话内可见的增量操作列表）。
  - **EgoFilter 深度切换**：`fast_calc_diff(new_deepth)` 只计算半径变化带来的节点/边差异，避免整图重算，然后发出 `diff_changed`。
- **信号**：`data_ready`、`diff_changed`。

### 2.5 绘制与编排 (`ForceDirectedViewWidget.py`)

- **组合**：内嵌 `ForceViewOpenGL`（C++）、`GraphViewSession`、`ForceViewSettingsPanel`、`ImageOverlayWidget`、设置按钮等。
- **职责**：
  - 连接 Session 的 `data_ready` / `diff_changed` 到 `_on_graph_data_ready` / `_on_graph_diff_changed`。
  - 将 `nx.Graph` 转为 C++ 所需格式（节点数、边索引、位置、id、label、半径、颜色），调用 `view.setGraph(...)` 或 `view.apply_diff_runtime(ops)`。
  - 节点颜色：按 `group` / 节点 id 前缀（`a`/`w`）及是否为中心节点（EgoFilter）计算，中心节点可高亮（如金色）。
  - 节点点击：根据 id 前缀 `a`/`w` 调用 `Router.instance().push("single_actress", ...)` 或 `push("work", ...)`。
  - 图模式切换（`_switch_graph`）：`all`（PassThroughFilter）、`favorite`（EgoFilter，需传入 center_id）、`test`（随机图，不经过 GraphManager）。
  - 控制图片叠加层开关、悬停时通过 `nodeHoveredWithInfo` 驱动 `ImageOverlayWidget` 显示封面/头像。

### 2.6 OpenGL 视图 (C++ `ForceViewOpenGL`)

- 位置：`cpp_bindings/forced_direct_view/`，Python 通过 `PyForceView` 绑定调用。
- **职责**：力导向仿真、节点/边渲染、拖拽、缩放、平移；`setGraph` 全量设置图，`add_node_runtime` / `remove_node_runtime` / `add_edge_runtime` / `remove_edge_runtime` 及 `apply_diff_runtime` 支持增量更新。
- **信号**：如 `nodeLeftClicked(str)`、`nodeHoveredWithInfo(str, float, float, float, float, bool)`、`scaleChanged`、`fpsUpdated` 等，供上层连接。

### 2.7 设置面板 (`ForceViewSettingsPanel.py`)

- 纯 UI + 信号：物理参数（斥力、向心力、链接强度/距离）、显示参数（半径系数、连线宽度、文字阈值、箭头、图邻居深度）、模拟控制（暂停/恢复/重启、适应内容）、图类型单选、测试用加减点/边。
- 不直接依赖 GraphManager/Session，由父控件 `ForceDirectedViewWidget` 将信号连接到 View 与 Session。

### 2.8 辅助模块

| 文件 | 说明 |
|------|------|
| `text_parser.py` | `parse_wikilinks(text)` 解析 `[[target]]` / `[[target\|alias]]`，供 GraphManager 从 story 中抽取作品引用。 |
| `async_image_loader.py` | 异步加载女优头像、作品封面，带缓存；`ImageOverlayWidget` 根据节点 id（`a*`/`w*`）取图并显示。 |

---

## 3. 结构示意

```
┌─────────────────────────────────────────────────────────────────────┐
│ForceDirectedViewWidget                                              │
│   ├── ForceViewOpenGL (C++)            ← 力导向绘制、交互             │
│   ├── ForceViewSettingsPanel           ← 物理/显示/图模式/调试        │
│   ├── ImageOverlayWidget               ← 节点悬停显示封面/头像        │
│   └── GraphViewSession                 ← 过滤 + 子图 + 增量 diff     │
│       ├── GraphFilter (PassThrough / Ego / ...)                     │
│       └── GraphManager.instance()    ← 总图 G + graph_diff_signal    │
│           └── graph.generate_graph() + story [[]] 增强               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计点

- **单例总图**：所有数据以 GraphManager 的 `G` 为唯一真相源，视图仅通过 filter 得到子图，避免多份图数据不一致。
- **增量优先**：数据变更时发 diff 列表，Session 裁剪后转发，View 用 `apply_diff_runtime` 更新，减少全图重算与闪烁。
- **过滤可插拔**：通过替换 `GraphFilter` 实现不同视图（全图、ego、后续可扩展按标签/时间等）。
- **线程安全**：GraphManager 初始化在后台线程，信号连接通过 `_connect_signals_requested` 投递到主线程，避免跨线程创建 Qt 对象。

---

## 5. 与项目其他部分的关系

- **启动**：`main.py` 中调用 `GraphManager.instance().initialize()`，后台建图；首屏不一定打开关系图页，由 Router 懒加载 `ForceDirectPage`。
- **数据变更**：作品/女优的增删改通过 `GlobalSignalBus.work_data_changed` 通知，GraphManager 的 `update_recent_changes` 据此更新图并发 `graph_diff_signal`。
- **路由**：节点点击由 `ForceDirectedViewWidget._on_node_clicked` 调用 `Router.instance().push("work", ...)` / `push("single_actress", ...)`，与主导航一致。

---

## 6. 文件清单 (core/graph)

| 文件 | 职责概要 |
|------|----------|
| `graph.py` | 图数据生成（DB → NetworkX）。 |
| `graph_manager.py` | 总图单例、初始化、story 增强、增量更新与信号。 |
| `graph_filter.py` | 过滤器抽象及 Empty / PassThrough / Ego 实现。 |
| `graph_session.py` | 视图会话、过滤、全量/增量 diff 与信号。 |
| `ForceDirectedViewWidget.py` | 图页主控件，编排 Session / View / Panel / Overlay。 |
| `ForceViewSettingsPanel.py` | 力导向图设置面板 UI 与信号。 |
| `text_parser.py` | 解析 story 中 `[[]]` 引用。 |
| `async_image_loader.py` | 异步图片加载与缓存。 |

关系图页面入口：`ui/pages/ForceDirectPage.py`（懒加载并创建 `ForceDirectedViewWidget`）。  
C++ 力导向实现：`cpp_bindings/forced_direct_view/`（参见项目内该目录及 `docs/force-graph-render-sim.md` 等）。

---

## 7. 验收标准

以下验收标准与第 2～6 节架构与功能一一对应，用于确认图模块行为正确、可交付。

### 7.1 图数据生成 (graph.py)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| G1 | 主入口图生成 | `generate_graph()` 从数据库正确拉取女优、作品、参演关系，生成 NetworkX 无向图；节点 id 为 `a{actress_id}` / `w{work_id}`，边表示参演关系。 |
| G2 | 节点属性 | 节点具备 `label`（名称/番号）、`group`（`"actress"` / `"work"`）。 |
| G3 | 随机图 | `generate_random_graph()` 可生成泊松分布随机图，用于测试/调试。 |
| G4 | 相似图 | `generate_similar_graph()` 能基于标签余弦相似度构建作品相似图（可不接入主流程）。 |

### 7.2 总图管理 (graph_manager.py)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| M1 | 单例 | `GraphManager.instance()` 全局唯一，多次调用返回同一实例。 |
| M2 | 后台初始化 | 初始化在后台线程执行，调用 `generate_graph()` 并完成 story 增强，不阻塞主线程。 |
| M3 | Story 增强 | `_augment_with_story_relations()` 正确解析作品简介中的 `[[]]` 引用，添加 `type='reference'` 的边。 |
| M4 | 只读总图 | `get_graph()` 返回当前总图 G，外部无法直接修改。 |
| M5 | 增量更新 | 监听 `GlobalSignalBus.work_data_changed`，对最近变更的作品做节点/边增删，并发出 `graph_diff_signal`，payload 为 `add_node` / `del_node` / `add_edge` / `remove_edge` 等操作列表。 |
| M6 | 信号 | 初始化完成后发出 `initialization_finished`；增量变更时发出 `graph_diff_signal`。 |
| M7 | 线程安全 | 信号连接等需在主线程执行的操作通过 `_connect_signals_requested` 等机制投递到主线程，无跨线程创建 Qt 对象。 |

### 7.3 过滤系统 (graph_filter.py)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| F1 | 抽象接口 | `GraphFilter` 定义 `filter_node(graph, node_id)` 与 `filter_edge(graph, u, v)`，子类可实现具体逻辑。 |
| F2 | EmptyFilter | 过滤后子图为空（无节点、无边）。 |
| F3 | PassThroughFilter | 过滤后子图与输入图一致（全部保留）。 |
| F4 | EgoFilter | 以指定节点为中心、给定半径内的 ego 子图正确；半径变化时节点/边集合随之变化。 |

### 7.4 会话层 (graph_session.py)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| S1 | 过滤子图 | 从 GraphManager 取总图 G，经当前 `GraphFilter` 得到 sub_G，与架构一致。 |
| S2 | 全量加载 | `new_load()` 计算 sub_G 后发出 `data_ready`，payload 含 `{"cmd": "load_graph", "graph": sub_G, "modify": False}`。 |
| S3 | 增量转发 | 订阅 `graph_diff_signal`，按当前 filter 重算 sub_G 并做 diff，仅对会话内可见的变更发出 `diff_changed`。 |
| S4 | Ego 深度切换 | `fast_calc_diff(new_depth)` 仅根据半径变化计算节点/边差异并发出 `diff_changed`，不触发整图重算。 |

### 7.5 绘制与编排 (ForceDirectedViewWidget)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| V1 | 信号连接 | Session 的 `data_ready` / `diff_changed` 正确连接到 `_on_graph_data_ready` / `_on_graph_diff_changed`。 |
| V2 | 数据转换 | 将 `nx.Graph` 转为 C++ 所需格式（节点数、边索引、位置、id、label、半径、颜色），能正确调用 `view.setGraph(...)` 与 `view.apply_diff_runtime(ops)`。 |
| V3 | 节点颜色 | 按 `group`、节点 id 前缀（`a`/`w`）及是否为中心节点（EgoFilter）计算颜色，中心节点可高亮（如金色）。 |
| V4 | 节点点击 | 点击节点后根据 id 前缀调用 `Router.instance().push("single_actress", ...)` 或 `push("work", ...)`，与主导航一致。 |
| V5 | 图模式切换 | `_switch_graph` 支持 `all`（PassThroughFilter）、`favorite`（EgoFilter + center_id）、`test`（随机图，不经过 GraphManager），切换后视图与数据一致。 |
| V6 | 图片叠加层 | 可开关叠加层；节点悬停时 `nodeHoveredWithInfo` 驱动 `ImageOverlayWidget` 正确显示封面/头像。 |

### 7.6 OpenGL 视图 (C++ ForceViewOpenGL)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| O1 | 全量设置 | `setGraph(...)` 能一次性设置整图并正确渲染。 |
| O2 | 增量更新 | `add_node_runtime` / `remove_node_runtime` / `add_edge_runtime` / `remove_edge_runtime` 及 `apply_diff_runtime` 能正确增删节点/边，无错位或闪烁。 |
| O3 | 交互 | 力导向仿真、拖拽、缩放、平移正常；`nodeLeftClicked(str)`、`nodeHoveredWithInfo(...)`、`scaleChanged`、`fpsUpdated` 等信号能正确发出并供上层使用。 |

### 7.7 设置面板 (ForceViewSettingsPanel)

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| P1 | 物理参数 | 斥力、向心力、链接强度/距离等参数可调节，并通过信号影响 C++ 视图。 |
| P2 | 显示参数 | 半径系数、连线宽度、文字阈值、箭头、图邻居深度等可调节并生效。 |
| P3 | 模拟控制 | 暂停/恢复/重启、适应内容等操作可用且与 View 一致。 |
| P4 | 图类型与调试 | 图类型单选（如全图/片关系图/测试）与测试用加减点/边可用；不直接依赖 GraphManager/Session，由父控件连接。 |

### 7.8 辅助模块

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| A1 | text_parser | `parse_wikilinks(text)` 正确解析 `[[target]]` / `[[target\|alias]]`，供 GraphManager 从 story 抽取引用。 |
| A2 | async_image_loader | 能按节点 id（`a*`/`w*`）异步加载女优头像、作品封面，带缓存；ImageOverlayWidget 能据此显示图片。 |

### 7.9 集成与整体

| 编号 | 验收项 | 通过标准 |
|------|--------|----------|
| I1 | 启动 | `main.py` 中调用 `GraphManager.instance().initialize()`，后台建图；首次进入关系图页（ForceDirectPage 懒加载）时能正常显示或等待初始化完成。 |
| I2 | 数据变更 | 在别处增删改作品/女优后，通过 `work_data_changed` 驱动图增量更新，关系图视图能收到并应用 diff，无全图重载即可看到变更。 |
| I3 | 路由一致 | 从关系图节点进入作品页/女优页后，与主导航的「作品」「女优」页行为一致（同一路由与参数）。 |
| I4 | 单例与过滤 | 多窗口/多标签下总图仍为单例；各视图通过不同 Filter 得到不同 sub_G，互不串数据。 |

---

# InBox模块架构
