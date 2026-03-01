# DarkEye 项目架构评估与改造建议（仅文档，不改代码）

更新时间：2026-02-27

## 1. 评估范围与方法

本次评估基于项目全量文件扫描与关键模块抽样深读，未修改任何代码文件。

- 扫描规模（基于 `rg --files --hidden`，排除 `.git`）：433 个文件
- 其中可解析文本文件：366 个
- Python 文件：249 个
- Python 结构统计：约 306 个类、2228 个函数
- 发现 1 个语法异常文件：`manual_tests/rubbish/rubbish.py`（unexpected indent）

说明：仓库包含 `build/`、`junk/`、`manual_tests/` 等实验或产物目录，本评估已区分“生产路径”和“非生产路径”的影响。

## 2. 当前总体架构（现状）

从目录结构看，项目意图采用“分层 + 领域模块化”架构：

- 启动与配置：`main.py`、`config.py`、`app_context.py`
- UI 层：`ui/`（主窗口、页面、导航、组件）
- 业务与能力层：`core/`
  - 数据库：`core/database/`
  - 图谱：`core/graph/`
  - 爬虫：`core/crawler/`
  - 推荐与其他能力：`core/recommendation/` 等
- 控制与跨模块通信：`controller/`
- 本地服务桥接：`server/`（FastAPI + bridge）
- 高性能渲染扩展：`cpp_bindings/forced_direct_view`

该结构在“功能覆盖”和“技术野心”上较强，但在“依赖边界”和“模块职责”上已出现明显退化。

## 3. 主要优点（应保留）

1. 功能域划分清晰
- `core / ui / controller / server` 目录层次整体可读，便于新人定位模块。

2. 图谱模块技术深度较高
- `core/graph` + `cpp_bindings` 形成了 Python 业务与 C++ 渲染协作路径，性能扩展空间充足。

3. 本地优先与隐私导向设计较明确
- SQLite、本地服务桥接、资源目录分层，符合离线/隐私场景。

4. 已具备“可重构基础设施”
- 存在 Router、Repository、ThemeManager 等抽象雏形，可作为后续架构收敛锚点。

## 4. 关键问题（按优先级）

## P0（需要优先治理）

1. 分层边界被穿透，UI 直接操作数据库能力
- 现象：`ui` 多处直接 import `core.database.query/insert/update/delete`。
- 风险：
  - 页面逻辑与数据逻辑强耦合，导致页面改动引发数据行为回归。
  - 复用困难（CLI、服务端接口、自动化任务无法共享同一业务规则）。
  - 测试只能做“页面级联调”，单元测试价值低。

2. 数据访问技术路径不一致
- 现象：`QSqlDatabaseManager` 与 `sqlite3 get_connection` 并存。
- 风险：
  - 连接生命周期、事务边界、锁冲突处理策略不统一。
  - 线上问题定位困难（同类问题在不同路径行为不一致）。

3. 超大“God Module”阻碍演进
- 典型文件：
  - `core/database/query.py`（约 2000+ 行）
  - `ui/pages/AddWorkTabPage3.py`（约 1000+ 行）
  - `ui/main_window.py`
  - `core/crawler/CrawlerManager.py`
- 风险：
  - 修改成本高，回归范围不可控。
  - 代码评审粒度过粗，缺陷容易漏过。

## P1（中期治理）

4. 全局单例/全局信号使用过重
- 现象：`Router`、`GraphManager`、`CrawlerManager`、`ServerBridge`、`GlobalSignalBus` 等作为全局入口。
- 风险：
  - 状态来源不透明，副作用扩散。
  - 初始化顺序敏感，启动时序问题多。

5. 存在跨包循环依赖
- 已识别到 `ui / controller / main`、`core/database / utils` 等环。
- 风险：
  - 依赖方向失真，重构时牵一发而动全身。
  - 导入时机和运行时行为易产生隐性 bug。

6. 路由层职责膨胀
- `ui/navigation/router.py` 除导航外承载部分业务状态组织。
- 风险：页面切换逻辑和业务逻辑互相污染，难以替换导航方案。

## P2（持续改进）

7. 自动化测试覆盖不足
- `tests/` 下正式单测较少，验证主要依赖 `manual_tests/`。
- 风险：重构无法得到可靠保护网。

8. 工程质量基线不统一
- 现象：较多 `print`、宽泛 `except Exception`、占位 `pass`。
- 风险：问题吞噬、日志不可观测、线上行为不可诊断。

9. 仓库“生产代码”与“实验/废弃代码”混杂
- `junk/`、`manual_tests/`、部分临时脚本与主路径并存。
- 风险：新人识别成本高，CI 与发布边界不清晰。

## 5. 架构改造建议（不改业务功能的前提下）

## 5.1 目标架构（建议）

建议收敛为四层：

1. Presentation（UI）
- 仅处理交互、展示、输入校验。
- 不直接访问 `query/insert/update/delete`。

2. Application（Service/UseCase）
- 编排业务流程、事务策略、跨仓储协同。
- 作为 UI 与数据层唯一入口。

3. Domain/Repository
- 实体规则、仓储接口与实现。

4. Infrastructure
- SQLite、FastAPI bridge、Crawler adapter、C++ binding 封装。

## 5.2 具体落地动作

1. 建立 Service 层并冻结“UI 直连 DB”增量
- 立即规则：新需求禁止在 `ui/` 直接引入 `core.database.*(query|insert|update|delete)`。
- 先从高频页面切入：`WorkPage`、`AddWorkTabPage3`、`SettingPage`。

2. 拆分 `core/database/query.py`
- 按聚合拆为：WorkQueryRepository、ActorRepository、TagRepository、StatsRepository。
- 将跨聚合逻辑上移到 Application Service，避免 Repository 互相嵌套调用。

3. 统一数据库连接与事务策略
- 明确“单一数据访问主通道”（建议优先沿用当前主流路径并补齐能力）。
- 统一事务控制、连接池/连接复用、错误码映射。

4. 给 Router 减负
- Router 只做页面装配与导航。
- 页面业务状态迁移到对应 Service + ViewModel（或 Presenter）层。

5. 拆分 CrawlerManager
- 拆成：任务调度、下载执行、解析归一、落库同步四个子服务。
- 每个子服务单独可测，主流程只做编排。

6. 管理全局单例
- 保留少量基础设施级单例（如配置、日志）。
- 业务单例改为显式依赖注入（至少在构造函数注入）。

7. 清理依赖环
- 建立依赖方向约束：`ui -> application -> domain -> infrastructure`。
- 在 CI 增加“循环依赖检测”与“禁止跨层导入”检查。

8. 补测试保护网
- 第一批优先：
  - 数据服务（事务、边界条件）
  - 路由行为（导航与状态隔离）
  - 图谱会话/差分逻辑（`graph_session` / `graph_manager`）
- 目标：先覆盖“高变更、高风险”链路。

9. 仓库分区治理
- 明确：`src`（生产）、`tests`（自动化）、`manual_tests`（手工）、`junk`（隔离/归档）。
- 对 `junk` 设置归档策略和过期清理规则，避免持续污染主干。

## 6. 分阶段路线图（建议）

## 第 0 阶段（1-2 周）：架构止血

- 发布导入规则：禁止 UI 新增直连 DB。
- 新增最小 CI 检查：lint + 单测冒烟 + 循环依赖扫描。
- 明确“单一数据访问主通道”与事务规范文档。

## 第 1 阶段（2-4 周）：高风险模块解耦

- 拆 `query.py` 的首批仓储。
- 将 `AddWorkTabPage3` 的数据库调用迁移到 Service。
- Router 仅保留导航职责，业务状态开始外移。

## 第 2 阶段（4-8 周）：能力域重构

- 拆分 `CrawlerManager` 为四子服务。
- 整理全局单例，替换高风险业务单例。
- 为图谱与爬虫核心链路补自动化测试。

## 第 3 阶段（持续）：工程化与可维护性收敛

- 清理 `manual_tests/rubbish` 等无效代码。
- 建立架构决策记录（ADR）与重构验收标准。
- 定期输出架构健康度指标（耦合、圈复杂度、测试覆盖、缺陷回归率）。

## 7. 建议关注的关键文件（改造优先）

- `core/database/query.py`
- `ui/pages/AddWorkTabPage3.py`
- `ui/main_window.py`
- `ui/navigation/router.py`
- `core/crawler/CrawlerManager.py`
- `controller/GlobalSignalBus.py`
- `main.py`

## 8. 结论

DarkEye 当前并非“架构错误”，而是处于“功能先行后的架构债集中暴露期”。

建议策略不是推倒重来，而是：
- 先立边界（UI 不直连 DB、统一数据通道）
- 再拆大模块（query/router/crawler）
- 同步补测试和 CI 约束

按上述路径推进，能在不影响现有功能交付的前提下，显著降低后续维护成本与回归风险。
