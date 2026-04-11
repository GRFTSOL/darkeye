"""多源爬取结果合并（旧桌面路径）；生产环境已改为插件合并 + ``merge_service.crawled_work_from_extension_payload``。

仅保留供单元测试回归，与 ``extensions/firefox_capture/merge_work.js`` 字段对齐思路一致。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict

from config import resource_path
from core.schema.model import CrawledWorkData
from utils.serial_number import convert_fanza

_exclude_genre_cache: frozenset[str] | None = None

_FANZA_PL_SKIP_MAKER_SUBSTR: frozenset[str] = frozenset(
    (
        "sod",
        "SOD Create",
        "ソフト・オン・デマンド",
        "SODクリエイト",
        "prestige",
        "プレステージ",
    )
)
_FANZA_PL_SKIP_SERIAL_PREFIXES: frozenset[str] = frozenset(
    (
        "START",
        "STARS",
        "SDJS",
        "SDAB",
        "SDDE",
        "SDMU",
        "SDNM",
        "SDMM",
        "SDAF",
        "SDHS",
        "FC2",
        "LUXU",
    )
)


def _fanza_pl_serial_head(serial: str) -> str:
    s = serial.strip().upper()
    if not s:
        return ""
    if "-" in s:
        return s.split("-", 1)[0]
    i = 0
    while i < len(s) and s[i].isalpha():
        i += 1
    return s[:i] if i else s


def _skip_fanza_pl_priority_cover(maker: str, canonical_serial: str) -> bool:
    m = (maker or "").strip().lower()
    if m and any(sub in m for sub in _FANZA_PL_SKIP_MAKER_SUBSTR):
        return True
    head = _fanza_pl_serial_head(canonical_serial)
    return bool(head) and head in _FANZA_PL_SKIP_SERIAL_PREFIXES


_FANZA_PL_MIN_RELEASE_YEAR = 2018


def _release_year_is_before(release_date: str, year: int) -> bool:
    s = (release_date or "").strip()
    if not s:
        return False
    m = re.search(r"(?:19|20)\d{2}", s)
    if not m:
        return False
    return int(m.group(0)) < year


def exclude_genre_set() -> frozenset[str]:
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


def merge_crawl_results(
    results: Dict[str, dict], canonical_serial: str
) -> CrawledWorkData:
    """合并各源结果为标准 CrawledWorkData。翻译在 ``DataUpdate`` 中统一处理。"""
    javlib_result = results.get("javlib") or {}
    javtxt_result = results.get("javtxt") or {}
    avdanyuwiki_result = results.get("avdanyuwiki") or {}
    javdb_result = results.get("javdb") or {}

    release_date = (
        javlib_result.get("release_date")
        or avdanyuwiki_result.get("release_date")
        or javdb_result.get("release_date")
        or javtxt_result.get("release_date")
        or ""
    )
    director = (
        avdanyuwiki_result.get("director")
        or javlib_result.get("director")
        or javdb_result.get("director")
        or javtxt_result.get("director")
        or ""
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

    def _urls(x):
        if x is None:
            return []
        return [x] if isinstance(x, str) else (x if isinstance(x, list) else [])

    maker = (
        avdanyuwiki_result.get("maker")
        or javlib_result.get("maker")
        or javdb_result.get("maker")
        or javtxt_result.get("maker")
        or ""
    )

    cover_list = [
        u for u in _urls(javlib_result.get("image")) if u and isinstance(u, str)
    ]
    sn = canonical_serial.strip()
    if (
        sn
        and not _skip_fanza_pl_priority_cover(maker, sn)
        and not _release_year_is_before(release_date, _FANZA_PL_MIN_RELEASE_YEAR)
    ):
        cid = convert_fanza(sn.upper())
        fanza_pl = (
            f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg"
        )
        cover_list.insert(0, fanza_pl)
    avdanurl = avdanyuwiki_result.get("cover") or ""
    if avdanurl:
        cover_list.append(avdanurl)
    serial_lower = canonical_serial.lower()
    cover_list.append("https://fourhoi.com/" + serial_lower + "/cover-n.jpg")

    javdburl = javdb_result.get("cover") or ""
    if javdburl:
        cover_list.append(javdburl)

    _avdan_series = avdanyuwiki_result.get("series") or ""
    if _avdan_series in ("", "----"):
        series = javdb_result.get("series") or javtxt_result.get("series") or ""
    else:
        series = _avdan_series

    label = (
        avdanyuwiki_result.get("label")
        or javlib_result.get("label")
        or javdb_result.get("label")
        or javtxt_result.get("label")
        or ""
    )

    tag_list = avdanyuwiki_result.get("tag_list") or []
    genre_jav = javlib_result.get("genre") or []
    genre_javdb = javdb_result.get("genre") or []
    genre_javtxt = javtxt_result.get("genre") or []
    genre_raw = (
        (tag_list if isinstance(tag_list, list) else [])
        + (genre_jav if isinstance(genre_jav, list) else [])
        + (genre_javdb if isinstance(genre_javdb, list) else [])
        + (genre_javtxt if isinstance(genre_javtxt, list) else [])
    )
    excluded_genres = exclude_genre_set()
    genre_list = [
        g
        for g in set(str(x) for x in genre_raw if x is not None)
        if g not in excluded_genres
    ]

    jp_title = (
        javlib_result.get("title")
        or javtxt_result.get("jp_title")
        or javdb_result.get("title")
        or ""
    )

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
        "fanart_list": fanart_list,
    }

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
