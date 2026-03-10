# 数据层说明

本文档描述 DarkEye 数据层的连接策略、模块职责与写操作后的信号约定。

---

## 1. 架构决策

- **无 ORM**：不使用 SQLAlchemy 等 ORM，直接使用 sqlite3。
- **无 Repository/Service 中间层**：UI 直接调用 `core.database.query/insert/update/delete`。
- **统一连接**：全部通过 `core.database.connection.get_connection` 获取连接。

---

## 2. 连接策略

### 2.1 获取连接

```python
from core.database.connection import get_connection

# 只读（查询、统计等）
with get_connection(database, readonly=True) as conn:
    cur = conn.execute("SELECT ...")

# 可读写（插入、更新、删除）
with get_connection(database, readonly=False) as conn:
    conn.execute("INSERT ...")
    conn.commit()
```

### 2.2 参数说明

| 参数 | 说明 |
|------|------|
| `database` | 数据库路径（`config.DATABASE` 公共库、`config.PRIVATE_DATABASE` 私有库） |
| `readonly` | `True` 只读模式（`mode=ro`），`False` 可读写（`mode=rwc`） |

### 2.3 连接特性

- 自动开启外键约束（`PRAGMA foreign_keys=ON`）
- 设置 `busy_timeout=5000` 避免锁等待过长
- 使用 `with` 确保连接正确关闭

### 2.4 私有库

需要联合查询公共库与私有库时，使用 `db_utils.attach_private_db(cursor)` / `detach_private_db(cursor)` 做 ATTACH。

---

## 3. Query 模块职责

`core/database/query/` 按业务域拆分为子模块，由 `__init__.py` 聚合导出。

| 子模块 | 职责 |
|--------|------|
| `work.py` | 作品相关：`get_workinfo_by_workid`、`get_actress_from_work_id`、`get_serial_number` 等 |
| `actress.py` | 女优相关：`get_actress_info`、`exist_actress`、`get_actressname` 等 |
| `actor.py` | 男优相关：`get_actor_info`、`exist_actor`、`get_actor_allname` 等 |
| `tag.py` | 标签相关：`get_tags`、`get_taginfo_by_id`、`get_tagid_by_keyword` 等 |
| `dashboard.py` | 仪表盘：`get_dashboard_stats` |
| `statistics.py` | 统计：`fetch_work_actress_avg_age`、`get_tag_frequence` 等 |
| `private.py` | 私有库：`query_actress`、`query_work`、`get_record_by_year` 等 |

**调用方式**：`from core.database.query import get_workinfo_by_workid, get_actress_info, ...`

---

## 4. 写操作与 Insert/Update/Delete

| 模块 | 职责 |
|------|------|
| `core/database/insert.py` | 新增：`InsertNewWork`、`InsertNewActress`、`insert_tag`、`insert_masturbation_record` 等 |
| `core/database/update.py` | 更新：`update_work_byhand`、`update_actress_byhand`、`mark_delete`、`update_tag` 等 |
| `core/database/delete.py` | 删除：`delete_work`、`delete_actress`、`delete_tag`、`delete_favorite_work` 等 |

---

## 5. 写操作后需 emit 的全局信号

**约定**：写操作完成后，**调用方**负责 emit 对应的 `global_signals.*_changed`，以通知其他 UI 组件刷新。

### 5.1 信号与写操作映射

| 信号 | 触发场景 | 典型调用方 |
|------|----------|------------|
| `work_data_changed` | 作品增删改、封面更新、标记删除/恢复 | AddWorkTabPage3、CrawlerManager、RecycleBinPage |
| `actress_data_changed` | 女优增删改 | ModifyActressPage、AddActressDialog、CrawlerManager |
| `actor_data_changed` | 男优增删改 | ModifyActorPage、AddActorDialog、CrawlerManager |
| `tag_data_changed` | 标签增删改、颜色/重定向变更 | TagManagement、CrawlerManager |
| `like_work_changed` | 喜欢/取消喜欢作品 | SingleWorkPage |
| `like_actress_changed` | 喜欢/取消喜欢女优 | SingleActressInfo |
| `masterbation_changed` | 自慰记录新增 | AddMasturbationDialog |
| `lovemaking_changed` | 做爱记录新增 | AddMakeLoveDialog |
| `sexarousal_changed` | 晨勃记录新增 | AddSexualArousalDialog |

### 5.2 其他信号（非数据变更）

| 信号 | 用途 |
|------|------|
| `status_msg_changed(str)` | 状态栏文字 |
| `download_success(str)` | 图片下载完成 |
| `gui_update(dict)` | 通用 GUI 更新通知 |
| `green_mode_changed(bool)` | 绿色模式切换 |

### 5.3 示例

```python
from core.database.update import update_tag
from controller.GlobalSignalBus import global_signals

# 更新标签后
if update_tag(tag_id, ...):
    global_signals.tag_data_changed.emit()
```

---

## 6. UI 表格模型

- **SqliteQueryTableModel**：只读表格，传入 SQL 与 database，通过 `get_connection` 执行查询，`refresh()` 重新加载。
- **SqliteEditableTableModel**：可编辑表格，传入表名与 database，支持 CRUD，同样使用 `get_connection`。

两者均不依赖 Qt SQL 模块，直接使用 sqlite3。
