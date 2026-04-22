import json
from dataclasses import dataclass

import keyring


@dataclass(frozen=True)
class WebDavCredentials:
    username: str
    password: str


def _service_name(profile: str) -> str:
    profile_name = (profile or "default").strip() or "default"
    return f"darkeye/webdav/{profile_name}"


def save_credentials(profile: str, username: str, password: str) -> None:
    payload = {
        "username": (username or "").strip(),
        "password": password or "",
    }
    keyring.set_password(_service_name(profile), "credentials", json.dumps(payload))


def load_credentials(profile: str) -> WebDavCredentials | None:
    raw = keyring.get_password(_service_name(profile), "credentials")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        return None
    return WebDavCredentials(username=username, password=password)


def has_credentials(profile: str) -> bool:
    return load_credentials(profile) is not None


def clear_credentials(profile: str) -> None:
    try:
        keyring.delete_password(_service_name(profile), "credentials")
    except keyring.errors.PasswordDeleteError:
        return
