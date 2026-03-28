"""Kodi 风格 <movie> NFO 解析并写入公有库 work 表。"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import DATABASE, TEMP_PATH
from controller.GlobalSignalBus import global_signals
from core.crawler.download import download_image_with_retry
from core.database.connection import get_connection
from core.database.insert import (
    InsertNewActor,
    InsertNewActress,
    InsertNewLabel,
    InsertNewMaker,
    InsertNewSeries,
    InsertNewWorkByHand,
    insert_tag,
    rename_save_image,
)
from core.database.query import (
    exist_actor,
    exist_actress,
    get_tagid_by_keyword,
    get_workid_by_serialnumber,
)
from core.database.query.work import (
    get_label_id_by_name,
    get_maker_id_by_name,
    get_series_id_by_name,
)
from core.database.update import update_actress_image


@dataclass
class NfoCastEntry:
    """Kodi 风格 <actor>：name + 可选头像 thumb。"""

    name: str
    thumb: str


@dataclass
class ParsedMovieNfo:
    """仅含从 XML 读取的字段，不含数据库 id。"""

    serial_number: str
    jp_title: str
    jp_story: str
    director: str
    release_date: str | None
    runtime: int | None
    notes: str
    studio_raw: str
    genre_names: list[str]
    tag_names: list[str]  # 来自 <tag>，入库时解析为系列（首条非空）
    fanart_json: str | None
    cast: list[NfoCastEntry]
    work_thumb_candidates: list[str]  # movie 直接子级 <thumb>，用于作品封面


def _text(root: ET.Element, tag: str) -> str:
    node = root.find(tag)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _parse_runtime(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_cast_entries(movie: ET.Element) -> list[NfoCastEntry]:
    out: list[NfoCastEntry] = []
    for node in movie.findall("actor"):
        nm = _text(node, "name")
        th = _text(node, "thumb")
        nm = nm.strip()
        if nm:
            out.append(NfoCastEntry(name=nm, thumb=(th or "").strip()))
    return out


def _movie_level_thumb_candidates(movie: ET.Element) -> list[str]:
    """仅 movie 直接子节点 <thumb>（不包含 fanart 内缩略图）。"""
    urls: list[str] = []
    for thumb in movie.findall("thumb"):
        u = (thumb.text or "").strip()
        if not u:
            u = (thumb.get("preview") or "").strip()
        if u:
            urls.append(u)
    return urls


def _fallback_cover_thumb_from_cast(cast: list[NfoCastEntry]) -> str | None:
    """无 movie 级 thumb 时：优先取已解析为女优的卡司的 thumb，再取首条非空头像。"""

    for entry in cast:
        thumb = (entry.thumb or "").strip()
        if not thumb:
            continue
        name = (entry.name or "").strip()
        if name and exist_actress(name) is not None:
            return thumb
    for entry in cast:
        thumb = (entry.thumb or "").strip()
        if thumb:
            return thumb
    return None


def _is_large_thumb_path(path: str) -> bool:
    """Jvedio 等：BigPic / large / 大图 视为封面大图。"""
    low = path.lower().replace("\\", "/")
    return "bigpic" in low or "largepic" in low or "/large/" in low or "大图" in path


def _is_small_thumb_path(path: str) -> bool:
    """小封面图路径：有大图时一律不采用。"""
    low = path.lower().replace("\\", "/")
    return "smallpic" in low or "small_pic" in low or "/small/" in low or "小图" in path


def _pick_work_cover_source(candidates: list[str]) -> str | None:
    """本地封面：有可用大图则只用大图，绝不再用小图；无大图再考虑中性路径、小图，最后 URL。"""
    locals_ok: list[str] = []
    remotes: list[str] = []
    for c in candidates:
        t = (c or "").strip()
        low = t.lower()
        if low.startswith("http://") or low.startswith("https://"):
            remotes.append(t)
            continue
        if Path(t).is_file():
            locals_ok.append(t)

    large_locals = [p for p in locals_ok if _is_large_thumb_path(p)]
    small_locals = [p for p in locals_ok if _is_small_thumb_path(p)]
    neutral_locals = [
        p for p in locals_ok if p not in large_locals and p not in small_locals
    ]

    if large_locals:
        # 同为大图时优先 BigPic，再其它 large
        large_locals.sort(key=lambda p: (0 if "bigpic" in p.lower() else 1, p.lower()))
        return large_locals[0]
    if neutral_locals:
        return neutral_locals[0]
    if small_locals:
        return small_locals[0]
    if remotes:
        return remotes[0]
    return None


def _prepare_local_image_path(src: str) -> str | None:
    """供 rename_save_image 使用的本地绝对路径；http(s) 先下载到临时文件。"""
    s = (src or "").strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        TEMP_PATH.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = TEMP_PATH / f"nfo_img_{ts}.jpg"
        ok, _ = download_image_with_retry(s, str(dest), retries=1)
        return str(dest.resolve()) if ok else None
    p = Path(s)
    return str(p.resolve()) if p.is_file() else None


def _work_cover_filename(serial_number: str) -> str:
    return serial_number.strip().lower().replace("-", "") + "pl.jpg"


def _resolve_cast_from_nfo(
    cast: list[NfoCastEntry],
) -> tuple[list[int], list[int], bool, bool]:
    """按 JAV NFO 常见顺序：首个库外人员建为女优，之后库外人员建为男优。"""
    actress_ids: list[int] = []
    actor_ids: list[int] = []
    seen_a: set[int] = set()
    seen_o: set[int] = set()
    actress_added = False
    actor_added = False
    first_unknown_as_actress = True

    for entry in cast:
        name = (entry.name or "").strip()
        if not name:
            continue
        aid = exist_actress(name)
        if aid is not None:
            if aid not in seen_a:
                seen_a.add(aid)
                actress_ids.append(aid)
            continue
        oid = exist_actor(name)
        if oid is not None:
            if oid not in seen_o:
                seen_o.add(oid)
                actor_ids.append(oid)
            continue
        if first_unknown_as_actress:
            if InsertNewActress(name, name):
                actress_added = True
            aid = exist_actress(name)
            first_unknown_as_actress = False
            if aid is not None and aid not in seen_a:
                seen_a.add(aid)
                actress_ids.append(aid)
        else:
            if InsertNewActor(name, name):
                actor_added = True
            oid = exist_actor(name)
            if oid is not None and oid not in seen_o:
                seen_o.add(oid)
                actor_ids.append(oid)
    return actress_ids, actor_ids, actress_added, actor_added


def _update_actor_image_only(actor_id: int, image_filename: str) -> None:
    conn = get_connection(DATABASE, False)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE actor SET image_url=? WHERE actor_id=?", (image_filename, actor_id)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def _apply_cast_portraits(cast: list[NfoCastEntry]) -> tuple[bool, bool]:
    """将各 <actor><thumb> 写入头像并移动到 actressimages/actorimages。"""
    actress_image_touched = False
    actor_image_touched = False
    for entry in cast:
        thumb = (entry.thumb or "").strip()
        if not thumb:
            continue
        name = (entry.name or "").strip()
        if not name:
            continue
        local = _prepare_local_image_path(thumb)
        if not local:
            logging.warning("NFO 头像无法解析或下载：%s", thumb[:80])
            continue
        aid = exist_actress(name)
        if aid is not None:
            dest_file = f"{aid}-{name}.jpg"
            rename_save_image(local, dest_file, "actress")
            update_actress_image(aid, dest_file)
            actress_image_touched = True
            continue
        oid = exist_actor(name)
        if oid is not None:
            dest_file = f"{oid}-{name}.jpg"
            rename_save_image(local, dest_file, "actor")
            _update_actor_image_only(oid, dest_file)
            actor_image_touched = True
    return actress_image_touched, actor_image_touched


def _collect_fanart_urls(movie: ET.Element) -> str | None:
    fan = movie.find("fanart")
    if fan is None:
        return None
    items: list[dict] = []
    for thumb in fan.findall("thumb"):
        url = (thumb.text or "").strip()
        if not url:
            url = (thumb.get("preview") or "").strip()
        if url:
            items.append({"url": url, "file": ""})
    if not items:
        return None
    return json.dumps(items, ensure_ascii=False)


def parse_movie_nfo(path: Path) -> tuple[ParsedMovieNfo | None, str | None]:
    """
    解析 NFO 文件（不访问数据库）。
    成功返回 (ParsedMovieNfo, None)，失败返回 (None, 错误信息)。
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        return None, f"XML 解析失败：{e}"
    except OSError as e:
        return None, f"无法读取文件：{e}"

    root = tree.getroot()
    if root is None or root.tag != "movie":
        return None, "根元素必须是 <movie>"

    serial = _text(root, "id") or _text(root, "num")
    serial = serial.strip()
    if not serial:
        return None, "NFO 中缺少番号（<id> 或 <num>）"

    premiered = _text(root, "premiered")
    release = _text(root, "release")
    release_date = (premiered or release) or None
    if release_date == "":
        release_date = None

    genre_names = [(g.text or "").strip() for g in root.findall("genre")]
    genre_names = [g for g in genre_names if g]
    tag_names = [(t.text or "").strip() for t in root.findall("tag")]
    tag_names = [t for t in tag_names if t]

    parsed = ParsedMovieNfo(
        serial_number=serial,
        jp_title=_text(root, "title"),
        jp_story=_text(root, "plot"),
        director=_text(root, "director"),
        release_date=release_date,
        runtime=_parse_runtime(_text(root, "runtime")),
        notes=_text(root, "source"),
        studio_raw=_text(root, "studio"),
        genre_names=genre_names,
        tag_names=tag_names,
        fanart_json=_collect_fanart_urls(root),
        cast=_parse_cast_entries(root),
        work_thumb_candidates=_movie_level_thumb_candidates(root),
    )
    return parsed, None


def _resolve_maker_label(studio_raw: str) -> tuple[int | None, int | None, bool, bool]:
    maker_id: int | None = None
    label_id: int | None = None
    maker_added = False
    label_added = False
    if not studio_raw:
        return maker_id, label_id, maker_added, label_added
    parts = [p.strip() for p in studio_raw.split("/", 1)]
    maker_name = parts[0] if parts else ""
    label_name = parts[1].strip() if len(parts) > 1 else ""

    if maker_name:
        maker_id = get_maker_id_by_name(maker_name)
        if maker_id is None:
            maker_id = InsertNewMaker(maker_name)
            if maker_id is None:
                raise RuntimeError(f"创建片商失败：{maker_name}")
            maker_added = True

    if label_name:
        label_id = get_label_id_by_name(label_name)
        if label_id is None:
            label_id = InsertNewLabel(label_name)
            if label_id is None:
                raise RuntimeError(f"创建厂牌失败：{label_name}")
            label_added = True

    return maker_id, label_id, maker_added, label_added


def _resolve_series_from_nfo_tags(tag_names: list[str]) -> tuple[int | None, bool]:
    """NFO 的 <tag> 视为系列名：取首条非空，匹配或新建 series。"""
    series_name = ""
    for t in tag_names:
        s = (t or "").strip()
        if s:
            series_name = s
            break
    if not series_name:
        return None, False
    series_id = get_series_id_by_name(series_name)
    if series_id is not None:
        return series_id, False
    series_id = InsertNewSeries(series_name)
    if series_id is None:
        raise RuntimeError(f"创建系列失败：{series_name}")
    return series_id, True


def _resolve_tag_names(names: list[str]) -> tuple[list[int], bool]:
    tag_ids: list[int] = []
    seen: set[int] = set()
    tag_added = False
    for name in names:
        tid = get_tagid_by_keyword(name, match_hole_word=True)
        if tid:
            tid = int(tid)
        else:
            ok, _msg, tid = insert_tag(name, 11, "#cccccc", "", None, [])
            if not ok or tid is None:
                raise RuntimeError(f"创建标签失败：{name}")
            tag_added = True
        if tid not in seen:
            seen.add(tid)
            tag_ids.append(tid)
    return tag_ids, tag_added


def import_work_from_movie_nfo(path: Path) -> tuple[bool, str]:
    """
    从 NFO 导入一条作品。番号已存在则跳过写入。
    返回 (是否视为成功, 提示文案)。已跳过导入时返回 (False, 说明番号已存在)。
    """
    p = Path(path)
    if not p.is_file():
        return False, "不是有效的文件路径"

    parsed, err = parse_movie_nfo(p)
    if parsed is None:
        return False, err or "解析失败"

    if get_workid_by_serialnumber(parsed.serial_number) is not None:
        return False, f"番号「{parsed.serial_number}」已在库中，已跳过导入。"

    try:
        maker_id, label_id, maker_added, label_added = _resolve_maker_label(
            parsed.studio_raw
        )
        tag_ids, tag_added = _resolve_tag_names(list(dict.fromkeys(parsed.genre_names)))
        series_id, series_added = _resolve_series_from_nfo_tags(parsed.tag_names)
        actress_ids, actor_ids, actress_added, actor_added = _resolve_cast_from_nfo(
            parsed.cast
        )
    except RuntimeError as e:
        return False, str(e)

    if maker_added:
        global_signals.maker_data_changed.emit()
    if label_added:
        global_signals.label_data_changed.emit()
    if series_added:
        global_signals.series_data_changed.emit()
    if tag_added:
        global_signals.tag_data_changed.emit()
    if actress_added:
        global_signals.actress_data_changed.emit()
    if actor_added:
        global_signals.actor_data_changed.emit()

    director = parsed.director.strip() or "----"
    jp_title = parsed.jp_title.strip() or None
    jp_story = parsed.jp_story.strip() or None
    notes = parsed.notes.strip() or None

    cover_src = _pick_work_cover_source(parsed.work_thumb_candidates)
    if not cover_src:
        cover_src = _fallback_cover_thumb_from_cast(parsed.cast)
    image_url: str | None = None
    if cover_src:
        local_cover = _prepare_local_image_path(cover_src)
        if local_cover:
            cover_name = _work_cover_filename(parsed.serial_number)
            rename_save_image(local_cover, cover_name, "cover")
            image_url = cover_name
        else:
            logging.warning("NFO 作品封面无法加载：%s", cover_src[:120])

    ok = InsertNewWorkByHand(
        parsed.serial_number,
        director,
        parsed.release_date,
        notes,
        parsed.runtime,
        list(dict.fromkeys(actress_ids)),
        list(dict.fromkeys(actor_ids)),
        None,
        None,
        jp_title,
        jp_story,
        image_url,
        tag_ids,
        maker_id,
        label_id,
        series_id,
        parsed.fanart_json,
    )
    if not ok:
        logging.warning(
            "InsertNewWorkByHand failed for NFO import: %s", parsed.serial_number
        )
        return False, "写入数据库失败"

    global_signals.work_data_changed.emit()

    img_act, img_actor = _apply_cast_portraits(parsed.cast)
    if img_act:
        global_signals.actress_data_changed.emit()
    if img_actor:
        global_signals.actor_data_changed.emit()

    return True, f"已从 NFO 导入作品：{parsed.serial_number}"
