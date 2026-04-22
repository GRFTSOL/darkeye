import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urljoin
import xml.etree.ElementTree as ET

import requests

from core.database.webdav_credential_store import WebDavCredentials


@dataclass(frozen=True)
class WebDavConfig:
    base_url: str
    remote_root: str
    timeout_seconds: int = 20


@dataclass(frozen=True)
class WebDavResult:
    ok: bool
    error_code: str = ""
    message: str = ""


def _normalized_remote_path(remote_path: str) -> str:
    val = (remote_path or "").replace("\\", "/").strip()
    return "/" + val.strip("/")


def _build_url(config: WebDavConfig, remote_path: str) -> str:
    root = _normalized_remote_path(config.remote_root)
    path = _normalized_remote_path(remote_path)
    if path == root or path.startswith(f"{root.rstrip('/')}/"):
        merged = path
    else:
        merged = f"{root.rstrip('/')}/{path.lstrip('/')}"
    encoded = quote(merged, safe="/-_.~")
    return urljoin(config.base_url.rstrip("/") + "/", encoded.lstrip("/"))


def _status_to_error(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "auth_failed",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        423: "locked",
        507: "insufficient_storage",
    }.get(status_code, f"http_{status_code}")


class WebDavBackupClient:
    def __init__(self, config: WebDavConfig, credentials: WebDavCredentials):
        self.config = config
        self.credentials = credentials
        self._session = requests.Session()
        self._session.auth = (credentials.username, credentials.password)

    def test_connection(self) -> WebDavResult:
        url = _build_url(self.config, "/")
        try:
            response = self._session.request(
                "PROPFIND",
                url,
                timeout=self.config.timeout_seconds,
                headers={"Depth": "0"},
            )
            if response.status_code in (200, 207):
                return WebDavResult(ok=True)
            return WebDavResult(
                ok=False,
                error_code=_status_to_error(response.status_code),
                message=f"连接失败，HTTP {response.status_code}",
            )
        except requests.RequestException as e:
            return WebDavResult(ok=False, error_code="network_error", message=str(e))

    def ensure_directory(self, remote_dir: str) -> WebDavResult:
        normalized = _normalized_remote_path(remote_dir)
        current = ""
        for piece in [p for p in normalized.split("/") if p]:
            current = f"{current}/{piece}"
            check = self._propfind(current)
            if check.status_code in (200, 207):
                continue
            if check.status_code not in (404,):
                return WebDavResult(
                    ok=False,
                    error_code=_status_to_error(check.status_code),
                    message=f"检查目录失败: {current}",
                )
            mk = self._mkcol(current)
            if mk.status_code not in (201, 301, 405):
                return WebDavResult(
                    ok=False,
                    error_code=_status_to_error(mk.status_code),
                    message=f"创建目录失败: {current}",
                )
        return WebDavResult(ok=True)

    def upload_file(self, local_path: Path, remote_path: str) -> WebDavResult:
        local_file = Path(local_path)
        if not local_file.is_file():
            return WebDavResult(
                ok=False, error_code="local_file_missing", message=str(local_file)
            )
        parent_dir = str(Path(_normalized_remote_path(remote_path)).parent)
        ensure = self.ensure_directory(parent_dir)
        if not ensure.ok:
            return ensure
        url = _build_url(self.config, remote_path)
        try:
            with local_file.open("rb") as f:
                response = self._session.put(
                    url, data=f, timeout=self.config.timeout_seconds
                )
            if response.status_code in (200, 201, 204):
                return WebDavResult(ok=True)
            return WebDavResult(
                ok=False,
                error_code=_status_to_error(response.status_code),
                message=f"上传失败，HTTP {response.status_code}",
            )
        except requests.RequestException as e:
            return WebDavResult(ok=False, error_code="network_error", message=str(e))

    def download_file(self, remote_path: str, local_path: Path) -> WebDavResult:
        local_file = Path(local_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)
        url = _build_url(self.config, remote_path)
        try:
            response = self._session.get(url, timeout=self.config.timeout_seconds)
            if response.status_code != 200:
                return WebDavResult(
                    ok=False,
                    error_code=_status_to_error(response.status_code),
                    message=f"下载失败，HTTP {response.status_code}",
                )
            with local_file.open("wb") as f:
                f.write(response.content)
            return WebDavResult(ok=True)
        except requests.RequestException as e:
            return WebDavResult(ok=False, error_code="network_error", message=str(e))

    def list_backups(self, remote_dir: str) -> tuple[WebDavResult, list[str]]:
        response = self._propfind(remote_dir, depth="1")
        if response.status_code not in (200, 207):
            return (
                WebDavResult(
                    ok=False,
                    error_code=_status_to_error(response.status_code),
                    message=f"列举失败，HTTP {response.status_code}",
                ),
                [],
            )
        try:
            root = ET.fromstring(response.text)
            ns = {"d": "DAV:"}
            hrefs = []
            for node in root.findall(".//d:response/d:href", ns):
                href = (node.text or "").strip()
                if not href:
                    continue
                hrefs.append(href)
            return WebDavResult(ok=True), sorted(set(hrefs))
        except ET.ParseError as e:
            return WebDavResult(ok=False, error_code="parse_error", message=str(e)), []

    def _propfind(self, remote_path: str, depth: str = "0") -> requests.Response:
        url = _build_url(self.config, remote_path)
        return self._session.request(
            "PROPFIND",
            url,
            timeout=self.config.timeout_seconds,
            headers={"Depth": depth},
        )

    def _mkcol(self, remote_path: str) -> requests.Response:
        url = _build_url(self.config, remote_path)
        return self._session.request("MKCOL", url, timeout=self.config.timeout_seconds)


def build_webdav_client(
    base_url: str,
    remote_root: str,
    timeout_seconds: int,
    credentials: WebDavCredentials,
) -> WebDavBackupClient:
    config = WebDavConfig(
        base_url=(base_url or "").strip(),
        remote_root=(remote_root or "").strip() or "/darkeye",
        timeout_seconds=max(3, int(timeout_seconds)),
    )
    if not config.base_url:
        logging.warning("[webdav] base_url 为空")
    return WebDavBackupClient(config=config, credentials=credentials)
