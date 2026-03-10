# 写操作 → 信号映射表

写操作完成后，**调用方负责** emit 对应的 `global_signals.*_changed` 信号。本表便于排查遗漏。

## 信号列表（GlobalSignalBus）

| 信号 | 用途 |
|------|------|
| `work_data_changed` | 作品数据变更 |
| `actress_data_changed` | 女优数据变更（刷新女优选择器等） |
| `actor_data_changed` | 男优数据变更（刷新男优选择器等） |
| `tag_data_changed` | 标签数据变更（刷新标签选择器等） |
| `masterbation_changed` | 撸管记录变更 |
| `lovemaking_changed` | 做爱记录变更 |
| `sexarousal_changed` | 晨勃记录变更 |
| `like_work_changed` | 喜欢作品变更 |
| `like_actress_changed` | 喜欢女优变更 |

---

## insert.py

| 函数 | 需 emit 的信号 |
|------|----------------|
| `InsertNewActress` | `actress_data_changed` |
| `InsertNewActor` | `actor_data_changed` |
| `InsertNewWork` | `work_data_changed` |
| `InsertNewWorkByHand` | `work_data_changed` |
| `insert_tag` | `tag_data_changed` |
| `add_tag2work` | `work_data_changed` |
| `insert_masturbation_record` | `masterbation_changed` |
| `insert_lovemaking_record` | `lovemaking_changed` |
| `insert_sexual_arousal_record` | `sexarousal_changed` |
| `insert_liked_actress` | `like_actress_changed` |
| `insert_liked_work` | `like_work_changed` |
| `InsertAliasName` | `actress_data_changed` |

---

## delete.py

| 函数 | 需 emit 的信号 |
|------|----------------|
| `delete_favorite_actress` | `like_actress_changed` |
| `delete_favorite_work` | `like_work_changed` |
| `delete_work` | `work_data_changed` |
| `delete_actress` | `actress_data_changed` |
| `delete_actor` | `actor_data_changed` |
| `delete_tag` | `tag_data_changed` |

---

## update.py

| 函数 | 需 emit 的信号 |
|------|----------------|
| `update_tag_type` | `tag_data_changed` |
| `UpdateWorkTags` | `work_data_changed` |
| `update_work_byhand` | `work_data_changed` |
| `update_work_byhand_` | `work_data_changed` |
| `update_work_actor` | `work_data_changed` |
| `update_db_actress` | `actress_data_changed` |
| `update_actress_image` | `actress_data_changed` |
| `update_actress_minnano_id` | `actress_data_changed`（若影响展示） |
| `update_work_javtxt` | 通常无需（内部缓存） |
| `update_titlestory` | `work_data_changed` |
| `update_tag_color` | `tag_data_changed` |
| `update_fanza_cover_url` | 通常无需（内部缓存） |
| `update_on_dan` | 通常无需（内部状态） |
| `update_tag` | `tag_data_changed` |
| `mark_delete` | `work_data_changed` |
| `mark_undelete` | `work_data_changed` |
| `update_actress_byhand` | `actress_data_changed` |
| `update_actor_byhand` | `actor_data_changed` |
| `redirect_tag_121` | `tag_data_changed` |

---

## 内部辅助函数（无需单独 emit）

以下函数由其他写函数内部调用，由调用方统一 emit 即可：

- `_update_actor`, `_update_actress`, `_update_worktag`（由 `update_work_byhand` 等调用）
- `update_actress_name`, `update_actor_name`, `update_tag_alias`（由 `update_*_byhand` 等调用）
