from __future__ import annotations

import hashlib
import json
import logging
import time
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from config import AVWIKI_PATH, TEMP_PATH, get_avwiki_latest_json_url


@dataclass(frozen=True)
class AvwikiUpdateResult:
    success: bool
    title: str
    message: str
    latest_version: str = ""
    release_notes: str = ""


def _sha256_file(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _download_bytes(
    url: str,
    *,
    timeout_seconds: int,
    user_agent: str,
) -> bytes:
    req = Request(url, headers={"User-Agent": user_agent})
    with urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read()


def _download_to_file(
    url: str,
    file_path: Path,
    *,
    timeout_seconds: int,
    user_agent: str,
    chunk_size: int = 1024 * 1024,
) -> None:
    req = Request(url, headers={"User-Agent": user_agent})
    with urlopen(req, timeout=timeout_seconds) as resp:
        with file_path.open("wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)


def _with_retry(func, *, retries: int = 3, sleep_seconds: float = 1.0):
    last_error = None
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if i < retries - 1:
                time.sleep(sleep_seconds * (i + 1))
    raise last_error


def _parse_manifest(data: dict) -> tuple[str, str, str, str]:
    latest_version = str(data.get("latestVersion", "")).strip()
    release_notes = str(data.get("releaseNotes", "")).strip()
    package = data.get("package") or {}
    package_url = str(package.get("url", "")).strip()
    package_sha256 = str(package.get("sha256", "")).strip().lower()

    if not latest_version:
        raise ValueError("manifest 缺少 latestVersion 字段")
    if not package_url:
        raise ValueError("manifest 缺少 package.url 字段")
    if not package_sha256:
        raise ValueError("manifest 缺少 package.sha256 字段")

    return latest_version, release_notes, package_url, package_sha256


def _find_extract_content_root(extract_dir: Path) -> Path:
    if any(extract_dir.glob("*.md")):
        return extract_dir
    children = [p for p in extract_dir.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_dir


def check_and_update_avwiki(
    latest_json_url: str | None = None,
    *,
    urlopen_timeout_seconds: int = 30,
    user_agent: str = "DarkEye-AVWiki-Updater/1.0",
) -> AvwikiUpdateResult:
    """
    拉取远端 avwiki manifest，下载并校验 zip 后覆盖 AVWIKI_PATH。
    """
    title = "AVWiki 更新"
    latest_url = (latest_json_url or "").strip() or get_avwiki_latest_json_url()
    if not latest_url:
        return AvwikiUpdateResult(False, title, "未配置 AVWiki 更新地址。")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{stamp}_{uuid.uuid4().hex[:8]}"
    run_dir = Path(TEMP_PATH) / "avwiki_update" / run_id
    zip_path = run_dir / "avwiki.zip"
    extract_dir = run_dir / "extract"

    target = Path(AVWIKI_PATH)
    parent = target.parent
    backup_dir = parent / f"{target.name}_backup_{run_id}"
    staging_dir = parent / f"{target.name}_incoming_{run_id}"

    old_exists = target.exists()
    moved_old = False
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        extract_dir.mkdir(parents=True, exist_ok=True)

        manifest_raw = _with_retry(
            lambda: _download_bytes(
                latest_url,
                timeout_seconds=urlopen_timeout_seconds,
                user_agent=user_agent,
            )
        )
        manifest = json.loads(manifest_raw.decode("utf-8", errors="replace"))
        latest_version, release_notes, package_url, package_sha256 = _parse_manifest(
            manifest
        )

        _with_retry(
            lambda: _download_to_file(
                package_url,
                zip_path,
                timeout_seconds=urlopen_timeout_seconds,
                user_agent=user_agent,
            )
        )

        actual_sha256 = _sha256_file(zip_path).lower()
        if actual_sha256 != package_sha256:
            return AvwikiUpdateResult(
                False,
                title,
                "资源包校验失败：sha256 不匹配，已终止覆盖。",
                latest_version=latest_version,
                release_notes=release_notes,
            )

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        content_root = _find_extract_content_root(extract_dir)
        md_files = list(content_root.rglob("*.md"))
        if not md_files:
            return AvwikiUpdateResult(
                False,
                title,
                "解压内容无 Markdown 文件，已终止覆盖。",
                latest_version=latest_version,
                release_notes=release_notes,
            )

        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        shutil.copytree(content_root, staging_dir)

        if old_exists:
            target.rename(backup_dir)
            moved_old = True

        staging_dir.rename(target)

        shutil.rmtree(run_dir, ignore_errors=True)
        if moved_old:
            shutil.rmtree(backup_dir, ignore_errors=True)

        lines = [f"更新完成，版本：{latest_version}"]
        if release_notes:
            lines.append(f"更新说明：{release_notes}")
        return AvwikiUpdateResult(
            True,
            title,
            "\n".join(lines),
            latest_version=latest_version,
            release_notes=release_notes,
        )
    except Exception as e:
        logging.exception("AVWiki 更新失败")
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        if moved_old and not target.exists() and backup_dir.exists():
            try:
                backup_dir.rename(target)
            except Exception:
                logging.exception("AVWiki 更新回滚失败")
        return AvwikiUpdateResult(
            False,
            title,
            f"更新失败：{e}\n建议检查网络连通性，稍后重试。",
        )
