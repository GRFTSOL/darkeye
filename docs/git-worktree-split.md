# DarkEye 按功能块拆分与 Git Worktree 开发建议

> 基于对 `docs/`、`server/`、`ui/`、`core/`、`controller/` 及 `main.py` 的阅读，给出用 Git Worktree 分块开发的划分方案与注意事项。

---

## 一、现状依赖关系概览

```
main.py
├── config.py
├── server/          ← 独立线程 FastAPI，仅依赖 config + bridge（Qt 信号）
├── core.database    ← 被 ui、crawler、graph、server（只读 sqlite）使用
├── core.graph       ← 被 ui（ForceDirectPage、AddWorkTabPage3）使用，依赖 controller
├── core.crawler     ← 被 ui 多处使用，CrawlerManager 依赖 controller
├── core.recommendation ← main_window 随机推荐
├── controller/      ← 被 ui、core（graph_manager、CrawlerManager）使用，无 core 依赖
└── ui/              ← 依赖 controller、core（database/query|insert|update|delete、crawler、graph）
```

- **controller**：仅提供全局信号、快捷键、消息框等，体量小，与 **ui** 同进同退更简单。
- **server**：只依赖 `config.DATABASE` 和 `bridge`，与 core 无直接 import，适合单独 worktree。
- **core**：database 被全栈使用；graph 与 crawler 都依赖 database，且会发 `global_signals`。
- **ui**：大量页面直接 import `core.database.query/insert/update/delete` 和 crawler、graph，与 core 耦合度高。

---

## 二、推荐拆分：三块功能用 Worktree 分开开发

按「谁常改、合并冲突尽量少」的原则，建议 **3 个 worktree**，对应 3 条长期分支（或 feature 分支）。

### 1. 内核 (core)

| 项 | 说明 |
|----|------|
| **目录** | `core/` 全量（database, graph, crawler, recommendation, schema, utils, cv） |
| **分支示例** | `dev/core` 或 `feature/core-data`、`feature/crawler` |
| **适合工作** | 数据库重构、Repository/Service 拆分、query 瘦身、图逻辑与过滤、爬虫多源与清洗、推荐算法、迁移与备份 |
| **注意** | 修改接口（函数签名、模块划分）时尽量在 core 分支完成，再在 ui 分支适配，避免双向改同一处 |

### 2. 服务与采集 (server)

| 项 | 说明 |
|----|------|
| **目录** | `server/`、`extensions/`（如 `firefox_capture`） |
| **分支示例** | `dev/server` 或 `feature/inbox`、`feature/plugin-api` |
| **适合工作** | FastAPI 路由、`/api/v1/check_existence` 与 `/capture`、ServerBridge 信号、浏览器插件、Inbox 待处理队列 |
| **注意** | 与主进程通过 `bridge` 和 `config` 交互，不直接 import core，可独立跑接口测试 |

### 3. 界面与入口 (ui)

| 项 | 说明 |
|----|------|
| **目录** | `ui/`、`controller/`、`design/`、`styles/`、`main.py`、`config.py` |
| **分支示例** | `dev/ui` 或 `feature/shelf`、`feature/dashboard` |
| **适合工作** | 主窗口、Router、侧栏、所有页面与组件、对话框、快捷键与状态栏、主题与 QSS、启动流程 |
| **注意** | 会依赖 core 与 server 的“当前接口”；core/server 分支合并后再在 ui worktree 合并并改调用处 |

---

## 三、Worktree 操作示例

```bash
# 假设主仓库在 x:/10-Project/darkeye，当前在 dev 分支

# 1. 内核 worktree（在 core 上做数据库/图/爬虫重构）
git worktree add ../darkeye-core dev/core
# 或先建分支再 add
git branch dev/core
git worktree add ../darkeye-core dev/core

# 2. 服务端 worktree（做 API / 插件 / Inbox）
git worktree add ../darkeye-server dev/server

# 3. 界面 worktree（做主界面、页面、样式）
git worktree add ../darkeye-ui dev/ui

# 日常：在对应目录开发、提交、推送
# 合并顺序建议：先合并 dev/core → 再 dev/server（可并行）→ 最后在 dev 或 main 上合并 dev/ui
```

---

## 四、可选：关系图单独一块（第 4 个 Worktree）

若 **关系图（ForceView）** 迭代非常频繁、且希望与「数据库/爬虫」改动完全并行，可单独拆出：

| 项 | 说明 |
|----|------|
| **目录** | `core/graph/`、`cpp_bindings/forced_direct_view/`、`ui/pages/ForceDirectPage.py` |
| **分支示例** | `dev/graph` |
| **适合工作** | 力导向图、过滤与会话、C++ 渲染与性能、图设置面板、ForceDirectPage 交互 |
| **注意** | 与 core（graph 依赖 database、controller）和 ui（其他页面、Router）有交叉；合并时易冲突，建议约定：**图相关改动集中在此分支**，core 只做 database 接口、ui 只做路由与入口，减少同一文件在多分支被改。 |

---

## 五、合并顺序与冲突规避

1. **推荐合并顺序**  
   `dev/core` → `dev/server`（可与 core 并行）→ 在 `dev` 或 `main` 上合并 `dev/ui`。这样 ui 总是基于最新的 core 与 server 接口做适配。

2. **减少冲突**  
   - core 分支：尽量不改 `ui/`、`main.py`；接口变更在 core 内完成并提交，再到 ui 分支一次性适配。  
   - server 分支：只改 `server/`、`extensions/`，必要时改 `config.py`（路径/常量），避免动 core。  
   - ui 分支：以「调用方」为主，适配 core/server 的接口变更；若在 ui 分支修 bug，涉及 core 的尽量只改「调用方式」，逻辑改动放到 core 分支。

3. **controller**  
   controller 体量小且被 ui 与 core 共同依赖，放在 **ui worktree** 里一起改即可；若未来拆成独立包再考虑单独 worktree。

---

## 六、小结表

| 功能块 | 主要目录 | 典型分支 | 主要职责 |
|--------|----------|----------|----------|
| **内核 (core)** | `core/` | dev/core | 数据层、图、爬虫、推荐、工具与模型 |
| **服务与采集 (server)** | `server/`, `extensions/` | dev/server | 本地 API、插件桥接、Inbox/采集 |
| **界面与入口 (ui)** | `ui/`, `controller/`, `design/`, `styles/`, `main.py`, `config.py` | dev/ui | 主窗口、路由、页面与组件、快捷键与状态栏、启动与配置 |
| **关系图 (可选)** | `core/graph/`, `cpp_bindings/forced_direct_view/`, `ui/pages/ForceDirectPage.py` | dev/graph | 力导向图与 C++ 渲染、图页 |

按上述 **3 块（或 4 块）** 用 worktree 分开开发，可以较好地在并行开发时控制冲突，并保持与当前架构（develop.md、architecture-refactor-proposal.md）一致。

```mermaid
flowchart LR
    A[开始] --> B[处理]
    B --> C[结束]
```