from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import get_latest_json_url

DEFAULT_LATEST_JSON_URL = get_latest_json_url()

# Cloudflare 等常对自定义/脚本类 UA 单独处置；与 core/crawler/download.py 一致使用常见
# 桌面 Chrome 串，末尾保留 DarkEye 便于自建日志区分。
DEFAULT_UPDATE_CHECK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36 DarkEye-Updater/1.0"
)


@dataclass(frozen=True)
class UpdateCheckResult:
    success: bool
    title: str
    message: str
    is_update_available: bool = False
    latest_version: str = ""
    release_notes: str = ""
    package_url: str = ""


def _parse_version_tuple(v: str) -> Optional[tuple[int, ...]]:
    """把 '1.1.2' 解析为 (1,1,2)。解析失败返回 None。"""
    if not v:
        return None
    try:
        v = str(v).strip()
        if v.startswith(("v", "V")):
            v = v[1:]
        parts = [p.strip() for p in v.split(".") if p.strip() != ""]
        parsed: list[int] = []
        for p in parts:
            parsed.append(int(p))
        return tuple(parsed)
    except Exception as e:
        logging.debug(
            "版本号解析失败 version=%r: %s",
            v,
            e,
            exc_info=True,
        )
        return None


def _is_newer_version(remote_version: str, local_version: str) -> bool:
    remote_t = _parse_version_tuple(remote_version)
    local_t = _parse_version_tuple(local_version)
    if remote_t is None or local_t is None:
        # 兜底：无法解析版本就按“字符串不等则认为需要更新”
        return (remote_version or "").strip() != (local_version or "").strip()
    return remote_t > local_t


def check_for_updates(
    local_version: str,
    latest_json_url: str = DEFAULT_LATEST_JSON_URL,
    *,
    urlopen_timeout_seconds: int = 8,
    urlopen_max_attempts: int = 3,
    user_agent: str = DEFAULT_UPDATE_CHECK_USER_AGENT,
    log_latest_json: bool = False,
) -> UpdateCheckResult:
    """
    检查远端 latest.json，返回更新判断结果（不做实际下载安装）。

    对短暂断连（如 Connection reset）会做有限次重试；HTTP 4xx/5xx 不重试。
    """
    result_title = "更新检查结果"
    attempts = max(1, int(urlopen_max_attempts))
    try:
        raw: bytes | None = None
        for attempt in range(attempts):
            try:
                req = Request(
                    latest_json_url,
                    headers={
                        "User-Agent": user_agent,
                        "Accept": "application/json, text/plain, */*",
                    },
                )
                with urlopen(req, timeout=urlopen_timeout_seconds) as resp:
                    raw = resp.read()
                break
            except HTTPError:
                raise
            except (URLError, TimeoutError):
                if attempt + 1 >= attempts:
                    raise
                # 指数退避，减轻对端与本地网络瞬时故障的影响
                time.sleep(0.35 * (2**attempt))
        assert raw is not None

        data = json.loads(raw.decode("utf-8", errors="replace"))

        if log_latest_json:
            # 直接打印远端 latest.json 内容，便于排查字段缺失/命名不一致
            try:
                logging.info(
                    "latest.json 数据: %s", json.dumps(data, ensure_ascii=False)
                )
            except Exception:
                logging.info("latest.json 数据(非json序列化): %r", data)

        latest_version = str(data.get("latestVersion", "")).strip()
        release_notes = str(data.get("releaseNotes", "")).strip()
        pkg_url = str((data.get("package") or {}).get("url", "")).strip()

        if not latest_version:
            return UpdateCheckResult(
                success=False,
                title=result_title,
                message="latest.json 缺少 latestVersion 字段。",
            )

        if not _is_newer_version(latest_version, local_version):
            msg = f"当前已是最新版本：{local_version}。"
            return UpdateCheckResult(
                success=True,
                title=result_title,
                message=msg,
                is_update_available=False,
                latest_version=latest_version,
                release_notes=release_notes,
                package_url=pkg_url,
            )

        # 需要更新
        lines = [f"检测到新版本：{local_version} -> {latest_version}"]
        if release_notes:
            lines.append(f"更新内容：{release_notes}")
        msg = "\n".join(lines)

        return UpdateCheckResult(
            success=True,
            title=result_title,
            message=msg,
            is_update_available=True,
            latest_version=latest_version,
            release_notes=release_notes,
            package_url=pkg_url,
        )
    except Exception as e:
        logging.exception("更新检查失败")
        return UpdateCheckResult(
            success=False,
            title="更新检查失败",
            message=f"无法获取最新版本信息：{e}",
        )
