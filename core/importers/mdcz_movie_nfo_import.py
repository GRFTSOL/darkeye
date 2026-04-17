"""MDCZ 风格 <movie> NFO 解析并写入公有库 work 表。"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from controller.global_signal_bus import global_signals
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

_WIN_FILENAME_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class ParsedMdczMovieNfo:
    """MDCZ NFO 解析结果（仅文件侧字段）。"""

    nfo_path: Path
    serial_number: str
    jp_title: str
    jp_story: str
    director: str
    release_date: str | None
    runtime: int | None
    notes: str
    studio_raw: str
    genre_names: list[str]
    tag_names: list[str]
    actor_names: list[str]
    cover_local_path: str | None
    fanart_items: list[dict[str, str]]
    extrafanart_pairs: list[tuple[str, str, Path]]


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


def _parse_serial(root: ET.Element) -> str:
    serial = _text(root, "id") or _text(root, "num")
    if serial.strip():
        return serial.strip().upper()

    unique_nodes = root.findall("uniqueid")
    preferred: str | None = None
    fallback: str | None = None
    for node in unique_nodes:
        txt = (node.text or "").strip()
        if not txt:
            continue
        if fallback is None:
            fallback = txt
        if (node.get("default") or "").strip().lower() == "true":
            preferred = txt
            break
    serial = preferred or fallback or ""
    return serial.strip().upper()


def _safe_fanart_stem(stem: str) -> str:
    stem = _WIN_FILENAME_FORBIDDEN.sub("_", stem).strip(" .")
    return stem or "fanart"


def _fanart_jpg_name_from_url(url: str) -> str | None:
    path = unquote(urlparse((url or "").strip()).path)
    base = Path(path).name
    if not base or base in (".", ".."):
        return None
    stem = _safe_fanart_stem(Path(base).stem)
    if not stem:
        return None
    return f"{stem}.jpg"


def _parse_actor_names(movie: ET.Element) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for node in movie.findall("actor"):
        name = _text(node, "name").strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _dedupe_names(names: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        s = (n or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _build_fanart_items_and_pairs(
    root: ET.Element,
    nfo_dir: Path,
) -> tuple[list[dict[str, str]], list[tuple[str, str, Path]]]:
    """构造 fanart JSON 条目及需要迁移的 extrafanart 源文件。

    约束：fanart 仅来自 <mdcz><scene_images><image>。
    """
    items: list[dict[str, str]] = []
    pairs: list[tuple[str, str, Path]] = []
    seen_url: set[str] = set()
    seen_file: set[str] = set()
    unresolved_scene_urls: list[tuple[str, str]] = []

    mdcz = root.find("mdcz")
    if mdcz is not None:
        scene = mdcz.find("scene_images")
        if scene is not None:
            for image_node in scene.findall("image"):
                url = (image_node.text or "").strip()
                if not url:
                    continue
                dest_name = _fanart_jpg_name_from_url(url)
                if not dest_name:
                    unresolved_scene_urls.append((url, ""))
                    continue

                src = (nfo_dir / "extrafanart" / dest_name).resolve()
                if src.is_file():
                    if dest_name not in seen_file:
                        items.append({"url": url, "file": dest_name})
                        seen_file.add(dest_name)
                        seen_url.add(url)
                        pairs.append((url, dest_name, src))
                    continue

                unresolved_scene_urls.append((url, dest_name))

        # 兜底：若文件名匹配不到，则按 scene_images 顺序与 extrafanart 文件顺序一一对应。
        # 这样可以兼容“本地命名与 URL basename 不一致”的工具导出。
        if unresolved_scene_urls:
            ext_dir = (nfo_dir / "extrafanart").resolve()
            all_files = []
            if ext_dir.is_dir():
                all_files = sorted(
                    [
                        p.resolve()
                        for p in ext_dir.iterdir()
                        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                    ],
                    key=lambda x: x.name.lower(),
                )
            used_src = {src for _url, _name, src in pairs}
            free_files = [p for p in all_files if p not in used_src]
            free_idx = 0
            for url, expected_name in unresolved_scene_urls:
                if url in seen_url:
                    continue
                if free_idx < len(free_files):
                    src = free_files[free_idx]
                    free_idx += 1
                    dest_name = expected_name or f"{_safe_fanart_stem(src.stem)}.jpg"
                    if dest_name in seen_file:
                        dest_name = f"{_safe_fanart_stem(src.stem)}_{free_idx}.jpg"
                    items.append({"url": url, "file": dest_name})
                    pairs.append((url, dest_name, src))
                    seen_url.add(url)
                    seen_file.add(dest_name)
                else:
                    items.append({"url": url, "file": ""})
                    seen_url.add(url)

    return items, pairs


def parse_mdcz_movie_nfo(path: Path) -> tuple[ParsedMdczMovieNfo | None, str | None]:
    """解析 MDCZ NFO 文件（不访问数据库）。"""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        return None, f"XML 解析失败：{e}"
    except OSError as e:
        return None, f"无法读取文件：{e}"

    root = tree.getroot()
    if root is None or root.tag != "movie":
        return None, "根元素必须是 <movie>"

    serial = _parse_serial(root)
    if not serial:
        return None, "NFO 中缺少番号（<id>/<num>/<uniqueid>）"

    release_date = _text(root, "premiered") or _text(root, "releasedate") or _text(
        root, "release"
    )
    release_date = release_date.strip() or None

    genre_names = _dedupe_names([(g.text or "").strip() for g in root.findall("genre")])
    tag_names = _dedupe_names([(t.text or "").strip() for t in root.findall("tag")])
    actor_names = _parse_actor_names(root)

    nfo_path = Path(path).resolve()
    nfo_dir = nfo_path.parent
    cover_path = (nfo_dir / "fanart.jpg").resolve()
    cover_local_path = str(cover_path) if cover_path.is_file() else None

    fanart_items, extrafanart_pairs = _build_fanart_items_and_pairs(root, nfo_dir)

    parsed = ParsedMdczMovieNfo(
        nfo_path=nfo_path,
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
        actor_names=actor_names,
        cover_local_path=cover_local_path,
        fanart_items=fanart_items,
        extrafanart_pairs=extrafanart_pairs,
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


def _resolve_series_from_set(root: ET.Element) -> tuple[int | None, bool]:
    set_node = root.find("set")
    if set_node is None:
        return None, False
    series_name = _text(set_node, "name").strip() or (set_node.text or "").strip()
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


def _resolve_cast_from_names(
    actor_names: list[str],
) -> tuple[list[int], list[int], bool, bool]:
    actress_ids: list[int] = []
    actor_ids: list[int] = []
    seen_a: set[int] = set()
    seen_o: set[int] = set()
    actress_added = False
    actor_added = False

    for name in actor_names:
        nm = (name or "").strip()
        if not nm:
            continue
        aid = exist_actress(nm)
        if aid is not None:
            if aid not in seen_a:
                seen_a.add(aid)
                actress_ids.append(aid)
            continue
        oid = exist_actor(nm)
        if oid is not None:
            if oid not in seen_o:
                seen_o.add(oid)
                actor_ids.append(oid)
            continue
        if InsertNewActress(nm, nm):
            actress_added = True
        aid = exist_actress(nm)
        if aid is not None and aid not in seen_a:
            seen_a.add(aid)
            actress_ids.append(aid)
        elif InsertNewActor(nm, nm):
            actor_added = True
            oid = exist_actor(nm)
            if oid is not None and oid not in seen_o:
                seen_o.add(oid)
                actor_ids.append(oid)

    return actress_ids, actor_ids, actress_added, actor_added


def _work_cover_filename(serial_number: str) -> str:
    return serial_number.strip().upper() + ".jpg"


def _delete_if_exists(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        logging.warning("删除源 fanart 文件失败：%s (%s)", path, e)


def _save_and_move_extrafanart_files(
    pairs: list[tuple[str, str, Path]],
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for url, dest_name, src in pairs:
        if not src.is_file():
            out.append({"url": url, "file": ""})
            continue
        rename_save_image(str(src), dest_name, "fanart")
        out.append({"url": url, "file": dest_name})
        _delete_if_exists(src)
    return out


def emit_after_mdcz_nfo_batch_import() -> None:
    """批量 MDCZ NFO 导入结束后统一刷新 UI。"""
    global_signals.makerDataChanged.emit()
    global_signals.labelDataChanged.emit()
    global_signals.seriesDataChanged.emit()
    global_signals.tagDataChanged.emit()
    global_signals.actressDataChanged.emit()
    global_signals.actorDataChanged.emit()
    global_signals.workDataChanged.emit()


def import_work_from_mdcz_movie_nfo(
    path: Path, *, emit_ui_signals: bool = True
) -> tuple[bool, str]:
    """从 MDCZ 风格 NFO 导入一条作品。"""
    p = Path(path)
    if not p.is_file():
        return False, "不是有效的文件路径"

    parsed, err = parse_mdcz_movie_nfo(p)
    if parsed is None:
        return False, err or "解析失败"

    if get_workid_by_serialnumber(parsed.serial_number) is not None:
        return False, f"番号「{parsed.serial_number}」已在库中，已跳过导入。"

    try:
        tree = ET.parse(parsed.nfo_path)
        root = tree.getroot()
        maker_id, label_id, maker_added, label_added = _resolve_maker_label(
            parsed.studio_raw
        )
        tag_names = _dedupe_names(parsed.genre_names + parsed.tag_names)
        tag_ids, tag_added = _resolve_tag_names(tag_names)
        series_id, series_added = _resolve_series_from_set(root)
        actress_ids, actor_ids, actress_added, actor_added = _resolve_cast_from_names(
            parsed.actor_names
        )
    except RuntimeError as e:
        return False, str(e)
    except ET.ParseError as e:
        return False, f"XML 解析失败：{e}"

    if emit_ui_signals:
        if maker_added:
            global_signals.makerDataChanged.emit()
        if label_added:
            global_signals.labelDataChanged.emit()
        if series_added:
            global_signals.seriesDataChanged.emit()
        if tag_added:
            global_signals.tagDataChanged.emit()
        if actress_added:
            global_signals.actressDataChanged.emit()
        if actor_added:
            global_signals.actorDataChanged.emit()

    director = parsed.director.strip() or "----"
    jp_title = parsed.jp_title.strip() or None
    jp_story = parsed.jp_story.strip() or None
    notes = parsed.notes.strip() or None

    image_url: str | None = None
    if parsed.cover_local_path:
        cover_name = _work_cover_filename(parsed.serial_number)
        rename_save_image(parsed.cover_local_path, cover_name, "cover")
        image_url = cover_name

    migrated = _save_and_move_extrafanart_files(parsed.extrafanart_pairs)
    fanart_items = list(migrated)
    migrated_urls = {x["url"] for x in migrated if x.get("url")}
    for item in parsed.fanart_items:
        url = (item.get("url") or "").strip()
        file = (item.get("file") or "").strip()
        if url and url in migrated_urls:
            continue
        fanart_items.append({"url": url, "file": file})
    fanart_json = json.dumps(fanart_items, ensure_ascii=False) if fanart_items else None

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
        fanart_json,
    )
    if not ok:
        logging.warning(
            "InsertNewWorkByHand failed for MDCZ NFO import: %s", parsed.serial_number
        )
        return False, "写入数据库失败"

    if emit_ui_signals:
        global_signals.workDataChanged.emit()

    return True, f"已从 NFO 导入作品：{parsed.serial_number}"
