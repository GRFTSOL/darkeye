#!/usr/bin/env python3
# 把编译的文件打包压缩改名，计算 sha256 和大小，然后生成新的 update/latest.json（含 releaseNotes）
# 编译后的文件在dist/main.dist中

import hashlib
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import zstandard as zstd

# 项目根目录（脚本在 scripts/ 下）
ROOT = Path(__file__).resolve().parent.parent
DIST_SRC = ROOT / "dist" / "main.dist"
DIST_DIR = ROOT / "dist"
LATEST_JSON = ROOT / "update" / "latest.json"
APP_NAME = "DarkEye"


def get_version() -> str:
    """从项目根目录 config.py 的 APP_VERSION 读取"""
    config_py = ROOT / "config.py"
    if config_py.exists():
        for line in config_py.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("APP_VERSION") and "=" in s:
                for q in ('"', "'"):
                    if q in line:
                        start = line.find(q) + 1
                        end = line.find(q, start)
                        if end > start:
                            return line[start:end].strip()
    return "1.0.0"


PACKAGE_URL_TEMPLATE = "http://yinruizhe.asia/DarkEye-v{version}.tar.zst"

# 每次发版在此填写更新说明（会写入 latest.json 的 releaseNotes）
RELEASE_NOTES = (
    "mdcz的nfo导入，爬虫的优化，包括其他各种更新详见github，现在浏览器插件放在extensions中，需要手动更新，可以不用去github上下载了"
)


def main():
    version = get_version()
    pkg_name = f"{APP_NAME}-v{version}.tar.zst"
    pkg_path = DIST_DIR / pkg_name

    if not DIST_SRC.exists():
        print(f"错误: 编译目录不存在: {DIST_SRC}", file=sys.stderr)
        print("请先运行 build-nuitka.ps1 完成编译", file=sys.stderr)
        sys.exit(1)

    # 1. 打包为 tar，再用 zstd 压缩
    print(f"正在打包 {DIST_SRC} -> {pkg_path} ...")
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        tar.add(DIST_SRC, arcname="main.dist")
    tar_buffer.seek(0)
    total = tar_buffer.getbuffer().nbytes

    def _progress_bar(done: int, total: int, prefix: str = "", width: int = 40) -> None:
        pct = done / total if total else 0
        filled = int(width * pct)
        bar = "=" * filled + "-" * (width - filled)
        sys.stderr.write(
            f"\r{prefix} |{bar}| {pct*100:.1f}% ({done//1024//1024}MB/{total//1024//1024}MB)"
        )
        sys.stderr.flush()

    cctx = zstd.ZstdCompressor(level=22)
    chunk_size = 1024 * 1024  # 1MB
    written = 0
    with open(pkg_path, "wb") as f:
        with cctx.stream_writer(f) as compressor:
            while chunk := tar_buffer.read(chunk_size):
                compressor.write(chunk)
                written += len(chunk)
                _progress_bar(written, total, "压缩")
    print(file=sys.stderr)

    # 2. 计算 sha256 和大小
    print("计算 sha256 ...")
    h = hashlib.sha256()
    with open(pkg_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    sha256 = h.hexdigest()
    size = pkg_path.stat().st_size
    print(f"  sha256: {sha256}")
    print(f"  size:   {size} bytes")

    # 3. 生成新的 update/latest.json（不读取旧文件）
    package_url = PACKAGE_URL_TEMPLATE.format(version=version)
    data = {
        "app": APP_NAME,
        "latestVersion": version,
        "releaseNotes": RELEASE_NOTES,
        "package": {
            "url": package_url,
            "sha256": sha256,
            "size": size,
        },
    }

    LATEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    LATEST_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已生成 {LATEST_JSON}")

    # 4. 额外生成 zip：归档内根目录名为 {APP_NAME}-v{version}（非 main.dist）
    zip_name = f"{APP_NAME}-v{version}.zip"
    zip_path = DIST_DIR / zip_name
    arc_root = f"{APP_NAME}-v{version}"
    print(f"正在打包 zip {DIST_SRC} -> {zip_path} ...")
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for path in DIST_SRC.rglob("*"):
            if path.is_file():
                rel = path.relative_to(DIST_SRC)
                zf.write(path, arcname=f"{arc_root}/{rel.as_posix()}")

    print(f"\n完成: {pkg_path}\n      {zip_path}")


if __name__ == "__main__":
    main()
