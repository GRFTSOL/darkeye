"""从公共库导出男优中文名与日文名，写入简单 JSON 列表。

输出为扁平字符串数组 ``["中文名", "日文名", ...]``：中、日名字按行依次混入，**整表去重**（首次出现保留，忽略空串）。

用法（在项目根目录）::

    python scripts/export_actors_cn_jp.py
    python scripts/export_actors_cn_jp.py -o D:\\out\\actors.json
    python scripts/export_actors_cn_jp.py --all-names

默认输出到项目根目录 ``actors_cn_jp_export.json``。
``--all-names`` 含别名（每条 ``actor_name`` 一行），否则每位男优只保留一条主名。
"""

from __future__ import annotations

import argparse
import configparser
import json
import sqlite3
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _public_db_path() -> Path:
    """解析公共库路径，不导入 ``config``（避免无 Qt 环境下加载 PySide6 失败）。"""
    root = _repo_root()
    ini = root / "data" / "settings.ini"
    default = (root / "data" / "public" / "public.db").resolve()

    if not ini.is_file():
        return default

    parser = configparser.ConfigParser()
    parser.read(ini, encoding="utf-8")
    raw = None
    if parser.has_section("Paths"):
        section = parser["Paths"]
        for key in ("Database", "database"):
            if key in section:
                raw = section[key]
                break
    if not raw:
        return default

    p = Path(raw)
    if p.is_absolute():
        return p if p.exists() else default
    cand = (root / p).resolve()
    return cand if cand.exists() else default


def _parse_args() -> argparse.Namespace:
    default_out = _repo_root() / "actors_cn_jp_export.json"
    p = argparse.ArgumentParser(
        description="导出男优中/日文名为去重后的扁平字符串列表"
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_out,
        help=f"输出 JSON 文件路径（默认：{default_out}）",
    )
    p.add_argument(
        "--all-names",
        action="store_true",
        help="导出每条 actor_name（含别名），否则每位男优仅一条主名",
    )
    return p.parse_args()


def _open_public_readonly(db_path: Path) -> sqlite3.Connection:
    """只读打开公共库（不经过 ``core`` 包，避免拉取 PySide6）。"""
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _push_unique(out: list[str], seen: set[str], *candidates: str | None) -> None:
    for raw in candidates:
        s = (raw or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)


def export_flat_primary(conn: sqlite3.Connection) -> list[str]:
    """每位男优一条：优先 name_type=1；该条先中文后日文并入总表去重。"""
    cur = conn.execute(
        """
        SELECT a.actor_id, n.cn, n.jp
        FROM actor a
        LEFT JOIN actor_name n ON n.actor_id = a.actor_id
        ORDER BY a.actor_id, n.name_type DESC, n.actor_name_id
        """
    )
    seen_actor: set[int] = set()
    seen_name: set[str] = set()
    out: list[str] = []
    for actor_id, cn, jp in cur:
        if actor_id in seen_actor:
            continue
        seen_actor.add(actor_id)
        _push_unique(out, seen_name, cn, jp)
    return out


def export_flat_all_names(conn: sqlite3.Connection) -> list[str]:
    """每条 actor_name 先 cn 后 jp，顺序扫描并去重。"""
    cur = conn.execute(
        """
        SELECT cn, jp
        FROM actor_name
        ORDER BY actor_id, name_type DESC, actor_name_id
        """
    )
    seen_name: set[str] = set()
    out: list[str] = []
    for cn, jp in cur:
        _push_unique(out, seen_name, cn, jp)
    return out


def main() -> None:
    args = _parse_args()

    db_path = _public_db_path()
    if not db_path.is_file():
        sys.stderr.write(f"找不到公共数据库: {db_path}\n")
        sys.exit(1)

    conn = _open_public_readonly(db_path)
    try:
        if args.all_names:
            data = export_flat_all_names(conn)
        else:
            data = export_flat_primary(conn)
    finally:
        conn.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    args.output.write_text(text, encoding="utf-8")
    print(f"已写入 {len(data)} 个不重复名字 -> {args.output.resolve()}")


if __name__ == "__main__":
    main()
