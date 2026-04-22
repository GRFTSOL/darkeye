#!/usr/bin/env python3
"""打包 resources/avwiki 并生成 avwiki_latest.json。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AVWIKI_SRC = ROOT / "resources" / "avwiki"
OUTPUT_DIR = ROOT / "update" / "avwiki"
ZIP_NAME = "avwiki.zip"
MANIFEST_NAME = "avwiki_latest.json"
DEFAULT_PACKAGE_URL = "https://darkeye.win/avwiki.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="压缩 resources/avwiki，计算 sha256，并生成 avwiki_latest.json"
    )
    parser.add_argument(
        "--version",
        default=datetime.now().strftime("%Y.%m.%d"),
        help="写入 latestVersion，默认当天日期（YYYY.MM.DD）",
    )
    parser.add_argument(
        "--release-notes",
        default="",
        help="写入 releaseNotes",
    )
    parser.add_argument(
        "--package-url",
        default=DEFAULT_PACKAGE_URL,
        help="写入 package.url",
    )
    return parser.parse_args()


def build_zip(src_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(src_dir)
                zf.write(path, arcname=rel.as_posix())


def sha256_file(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    args = parse_args()

    if not AVWIKI_SRC.exists():
        print(f"错误: 找不到目录 {AVWIKI_SRC}", file=sys.stderr)
        raise SystemExit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / ZIP_NAME
    manifest_path = OUTPUT_DIR / MANIFEST_NAME

    print(f"正在压缩: {AVWIKI_SRC} -> {zip_path}")
    build_zip(AVWIKI_SRC, zip_path)

    sha256 = sha256_file(zip_path)
    size = zip_path.stat().st_size

    manifest = {
        "app": "AVWiki",
        "latestVersion": args.version.strip(),
        "releaseNotes": args.release_notes.strip(),
        "package": {
            "url": args.package_url.strip(),
            "sha256": sha256,
            "size": size,
        },
    }

    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"sha256: {sha256}")
    print(f"size:   {size} bytes")
    print(f"已生成: {manifest_path}")


if __name__ == "__main__":
    main()
