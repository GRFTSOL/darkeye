"""插件返回的作品载荷 → ``CrawledWorkData``。

多源桌面合并逻辑已迁至 ``tests/support/merge_crawl_legacy.py``（仅单测回归）。
"""

from __future__ import annotations

from typing import Any

from core.schema.model import CrawledWorkData


def crawled_work_from_extension_payload(data: dict[str, Any]) -> CrawledWorkData:
    """将插件 ``GET /api/v1/work`` 返回的 ``data`` 映射为 ``CrawledWorkData``（无翻译）。"""
    if not isinstance(data, dict):
        raise TypeError("extension payload must be a dict")
    sn = str(data.get("serial_number") or "").strip()
    try:
        rt = int(data.get("runtime")) if data.get("runtime") not in (None, "") else 0
    except (ValueError, TypeError):
        rt = 0
    tag = data.get("tag_list")
    if not isinstance(tag, list):
        tag = []
    al = data.get("actress_list")
    if not isinstance(al, list):
        al = []
    acl = data.get("actor_list")
    if not isinstance(acl, list):
        acl = []
    cov = data.get("cover_url_list")
    if not isinstance(cov, list):
        cov = []
    fan = data.get("fanart_url_list")
    if not isinstance(fan, list):
        fan = []
    return CrawledWorkData(
        serial_number=sn,
        director=str(data.get("director") or ""),
        release_date=str(data.get("release_date") or ""),
        runtime=rt,
        cn_title=str(data.get("cn_title") or ""),
        jp_title=str(data.get("jp_title") or ""),
        cn_story=str(data.get("cn_story") or ""),
        jp_story=str(data.get("jp_story") or ""),
        tag_list=[str(x) for x in tag if x is not None],
        actress_list=[str(x) for x in al if x is not None],
        actor_list=[str(x) for x in acl if x is not None],
        cover_url_list=[str(x).strip() for x in cov if x],
        maker=str(data.get("maker") or ""),
        series=str(data.get("series") or ""),
        label=str(data.get("label") or ""),
        fanart_url_list=[
            str(x).strip() for x in fan if isinstance(x, str) and str(x).strip()
        ],
    )
