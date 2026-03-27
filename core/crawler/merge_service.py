from __future__ import annotations

import json
import logging
import traceback
from typing import Dict

from config import resource_path
from core.schema.model import CrawledWorkData
from utils.utils import translate_text_sync

_exclude_genre_cache: frozenset[str] | None = None


def exclude_genre_set() -> frozenset[str]:
    """从 resources/config/exclude_genre.json 读取需排除的 genre 名（带缓存）。"""
    global _exclude_genre_cache
    if _exclude_genre_cache is not None:
        return _exclude_genre_cache
    path = resource_path("resources/config/exclude_genre.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("exclude_genre", [])
        _exclude_genre_cache = frozenset(str(x) for x in items if x is not None)
    except Exception as e:
        logging.warning("读取 exclude_genre.json 失败，将不排除任何 genre: %s", e)
        _exclude_genre_cache = frozenset()
    return _exclude_genre_cache


def merge_crawl_results(results: Dict[str, dict], canonical_serial: str) -> CrawledWorkData:
    """合并各源结果为标准 CrawledWorkData（含同步翻译）。不依赖 CrawlerManager。"""
    javlib_result = results.get("javlib") or {}
    javtxt_result = results.get("javtxt") or {}
    avdanyuwiki_result = results.get("avdanyuwiki") or {}
    javdb_result = results.get("javdb") or {}

    release_date = javlib_result.get(
        "release_date",
        avdanyuwiki_result.get("release_date", javdb_result.get("release_date", "")),
    )
    director = avdanyuwiki_result.get(
        "director",
        javlib_result.get("director", javdb_result.get("director", "")),
    )
    runtime = avdanyuwiki_result.get(
        "runtime",
        javlib_result.get("length", javdb_result.get("length", "")),
    )
    actress_list = (
        avdanyuwiki_result.get("actress_list")
        or javlib_result.get("actress")
        or javdb_result.get("actress")
        or []
    )
    #这里最好加一个屏蔽词

    def _urls(x):
        if x is None:
            return []
        return [x] if isinstance(x, str) else (x if isinstance(x, list) else [])

    cover_list = [u for u in _urls(javlib_result.get("image")) if u and isinstance(u, str)]
    avdanurl = avdanyuwiki_result.get("cover") or ""
    if avdanurl:
        cover_list.append(avdanurl)
    serial_lower = canonical_serial.lower()
    cover_list.append("https://fourhoi.com/" + serial_lower + "/cover-n.jpg")

    maker = (
        avdanyuwiki_result.get("maker")
        or javlib_result.get("maker")
        or javdb_result.get("maker")
        or ""
    )
    series = (
        avdanyuwiki_result.get("series")
        or javdb_result.get("series")
        or ""
    )
    label = (
        avdanyuwiki_result.get("label")
        or javlib_result.get("label")
        or javdb_result.get("label")
        or ""
    )

    tag_list = avdanyuwiki_result.get("tag_list") or []
    genre_jav = javlib_result.get("genre") or []
    genre_javdb = javdb_result.get("genre") or []
    genre_raw = (
        (tag_list if isinstance(tag_list, list) else [])
        + (genre_jav if isinstance(genre_jav, list) else [])
        + (genre_javdb if isinstance(genre_javdb, list) else [])
    )
    excluded_genres = exclude_genre_set()
    genre_list = [
        g
        for g in set(str(x) for x in genre_raw if x is not None)
        if g not in excluded_genres
    ]

    jp_title = javlib_result.get("title", javtxt_result.get("jp_title", ""))

    fanart_list = javlib_result.get("fanart") or javdb_result.get("fanart") or []

    work_merge = {
        "serial_number": canonical_serial,
        "release_date": release_date,
        "director": director,
        "runtime": runtime,
        "actress_list": actress_list,
        "maker": maker,
        "series": series,
        "label": label,
        "actor_list": avdanyuwiki_result.get("actor_list") or [],
        "genre_list": genre_list,
        "cn_title": javtxt_result.get("cn_title", ""),
        "jp_title": jp_title,
        "cn_story": javtxt_result.get("cn_story", ""),
        "jp_story": javtxt_result.get("jp_story", ""),
        "cover_list": cover_list,
        "fanart_list": fanart_list
    }

    try:
        if work_merge["cn_title"] == "" and work_merge["jp_title"] != "":
            work_merge["cn_title"] = translate_text_sync(work_merge["jp_title"], fallback="empty")
        if work_merge["cn_story"] == "" and work_merge["jp_story"] != "":
            work_merge["cn_story"] = translate_text_sync(work_merge["jp_story"], fallback="empty")
    except Exception as e:
        logging.warning(
            "merge_crawl_results 翻译失败，使用原文: %s\n%s",
            e,
            traceback.format_exc(),
        )

    logging.info("基本聚合结果: %s", work_merge)

    try:
        runtime_val = int(work_merge["runtime"]) if work_merge["runtime"] else 0
    except (ValueError, TypeError):
        runtime_val = 0

    return CrawledWorkData(
        serial_number=work_merge["serial_number"],
        director=work_merge["director"],
        release_date=work_merge["release_date"],
        runtime=runtime_val,
        cn_title=work_merge["cn_title"],
        jp_title=work_merge["jp_title"],
        cn_story=work_merge["cn_story"],
        jp_story=work_merge["jp_story"],
        tag_list=work_merge["genre_list"],
        actress_list=work_merge["actress_list"],
        actor_list=work_merge["actor_list"],
        cover_url_list=work_merge["cover_list"],
        maker=work_merge["maker"],
        series=work_merge["series"],
        label=work_merge["label"],
        fanart_url_list=work_merge["fanart_list"],
    )
