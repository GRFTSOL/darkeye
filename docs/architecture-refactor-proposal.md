# DarkEye 整体架构修改建议

> 基于对项目代码的全面阅读，提出以下架构层面的改进建议，按优先级与实施难度排序。

---

## 一、现状概览

### 当前架构分层
```
main.py (入口)
├── core/           # 核心业务：爬虫、数据库、图、推荐
├── controller/     # 控制器：信号总线、任务管理、快捷键
├── ui/             # 界面层：页面、组件、导航
├── server/         # 本地 API（FastAPI）对接浏览器插件
└── utils/          # 工具函数
```

### 数据流
- **UI → 数据库**：页面直接 import `core.database.query/insert/update/delete`，跨层调用
- **跨线程通信**：Server (FastAPI) → ServerBridge (Qt Signal) → MainWindow
- **事件通知**：`global_signals` 在 30+ 文件中使用，用于数据变更后的 UI 刷新

---

## 二、问题与改进建议

### 1. 数据层：Query 巨型模块 + 双连接体系（高优先级）

**现状**：
- `core/database/query.py` 超过 2000 行，被 30+ 文件直接引用
- 已统一为 sqlite3 `get_connection`（原 QSqlDatabaseManager 已移除）
- 仅 `WorkRepository` 采用 Repository 模式，其余为分散的 procedural 函数

**建议**：
1. **统一连接策略**
   - 全部使用 sqlite3 `get_connection`
   - 在文档中写明适用场景，避免混用

2. **按实体拆分 Repository**
   - `WorkRepository`（已有）
   - `ActressRepository`、`ActorRepository`、`TagRepository`、`MasturbationRepository` 等
   - 逐步将 `query.py` 中函数迁移到对应 Repository，保留旧函数为 deprecated wrapper

3. **引入 Service 层**
   - 创建 `core/services/`：如 `WorkService`、`ActressService`
   - 封装跨实体的业务（如「添加作品并关联女优、标签」），供 UI 和爬虫调用
   - 减少 UI 直接操作多表逻辑

---

### 2. UI 与数据层耦合（高优先级）

**现状**：
- 页面、组件、Router 直接 import 并调用 `core.database.*`
- 难以做单元测试和 UI 层与数据层解耦

**建议**：
1. **依赖注入**
   - 为页面/ViewModel 注入 `IWorkService`、`IActressService` 等接口
   - 在 `main.py` 或启动模块中统一构造并注入实现类

2. **避免 Router 持有业务逻辑**
   - `router.py` 中 `_handle_work_route` 调用了 `get_actor_allname`，属于数据访问
   - 将「根据 actor_id 获取显示名并填充到页面」这类逻辑移至 WorkPage 或 ViewModel
   - Router 只负责 `push(route_name, **params)` 与切换页面

---

### 3. MainWindow 职责过重（中优先级）

**现状**：
- 创建并持有所有页面
- 负责状态栏、内存监控、插件抓取处理、路由、快捷键等
- 页面在启动时全部创建，影响启动速度

**建议**：
1. **按需加载页面（Lazy 化）**
   - 已有 `LazyWidget` 和 `LazyScrollArea`，可扩展到页面级
   - 首次切换到某页面时再创建并缓存，减少启动开销

2. **抽取 ApplicationController**
   - 将 `handle_capture_data`、`handle_capture`、部分信号连接移到独立控制器
   - MainWindow 只负责布局、路由绑定和基础生命周期

3. **状态栏独立**
   - 将内存、线程数、任务通知等封装为 `StatusBarController`
   - 与 MainWindow 解耦，方便在无主窗口的场景复用（如 tray 模式）

---

### 4. 全局信号总线滥用（中优先级）

**现状**：
- `global_signals` 被广泛使用，数据流难以追踪
- 如 `work_data_changed` 可能触发多页面刷新，依赖关系不清晰
- 维护和调试成本高

**建议**：
1. **收敛事件类型**
   - 合并语义接近的信号（如 `actress_data_changed` 与选择器刷新）
   - 为信号添加清晰命名和文档，说明触发场景与订阅者

2. **局部事件优先**
   - 能在父子组件间通过参数或局部 Signal 传递的，不经过全局总线
   - 仅在跨模块、跨层级时使用 `global_signals`

3. **可选：引入轻量事件总线**
   - 使用 `typing.Protocol` 定义 `EventBus` 接口
   - 实现可替换，便于测试时注入 mock

---

### 5. CrawlerManager 与 DataUpdate 职责混杂（高优先级）

**现状**：
- `CrawlerManager` 负责：任务队列、多源分发、结果合并、触发写入
- `DataUpdate` 负责：标签处理、女优/男优插入、图片下载、DB 写入、信号发射
- 爬虫逻辑与数据持久化强耦合

**建议**：
1. **职责拆分**
   ```
   CrawlerManager (调度、分发)
        ↓ 产出 CrawledWorkData
   DataMergeService (多源合并、清洗)
        ↓ 产出标准 Work 领域对象
   WorkImportService (标签/女优/男优处理、图片下载、DB 写入)
   ```

2. **DataUpdate 重构**
   - 将 `DataUpdate` 拆成 `WorkImportService` 的用例
   - 女优/男优/标签的插入逻辑迁移到对应 Service
   - 图片下载单独成 `ImageDownloadService`，可被爬虫和手动添加共用

---

### 6. 模型与 Schema 不统一（中优先级）

**现状**：
- `core/database/model/model.py`：`Work` 等持久化模型
- `core/schema/model.py`：`CrawledWorkData` 爬虫 DTO
- `AddWorkTabPage3.Model`：页面内部数据模型
- 三者语义重叠，转换逻辑分散

**建议**：
1. **明确分层**
   - `core/schema/`：API、爬虫、外部输入的 DTO
   - `core/domain/` 或 `core/database/model/`：领域/持久化模型
   - UI ViewModel 持有领域模型或精简 DTO，不重复定义业务字段

2. **统一转换**
   - 在 Service 层集中处理 `CrawledWorkData` → `Work`、`Work` → 展示 DTO
   - 减少各页面手写转换逻辑

---

### 7. Server 与数据库访问方式不统一（中优先级）

**现状**：
- `server/app.py` 的 `check_existence` 直接用 sqlite3 连接
- 其他模块统一使用 `get_connection`

**建议**：
1. **Server 使用 sqlite3**
   - Server 在独立线程，使用 `get_connection(DATABASE, readonly=True)` 合理
   - 明确约定：只读接口用只读连接，避免锁冲突

2. **抽离共享查询**
   - 将 `check_existence` 的逻辑迁移到 `WorkRepository` 或 `WorkService`
   - Server 通过 `WorkService.check_exists(serials)` 调用，保持单一数据入口

---

### 8. 单例过多影响可测试性（低优先级）

**现状**：
- `Router`、`GraphManager`、`CrawlerManager`、`TaskManager`、`ServerBridge` 等均为单例
- 单元测试难以替换实现

**建议**：
1. **短期**
   - 为单例提供 `_instance = None` 的 reset 方法（仅用于测试）
   - 或用 `pytest` 的 fixture 在测试前重置

2. **长期**
   - 通过 DI 容器注入这些依赖，生产环境用单例实现，测试环境用 mock
   - 可考虑 `dependency-injector` 等轻量库

---

### 9. 启动顺序与错误恢复（低优先级）

**现状**：
- `main.py` 顺序执行：Sim 进程 → Graph → Server → DB 初始化 → 样式 → MainWindow
- 任一步骤失败可能导致半初始化状态

**建议**：
1. **启动阶段封装**
   - 将启动逻辑封装为 `Bootstrap` 或 `ApplicationContext`
   - 各阶段有明确成功/失败状态，失败时给出清晰错误信息并安全退出

2. **数据库迁移前置**
   - 在创建 MainWindow 之前完成所有 DB 检查和迁移
   - 避免 UI 已展示但数据库未就绪

---

### 10. 配置与路径管理（低优先级）

**现状**：
- `config.py` 混合路径解析、`QSettings`、常量
- `resource_path`、`get_PATH` 等职责略杂

**建议**：
1. **模块化**
   - `config/paths.py`：路径解析、打包适配
   - `config/settings.py`：QSettings 与 ini 读写
   - `config/constants.py`：版本号、默认值等常量

---

## 三、推荐实施顺序

| 阶段 | 内容 | 预期收益 |
|------|------|----------|
| **P0** | 统一数据连接策略，拆分 query.py 到 Repository | 降低耦合，便于后续重构 |
| **P0** | CrawlerManager / DataUpdate 职责拆分 | 爬虫与持久化解耦，逻辑更清晰 |
| **P1** | 引入 Service 层，UI 通过 Service 访问数据 | 可测试性提升，Router 瘦身 |
| **P1** | MainWindow 职责拆分，页面 Lazy 加载 | 启动更快，结构更清晰 |
| **P2** | 收敛 global_signals，规范事件流 | 便于维护和排错 |
| **P2** | 统一模型与 Schema | 减少重复定义和转换错误 |
| **P3** | 配置模块化、单例可测试化 | 提升长期可维护性 |

---

## 四、架构演进目标示意

```
┌─────────────────────────────────────────────────────────────┐
│  main.py / Bootstrap                                        │
│  - 初始化 DB、Graph、Server、样式                            │
│  - 构建 DI 容器或 Service 实例                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  MainWindow                                                 │
│  - 布局、路由、状态栏                                        │
│  - 注入 PageFactory (Lazy 创建页面)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Pages / Dialogs (UI)                                       │
│  - 接收 ViewModel 或 Service 注入                            │
│  - 不直接 import core.database                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Services (WorkService, ActressService, ...)                │
│  - 封装业务逻辑，跨实体操作                                   │
│  - 调用 Repository                                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Repositories (WorkRepo, ActressRepo, ...)                  │
│  - 单一实体的 CRUD                                          │
│  - 使用统一的 connection 获取方式                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Database (get_connection)                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、小结

整体来看，项目功能完整，分层和模块划分已有雏形，主要问题集中在：

1. **数据层**：Query 过大、双连接、Repository 应用不彻底  
2. **耦合**：UI 直连数据库、Router 含业务逻辑、Crawler 与持久化混在一起  
3. **职责**：MainWindow 过重、全局信号使用过广  

建议从数据层与爬虫拆分入手，再逐步引入 Service 层和依赖注入，在不大幅改写的前提下渐进式改进，以降低风险并保持可交付性。
