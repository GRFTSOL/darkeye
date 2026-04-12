"""作品在库中的信息完整度：按固定顺序 15 维布尔，供爬虫 Inbox 等 UI 展示。"""

from __future__ import annotations

import json
import logging
from typing import Final

from ..connection import get_connection

logger = logging.getLogger(__name__)

# 与产品约定一致：左起第 1 盏灯到第 15 盏灯（UI / tuple 下标同序）。
WORK_COMPLETENESS_KEYS: Final[tuple[str, ...]] = (
    "cover",
    "actress",
    "actor",
    "director",
    "release_date",
    "runtime",
    "tag",
    "cn_title",
    "jp_title",
    "cn_story",
    "jp_story",
    "maker",
    "label",
    "series",
    "fanart",
)

# Tooltip / 无障碍文案（与 WORK_COMPLETENESS_KEYS 顺序一致）。
WORK_COMPLETENESS_LABELS_ZH: Final[tuple[str, ...]] = (
    "封面",
    "女优",
    "男优",
    "导演",
    "发售日",
    "时长",
    "标签",
    "中文标题",
    "日文标题",
    "中文简介",
    "日文简介",
    "片商",
    "厂牌",
    "系列",
    "多图",
)

_COMPLETENESS_ROW_SQL = """
SELECT
    w.image_url,
    (SELECT COUNT(1) FROM work_actress_relation wa WHERE wa.work_id = w.work_id),
    (SELECT COUNT(1) FROM work_actor_relation wo WHERE wo.work_id = w.work_id),
    w.director,
    w.release_date,
    w.runtime,
    (SELECT COUNT(1) FROM work_tag_relation wt WHERE wt.work_id = w.work_id),
    w.cn_title,
    w.jp_title,
    w.cn_story,
    w.jp_story,
    w.maker_id,
    w.label_id,
    w.series_id,
    w.fanart
FROM work w
WHERE w.work_id = ?
"""


def _nonempty_str(value: object) -> bool:
    if value is None:
        return False
    return str(value).strip() != ""


def _fanart_nonempty(value: object) -> bool:
    if value is None:
        return False
    raw = str(value).strip()
    if not raw:
        return False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.debug("fanart JSON 解析失败，完整度计为无")
        return False
    return isinstance(parsed, list) and len(parsed) > 0


def _fk_present(value: object) -> bool:
    if value is None:
        return False
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def read_work_completeness_flags(
    work_id: int | None,
    *,
    database: str | None = None,
) -> dict[str, bool]:
    """读取单部作品在库中的 15 维完整度（有则 True，无则 False）。

    须在可访问目标库的线程上调用（通常为数据库队列线程）。
    ``database`` 省略时使用 ``config.DATABASE``（单测可传入临时库路径）。
    """
    empty = {k: False for k in WORK_COMPLETENESS_KEYS}
    if work_id is None or work_id <= 0:
        return empty

    db_path = database
    if db_path is None:
        from config import DATABASE as _db

        db_path = str(_db)

    try:
        with get_connection(db_path, True) as conn:
            cur = conn.cursor()
            cur.execute(_COMPLETENESS_ROW_SQL, (work_id,))
            row = cur.fetchone()
    except Exception:
        logger.exception("read_work_completeness_flags 查询失败 work_id=%s", work_id)
        return empty

    if not row:
        return empty

    (
        image_url,
        actress_cnt,
        actor_cnt,
        director,
        release_date,
        runtime,
        tag_cnt,
        cn_title,
        jp_title,
        cn_story,
        jp_story,
        maker_id,
        label_id,
        series_id,
        fanart,
    ) = row

    try:
        rt = int(runtime) if runtime is not None and str(runtime).strip() != "" else 0
    except (TypeError, ValueError):
        rt = 0

    try:
        ac = int(actress_cnt or 0)
    except (TypeError, ValueError):
        ac = 0
    try:
        oc = int(actor_cnt or 0)
    except (TypeError, ValueError):
        oc = 0
    try:
        tc = int(tag_cnt or 0)
    except (TypeError, ValueError):
        tc = 0

    return {
        "cover": _nonempty_str(image_url),
        "actress": ac > 0,
        "actor": oc > 0,
        "director": _nonempty_str(director),
        "release_date": _nonempty_str(release_date),
        "runtime": rt > 0,
        "tag": tc > 0,
        "cn_title": _nonempty_str(cn_title),
        "jp_title": _nonempty_str(jp_title),
        "cn_story": _nonempty_str(cn_story),
        "jp_story": _nonempty_str(jp_story),
        "maker": _fk_present(maker_id),
        "label": _fk_present(label_id),
        "series": _fk_present(series_id),
        "fanart": _fanart_nonempty(fanart),
    }
