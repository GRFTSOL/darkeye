# force_direct_view C++ 架构修改意见

## 分析范围
- `cpp_bindings/forced_direct_view/include`
- `cpp_bindings/forced_direct_view/src`

## 总结
当前实现功能完整、性能路径也有初步优化（Barnes-Hut、可见性裁剪、MSDF 异步构建），但架构层面存在明显的“单类过重 + 状态耦合 + 并发边界不清”问题。  
短期可维护，长期在“运行时增删图、并发稳定性、功能扩展速度”上会越来越吃力。

## 关键架构问题

### 1. `ForceViewOpenGL` 职责过重（God Object）
代码证据：
- `include/ForceViewOpenGL.h` 已达 334 行，成员变量覆盖仿真、渲染、输入、文本、运行时 diff、配色、相机等多个子域。
- 相关实现分散在 6 个 `ForceViewOpenGL_*.cpp`，但本质仍是一个巨型对象共享全部状态。

影响：
- 任意需求改动都容易触发跨子系统回归。
- 线程问题、渲染问题、图数据问题耦合在一起，排障成本高。

建议：
- 将 `ForceViewOpenGL` 收敛为“UI 外壳 + 调度入口”，拆分为：
  - `GraphDataStore`（节点/边/ID 索引/邻接）
  - `SimulationController`（仿真线程、tick、force 参数）
  - `RenderPipeline`（可见性、几何构建、GL draw）
  - `TextAtlasService`（MSDF atlas 和布局缓存）
  - `InteractionController`（hover/drag/pan 状态机）

### 2. 数据模型耦合过深，存在多份并行状态
代码证据：
- `PhysicsState` 同时承载物理状态、渲染双缓冲、拖拽状态、图拓扑增删（`include/PhysicsState.h`）。
- `ForceViewOpenGL` 自身再维护 `m_ids/m_labels/m_showRadiiBase/m_nodeColors/m_neighbors/m_neighborMask...`（`include/ForceViewOpenGL.h`）。

影响：
- 一次节点删除需要在多份容器同步索引，`swap-last` 语义传播范围大，极易出现漏改。
- “谁是真实数据源”不清晰，后续难引入事务化更新与回滚。

建议：
- 统一单一真源：`GraphDataStore` 持有结构化 `NodeRecord` + `EdgeRecord`。
- `PhysicsState` 退回纯仿真缓存，不承担业务层拓扑增删。
- 所有显示层数组由 `GraphDataStore -> RenderSnapshot` 一次性投影生成。

### 3. 并发边界不一致，线程模型不统一
代码证据：
- `setGraph` 有 GUI 线程切换保护（`src/ForceViewOpenGL_Simulation.cpp:19`）。
- 但 `add_node_runtime/remove_node_runtime/apply_diff_runtime` 没有同样的线程入口收敛（`src/ForceViewOpenGL_Runtime.cpp`）。
- 仿真线程在锁内执行 `tick + publish`（`src/ForceViewOpenGL.cpp:186,202,203`），并与 UI 线程共享多类状态容器。

影响：
- 运行时改图在不同调用线程下行为不可预测。
- 未来做更细粒度并发（例如并行几何构建）时，锁竞争和竞态风险会迅速放大。

建议：
- 建立单写模型：所有图变更统一进入 `GraphMutationQueue`，只在 GUI 线程消费。
- 仿真线程只读快照 + 写入独立输出缓冲，不直接触碰 UI/业务容器。
- 把线程策略显式写入接口契约（API 文档 + 断言）。

### 4. API 契约与实现存在偏差
代码证据：
- `setGraph` 接收 `pos`，但实现直接随机初始化位置（`src/ForceViewOpenGL_Simulation.cpp:19-47`），没有使用传入布局。
- `Forces.h` 注释阈值与 `Forces.cpp` 实际阈值不一致（注释提到 `500/2000`，实现是 `1000` 分界）。

影响：
- 上层调用方难以预期行为，调参和复现困难。
- 注释和实现漂移会降低团队对代码的信任度。

建议：
- 明确 `setGraph` 契约：优先使用传入 `pos`，无效时再随机。
- 性能阈值统一为可配置常量，注释只描述策略，不写死过时数字。

### 5. Force 管理方式扩展性一般
代码证据：
- 通过字符串名 + `getForce("manybody")` + `dynamic_cast` 修改参数（`src/ForceViewOpenGL_Simulation.cpp:171-206`）。

影响：
- 重构/重命名不安全，编译期无法发现拼写问题。
- 新增 force 类型时易引入重复模板代码。

建议：
- 改为类型化句柄或参数总线：
  - `Simulation::setParameter(ForceType::ManyBody, ForceParam::Strength, value)`
  - 或保留对象句柄 `ManyBodyForce*` 由构建阶段缓存，不再每次字符串查找。

### 6. 渲染与仿真更新链路缺少“脏标记分层”
代码证据：
- `prepareFrame()` 每帧都会做可见性计算、边几何重建、节点实例重建（`src/ForceViewOpenGL_Geometry.cpp`）。
- 运行时增删点边后直接 `rebuildSimulation()`，即使是小改动也全量重建 force（`src/ForceViewOpenGL_Runtime.cpp`）。

影响：
- 大图场景下 CPU 开销和帧抖动明显。
- 增量更新能力弱，后续实时编辑体验上限低。

建议：
- 引入分层 dirty flag：
  - `TopologyDirty`（点边变化）
  - `StyleDirty`（颜色、半径、线宽）
  - `ViewDirty`（pan/zoom）
  - `HoverDirty`（高亮动画）
- 将“全量重建”降级为“按脏域更新”。

## 推荐目标架构

```text
ForceViewOpenGL (QOpenGLWidget, 薄壳)
  -> GraphFacade (统一入口: setGraph / diff / params)
      -> GraphDataStore        (节点/边/ID索引/邻接，单写)
      -> SimulationController  (仿真线程 + 物理快照)
      -> RenderPipeline        (可见性 + 几何 + GLRenderer)
      -> TextAtlasService      (MSDF 异步构建与缓存)
      -> InteractionController (输入状态机)
```

## 分阶段改造建议

### P0（先做稳定性）


### P1（拆核心耦合）
1. 抽离 `GraphDataStore`，收拢 `m_ids/m_labels/m_nodeColors/...`。
3. `SimulationController` 独立，封装线程和锁策略。

### P2（提性能上限）
1. 引入 dirty-flag 驱动的增量构建。
2. 运行时图修改改为增量更新 force，而非每次全量 `rebuildSimulation()`。
3. 为渲染构建链路增加可测性能指标（构建耗时、上传耗时、帧抖动）。

## 建议验收标准
- 线程一致性：运行时增删图不再依赖调用线程，行为稳定可复现。
- 模块边界：`ForceViewOpenGL` 只保留 UI 与编排，核心逻辑转入独立组件。
- 性能可观测：大图场景下 `tick/paint` 波动减小，diff 场景延迟可量化。
- 代码可维护性：删除“字符串 + dynamic_cast”参数通道，接口更强类型化。
