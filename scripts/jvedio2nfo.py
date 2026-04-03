#!/usr/bin/env python3
# sqlite_to_nfo_with_actors.py
# 说明：基于 metadata + metadata_video + metadata_to_actor + actor_info 生成 .nfo（Kodi/Jellyfin/Emby 标准格式）

import sqlite3
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import hashlib
import re
import requests

# ----------------- 配置区（请修改） -----------------
DB_PATH = r"XXXXX\app_datas.sqlite"  # <-- 将XXXXX改成你Jvedio的数据库 sqlite 路径，文件名为“app_datas.sqlite”
OUTPUT_DIR = r""  # <-- NFO文件输出目录
WRITE_NFO_TO_VIDEO_DIR = False  # True: 若影片的视频路径存在，尝试写入影片的NFO中，可按需开启
DOWNLOAD_IMAGES = False  # True: 会下载演员与海报图片（需 requests），可按需开启
IMAGE_SAVE_DIR = r""  # 若下载图片，保存位置
SAMPLE_LIMIT = None  # 测试时仅处理前 N 条，设为 None 处理全部

# 本地图片根目录（Jvedio 常见结构）
PIC_ROOT = r""  # Jvedio文件保存的图片目录，通常在 Jvedio 的 data 目录下，里面有 BigPic 和 SmallPic 等子目录
BIGPIC_DIR = "BigPic"
SMALLPIC_DIR = "SmallPic"

# 若本地没有图片，是否回退到原始在线链接
FALLBACK_TO_ONLINE_IMAGE_URL = True
# -----------------------------------------------------

if DOWNLOAD_IMAGES:
    try:
        import requests
    except Exception:
        raise RuntimeError("DOWNLOAD_IMAGES=True 但未安装 requests。请先 pip install requests 并重启脚本。")


def format_to_yyyy_mm_dd(date_str):
    """将各种格式的日期强制转换为标准的 YYYY-MM-DD 格式"""
    if not date_str:
        return ""
    date_str = str(date_str).strip()

    match = re.search(r"(\d{4})[^\d]*(\d{1,2})[^\d]*(\d{1,2})", date_str)
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    match_ym = re.search(r"(\d{4})[^\d]*(\d{1,2})", date_str)
    if match_ym:
        y, m = match_ym.groups()
        return f"{int(y):04d}-{int(m):02d}-01"

    match_y = re.search(r"(\d{4})", date_str)
    if match_y:
        y = match_y.group(1)
        return f"{int(y):04d}-01-01"

    return date_str


def sanitize_xml_text(value):
    """
    清洗 XML 非法字符：
    保留 \t \n \r，以及 XML 1.0 允许的 Unicode 区间。
    这样可避免 minidom / ElementTree 在解析时因脏数据报错。
    """
    if value is None:
        return ""
    s = str(value)
    return "".join(
        ch for ch in s
        if ch == "\t" or ch == "\n" or ch == "\r"
        or 0x20 <= ord(ch) <= 0xD7FF
        or 0xE000 <= ord(ch) <= 0xFFFD
        or 0x10000 <= ord(ch) <= 0x10FFFF
    )


def safe_text(value):
    return sanitize_xml_text(value)


def indent_xml(elem, level=0):
    """兼容低版本 Python 的 XML 缩进。"""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def pretty_xml(elem):
    """
    格式化 XML，使用 ElementTree 输出，避免 minidom.parseString 对脏字符更敏感的问题。
    """
    try:
        ET.indent(elem, space="  ")
    except Exception:
        indent_xml(elem)

    xml_str = ET.tostring(
        elem,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=False
    ).decode("utf-8")

    xml_str = xml_str.replace(
        '<?xml version=\'1.0\' encoding=\'utf-8\'?>',
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        1
    ).replace(
        '<?xml version="1.0" encoding="utf-8"?>',
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        1
    )

    lines = [line for line in xml_str.splitlines() if line.strip()]
    xml_str = "\n".join(lines)
    return xml_str.encode("utf-8")


def add_text(parent, tag, text, force=False, default=""):
    """
    向父节点添加子节点。
    force=True 时，即使内容为空也会生成空标签，或使用 default 默认值。
    """
    val = safe_text(text)
    if not val and not force:
        return
    if not val and force:
        val = default
    el = ET.SubElement(parent, tag)
    el.text = val


def build_actor_node(parent, name, thumb=None, role=None):
    actor = ET.SubElement(parent, "actor")
    n = ET.SubElement(actor, "name")
    n.text = safe_text(name)
    if role:
        r = ET.SubElement(actor, "role")
        r.text = safe_text(role)
    if thumb:
        t = ET.SubElement(actor, "thumb")
        t.text = safe_text(thumb)


def ensure_dir(p):
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(s):
    if not s:
        return "unknown"
    keep = "-_.()[] {}"
    return "".join(c for c in s if c.isalnum() or c in keep).strip()[:200] or "unknown"


def download_image(url, save_dir):
    try:
        r = requests.get(url, timeout=15, stream=True)
        if r.status_code == 200:
            h = hashlib.sha1(url.encode("utf-8")).hexdigest()
            ext = os.path.splitext(url.split("?")[0])[1]
            if not ext:
                ext = ".jpg"
            fname = f"{h}{ext}"
            p = Path(save_dir) / fname
            with open(p, "wb") as fh:
                for chunk in r.iter_content(1024 * 8):
                    if not chunk:
                        break
                    fh.write(chunk)
            return str(p.resolve())
    except Exception:
        pass
    return url


def norm_key(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", str(s).upper())


def build_local_pic_index(pic_root):
    index = {
        BIGPIC_DIR: {},
        SMALLPIC_DIR: {},
    }
    root = Path(pic_root)
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    for folder in [BIGPIC_DIR, SMALLPIC_DIR]:
        folder_path = root / folder
        if not folder_path.exists():
            continue
        for p in folder_path.rglob("*"):
            if p.is_file() and p.suffix.lower() in valid_exts:
                key = norm_key(p.stem)
                if key and key not in index[folder]:
                    index[folder][key] = str(p.resolve())

    return index


LOCAL_PIC_INDEX = build_local_pic_index(PIC_ROOT)


def resolve_local_pic(nfo_id, folder_name):
    if not nfo_id:
        return None
    key = norm_key(nfo_id)
    return LOCAL_PIC_INDEX.get(folder_name, {}).get(key)


def load_actor_maps(conn):
    cur = conn.cursor()
    actor_map = {}
    data_to_actorids = {}

    try:
        cur.execute("SELECT * FROM actor_info;")
        for r in cur.fetchall():
            actorid = r["ActorID"] if "ActorID" in r.keys() else r[0]
            k = str(actorid)
            actor_map[k] = {col: r[col] if col in r.keys() else None for col in r.keys()}
    except Exception:
        pass

    try:
        cur.execute("SELECT * FROM metadata_to_actor;")
        for r in cur.fetchall():
            actorid = None
            dataid = None
            if "ActorID" in r.keys():
                actorid = r["ActorID"]
            else:
                try:
                    actorid = r[1]
                except Exception:
                    actorid = None
            if "DataID" in r.keys():
                dataid = r["DataID"]
            else:
                try:
                    dataid = r[2]
                except Exception:
                    dataid = None
            if actorid is None or dataid is None:
                continue
            key = str(dataid)
            data_to_actorids.setdefault(key, []).append(str(actorid))
    except Exception:
        pass

    return actor_map, data_to_actorids


def main():
    db = Path(DB_PATH)
    if not db.exists():
        print(f"错误：找不到数据库文件：{DB_PATH}")
        return

    out_dir = ensure_dir(OUTPUT_DIR)
    if DOWNLOAD_IMAGES:
        ensure_dir(IMAGE_SAVE_DIR)

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    actor_map, data_to_actorids = load_actor_maps(conn)
    print(f"加载演员信息：{len(actor_map)} 条；加载 data->actor 映射：{len(data_to_actorids)} 个 dataid")
    print(f"本地图片索引：BigPic {len(LOCAL_PIC_INDEX[BIGPIC_DIR])} 条；SmallPic {len(LOCAL_PIC_INDEX[SMALLPIC_DIR])} 条")

    cur = conn.cursor()
    sql = "SELECT m.*, mv.* FROM metadata m LEFT JOIN metadata_video mv ON mv.DataID = m.DataID"
    if SAMPLE_LIMIT and isinstance(SAMPLE_LIMIT, int):
        sql = sql + f" LIMIT {SAMPLE_LIMIT}"
    cur.execute(sql)
    rows = cur.fetchall()
    total = len(rows)
    print(f"读取到 {total} 条记录 (metadata JOIN metadata_video)")

    for idx, row in enumerate(rows, start=1):
        def g(k):
            return row[k] if k in row.keys() else None

        DataID = g("DataID")
        dataid_key = str(DataID) if DataID is not None else ""
        title = g("Title") or g("title") or ""
        path = g("Path") or ""

        raw_release_date = g("ReleaseDate") or ""
        release_date = format_to_yyyy_mm_dd(raw_release_date)

        release_year = g("ReleaseYear") or ""
        rating = g("Rating") or ""
        genre = g("Genre") or ""
        country = g("Country") or ""
        viewcount = g("ViewCount") or ""
        size = g("Size") or ""
        path_exist = g("PathExist")

        VID = g("VID") or ""
        director = g("Director") or ""
        studio = g("Studio") or ""
        plot = g("Plot") or g("Outline") or ""
        duration = g("Duration") or ""
        imageurls_raw = g("ImageUrls") or ""
        weburl = g("WebUrl") or ""
        series = g("Series") or ""

        nfo_id = VID or (str(DataID) if DataID is not None else "")
        nfo_id = str(nfo_id).strip()

        parsed_actor_names = []
        parsed_actress_imgs = []
        thumbs_from_imageurls = []
        fanarts = []

        try:
            if imageurls_raw:
                jo = json.loads(imageurls_raw)
                if isinstance(jo, dict):
                    small = jo.get("SmallImageUrl")
                    big = jo.get("BigImageUrl")
                    extra = jo.get("ExtraImageUrl") or []
                    actress_imgs = jo.get("ActressImageUrl") or []
                    actor_names = jo.get("ActorNames") or []
                    if big:
                        thumbs_from_imageurls.append(big)
                    if small and small not in thumbs_from_imageurls:
                        thumbs_from_imageurls.append(small)
                    if isinstance(extra, list):
                        fanarts.extend(extra)
                    if isinstance(actor_names, list):
                        parsed_actor_names = actor_names
                    if isinstance(actress_imgs, list):
                        parsed_actress_imgs = actress_imgs
        except Exception:
            pass

        target_dir = out_dir
        wrote_to_video_dir = False
        if WRITE_NFO_TO_VIDEO_DIR and path:
            try:
                p = Path(path)
                path_exists_flag = False
                if path_exist in (1, "1", True, "True", "true", "t"):
                    path_exists_flag = True
                if p.exists() or path_exists_flag:
                    parent = p.parent if p.parent else None
                    if parent:
                        target_dir = ensure_dir(parent)
                        wrote_to_video_dir = True
            except Exception:
                pass

        base_name = None
        if path:
            try:
                base_name = Path(path).stem
            except Exception:
                base_name = None
        if not base_name:
            base_name = VID or f"{DataID}"
        base_name = safe_filename(base_name)

        # ---------------- 构建 XML ----------------
        movie = ET.Element("movie")

        add_text(movie, "source", weburl, force=True)
        add_text(movie, "plot", plot, force=True)
        add_text(movie, "title", title)
        add_text(movie, "director", director, force=True)
        add_text(movie, "rating", rating, force=True, default="0")
        add_text(movie, "criticrating", "", force=True)

        y = release_year
        if not y and release_date:
            y = str(release_date)[:4]
        add_text(movie, "year", y, force=True, default="0")

        add_text(movie, "mpaa", "", force=True)
        add_text(movie, "customrating", "", force=True)
        add_text(movie, "countrycode", "", force=True)

        add_text(movie, "premiered", release_date)
        add_text(movie, "release", release_date)
        add_text(movie, "runtime", duration)

        add_text(movie, "country", country, force=True)
        add_text(movie, "studio", studio)

        add_text(movie, "id", nfo_id)
        add_text(movie, "num", nfo_id)

        if genre:
            genre_clean = str(genre).replace("\x07", ",").replace("\n", ",")
            for gi in [s.strip() for s in genre_clean.split(",") if s.strip()]:
                add_text(movie, "genre", gi)

        if series:
            add_text(movie, "tag", series)

        local_big = resolve_local_pic(nfo_id, BIGPIC_DIR)
        local_small = resolve_local_pic(nfo_id, SMALLPIC_DIR)
        thumb_candidates = []

        if local_big:
            thumb_candidates.append(local_big)
        elif FALLBACK_TO_ONLINE_IMAGE_URL and thumbs_from_imageurls:
            thumb_candidates.append(thumbs_from_imageurls[0])

        if local_small:
            if local_small != local_big:
                thumb_candidates.append(local_small)
        elif FALLBACK_TO_ONLINE_IMAGE_URL and len(thumbs_from_imageurls) > 1:
            online_small = thumbs_from_imageurls[1]
            if online_small not in thumb_candidates:
                thumb_candidates.append(online_small)

        seen_thumb = set()
        for t in thumb_candidates:
            if t and t not in seen_thumb:
                add_text(movie, "thumb", t)
                seen_thumb.add(t)

        if fanarts:
            fanart_el = ET.SubElement(movie, "fanart")
            for f in fanarts:
                t_el = ET.SubElement(fanart_el, "thumb")
                t_el.set("preview", safe_text(f))
                t_el.text = safe_text(f)

        actors_to_write = []
        if dataid_key and dataid_key in data_to_actorids:
            for aid in data_to_actorids[dataid_key]:
                act = actor_map.get(aid)
                if act:
                    name = act.get("ActorName") or act.get("actorname") or ""
                    thumb = act.get("ImageUrl") or act.get("imageurl") or None
                    actors_to_write.append((name, thumb))
                else:
                    actors_to_write.append((f"ActorID_{aid}", None))

        if not actors_to_write and parsed_actor_names:
            for idx_a, name in enumerate(parsed_actor_names):
                thumb = parsed_actress_imgs[idx_a] if idx_a < len(parsed_actress_imgs) else None
                actors_to_write.append((name, thumb))

        seen = set()
        actors_filtered = []
        for n, t in actors_to_write:
            key = (n or "").strip()
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            actors_filtered.append((n, t))
        actors_to_write = actors_filtered

        for (name, thumb) in actors_to_write:
            final_thumb = thumb
            if DOWNLOAD_IMAGES and thumb:
                final_thumb = download_image(thumb, IMAGE_SAVE_DIR)
            build_actor_node(movie, name, thumb=final_thumb)

        # 出错时输出当前数据，方便定位脏字段
        try:
            xml_bytes = pretty_xml(movie)
        except Exception as e:
            print(f"\n[XML生成失败] idx={idx}, DataID={DataID}, VID={VID}")
            print("title =", repr(title))
            print("plot  =", repr(plot[:300]))
            print("director =", repr(director))
            print("weburl =", repr(weburl))
            raise

        out_path = Path(target_dir) / (f"{base_name}.nfo")
        try:
            with open(out_path, "wb") as fh:
                fh.write(xml_bytes)
        except Exception:
            fallback = out_dir / (f"{base_name}.nfo")
            with open(fallback, "wb") as fh:
                fh.write(xml_bytes)
            out_path = fallback

        if idx % 50 == 0 or idx == total:
            where = "视频目录" if wrote_to_video_dir else "输出目录"
            print(f"[{idx}/{total}] 写入：{out_path} ({where})")

    conn.close()
    print("\n全部完成！输出目录：", out_dir.resolve())
    if DOWNLOAD_IMAGES:
        print("图片保存目录：", Path(IMAGE_SAVE_DIR).resolve())


if __name__ == "__main__":
    main()