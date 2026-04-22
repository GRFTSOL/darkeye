from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging
import zipfile
from urllib.parse import unquote, urlparse

from config import (
    DATABASE,
    DATABASE_BACKUP_PATH,
    PRIVATE_DATABASE,
    PRIVATE_DATABASE_BACKUP_PATH,
    TEMP_PATH,
    get_webdav_auto_upload_on_backup,
    get_webdav_base_url,
    get_webdav_enabled,
    get_webdav_profile_name,
    get_webdav_remote_root,
    get_webdav_timeout_seconds,
)
from core.database.backup_utils import (
    backup_database,
    create_resource_snapshot,
    restore_backup_safely,
    restore_snapshot,
)
from core.database.webdav_backup_client import build_webdav_client, WebDavResult
from core.database.webdav_credential_store import load_credentials


@dataclass(frozen=True)
class BackupActionResult:
    ok: bool
    message: str
    local_path: Path | None = None
    remote_path: str = ""


def _today_parts() -> tuple[str, str]:
    now = datetime.now()
    return now.strftime("%Y"), now.strftime("%m")


def _build_remote_file_path(
    profile: str, db_scope: str, backup_type: str, file_name: str
) -> str:
    _ = (profile, db_scope, backup_type)
    root = get_webdav_remote_root().rstrip("/")
    return f"{root}/{file_name}"


def _build_client_or_error() -> tuple[object | None, BackupActionResult | None]:
    if not get_webdav_enabled():
        return None, BackupActionResult(ok=False, message="WebDAV 云备份未启用。")
    creds = load_credentials(get_webdav_profile_name())
    if creds is None:
        return None, BackupActionResult(
            ok=False, message="未找到 WebDAV 凭据，请先保存凭据。"
        )
    client = build_webdav_client(
        base_url=get_webdav_base_url(),
        remote_root=get_webdav_remote_root(),
        timeout_seconds=get_webdav_timeout_seconds(),
        credentials=creds,
    )
    return client, None


def test_webdav_connection() -> BackupActionResult:
    client, error = _build_client_or_error()
    if error is not None:
        return error
    result: WebDavResult = client.test_connection()
    if result.ok or result.error_code == "not_found":
        root_dir = get_webdav_remote_root()
        ensure_result: WebDavResult = client.ensure_directory(root_dir)
        if ensure_result.ok:
            return BackupActionResult(
                ok=True, message=f"WebDAV 连接成功，远端根目录已就绪：{root_dir}"
            )
        return BackupActionResult(
            ok=False,
            message=(
                "WebDAV 连接成功，但根目录创建失败："
                f"{ensure_result.error_code or ensure_result.message}"
            ),
        )
    return BackupActionResult(
        ok=False,
        message=f"WebDAV 连接失败：{result.error_code or result.message}",
    )


def backup_public_simple_and_optional_upload(
    local_backup_dir: Path | None = None,
    force_upload: bool = False,
) -> BackupActionResult:
    backup_dir = Path(local_backup_dir or DATABASE_BACKUP_PATH)
    local_path = Path(backup_database(DATABASE, backup_dir, "darkeye-public"))
    if not (force_upload or get_webdav_auto_upload_on_backup()):
        return BackupActionResult(
            ok=True, message="本地备份成功。", local_path=local_path
        )
    return upload_local_backup_file(local_path, db_scope="public", backup_type="simple")


def backup_private_and_optional_upload(
    local_backup_dir: Path | None = None,
    force_upload: bool = False,
) -> BackupActionResult:
    backup_dir = Path(local_backup_dir or PRIVATE_DATABASE_BACKUP_PATH)
    local_path = Path(backup_database(PRIVATE_DATABASE, backup_dir, "darkeye-private"))
    if not (force_upload or get_webdav_auto_upload_on_backup()):
        return BackupActionResult(
            ok=True, message="本地备份成功。", local_path=local_path
        )
    return upload_local_backup_file(
        local_path, db_scope="private", backup_type="simple"
    )


def backup_public_snapshot_and_optional_upload(
    snapshot_root: Path | None = None,
    force_upload: bool = False,
) -> BackupActionResult:
    root = Path(snapshot_root or DATABASE_BACKUP_PATH)
    snapshot_dir = create_resource_snapshot(root)
    if snapshot_dir is None:
        return BackupActionResult(ok=False, message="创建本地快照失败。")
    archive_path = _zip_snapshot_dir(Path(snapshot_dir))
    if not (force_upload or get_webdav_auto_upload_on_backup()):
        return BackupActionResult(
            ok=True, message="本地快照成功。", local_path=archive_path
        )
    return upload_local_backup_file(
        archive_path, db_scope="public", backup_type="snapshot"
    )


def upload_local_backup_file(
    local_path: Path,
    db_scope: str,
    backup_type: str,
) -> BackupActionResult:
    client, error = _build_client_or_error()
    if error is not None:
        return error
    profile = get_webdav_profile_name()
    remote_path = _build_remote_file_path(
        profile=profile,
        db_scope=db_scope,
        backup_type=backup_type,
        file_name=local_path.name,
    )
    result: WebDavResult = client.upload_file(local_path, remote_path)
    if not result.ok:
        return BackupActionResult(
            ok=False,
            message=f"上传失败：{result.error_code or result.message}",
            local_path=local_path,
            remote_path=remote_path,
        )
    return BackupActionResult(
        ok=True,
        message="本地备份成功并已上传云端。",
        local_path=local_path,
        remote_path=remote_path,
    )


def list_webdav_backups(
    db_scope: str = "public",
    backup_type: str = "simple",
) -> tuple[BackupActionResult, list[str]]:
    _ = (db_scope, backup_type)
    client, error = _build_client_or_error()
    if error is not None:
        return error, []
    remote_base = get_webdav_remote_root().rstrip("/")
    list_result, entries = client.list_backups(remote_base)
    if not list_result.ok:
        return (
            BackupActionResult(
                ok=False, message=f"列举备份失败：{list_result.error_code or list_result.message}"
            ),
            [],
        )
    base_dir = remote_base.rstrip("/")
    filtered: list[str] = []
    for entry in entries:
        normalized = _normalize_webdav_entry(entry)
        if not normalized:
            continue
        rel = _relative_to_remote_base(normalized, base_dir)
        if rel is None:
            continue
        if not rel or "/" in rel:
            continue
        if rel.endswith(".meta.json"):
            continue
        filtered.append(f"{base_dir}/{rel}")
    filtered = sorted(set(filtered))
    return BackupActionResult(ok=True, message=f"列举成功，共 {len(filtered)} 条。"), filtered


def restore_from_webdav_object(
    remote_path: str,
    db_scope: str = "public",
    backup_type: str = "simple",
) -> BackupActionResult:
    client, error = _build_client_or_error()
    if error is not None:
        return error
    temp_root = Path(TEMP_PATH) / "webdav_restore"
    temp_root.mkdir(parents=True, exist_ok=True)
    local_path = temp_root / Path(remote_path).name
    download_result = client.download_file(remote_path, local_path)
    if not download_result.ok:
        return BackupActionResult(
            ok=False,
            message=f"下载备份失败：{download_result.error_code or download_result.message}",
            remote_path=remote_path,
        )
    if backup_type == "snapshot":
        meta_path = _extract_snapshot_archive(local_path, temp_root)
        if meta_path is None:
            return BackupActionResult(ok=False, message="快照文件解压失败。")
        ok = restore_snapshot(meta_path)
    else:
        target = DATABASE if db_scope == "public" else PRIVATE_DATABASE
        ok = restore_backup_safely(local_path, target)
    return BackupActionResult(ok=ok, message="恢复成功。" if ok else "恢复失败。")


def _zip_snapshot_dir(snapshot_dir: Path) -> Path:
    zip_path = snapshot_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in snapshot_dir.rglob("*"):
            if file.is_file():
                archive.write(file, arcname=file.relative_to(snapshot_dir))
    return zip_path


def _extract_snapshot_archive(archive_path: Path, extract_root: Path) -> Path | None:
    target_dir = extract_root / archive_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(target_dir)
    except (OSError, zipfile.BadZipFile):
        logging.exception("[webdav] 解压快照失败")
        return None
    meta_candidates = sorted(target_dir.rglob("meta.json"))
    return meta_candidates[0] if meta_candidates else None


def _normalize_webdav_entry(entry: str) -> str:
    val = (entry or "").strip()
    if not val:
        return ""
    if "://" in val:
        parsed = urlparse(val)
        val = parsed.path or ""
    val = unquote(val).replace("\\", "/").strip()
    if not val.startswith("/"):
        val = "/" + val
    if val != "/" and val.endswith("//"):
        val = val.rstrip("/")
    return val


def _relative_to_remote_base(path: str, base_dir: str) -> str | None:
    """将 WebDAV 返回路径归一到 remote_root 下的相对路径。"""
    normalized_path = path.rstrip("/")
    normalized_base = base_dir.rstrip("/")
    if normalized_path == normalized_base:
        return ""
    prefix = f"{normalized_base}/"
    if normalized_path.startswith(prefix):
        return normalized_path[len(prefix) :].strip("/")
    idx = normalized_path.find(prefix)
    if idx >= 0:
        return normalized_path[idx + len(prefix) :].strip("/")
    return None
