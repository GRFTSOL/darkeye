"""utils.avwiki_updater：manifest 校验、覆盖更新与回滚。"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MOD_NAME = "utils.avwiki_updater"


def _load_module_with_stub_config(tmp_path: Path):
    config_stub = types.ModuleType("config")
    config_stub.AVWIKI_PATH = str(tmp_path / "resources" / "avwiki")
    config_stub.TEMP_PATH = tmp_path / "temp"
    config_stub.get_avwiki_latest_json_url = lambda: "https://example.test/avwiki/avwiki_latest.json"
    sys.modules["config"] = config_stub

    if "utils" not in sys.modules:
        utils_pkg = types.ModuleType("utils")
        utils_pkg.__path__ = [str(_ROOT / "utils")]
        sys.modules["utils"] = utils_pkg

    spec = importlib.util.spec_from_file_location(
        _MOD_NAME,
        _ROOT / "utils" / "avwiki_updater.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def _build_zip_bytes(file_map: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in file_map.items():
            zf.writestr(name, text)
    return buf.getvalue()


class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1):
        if size is None or size < 0:
            if self._offset >= len(self._payload):
                return b""
            data = self._payload[self._offset :]
            self._offset = len(self._payload)
            return data
        if self._offset >= len(self._payload):
            return b""
        end = min(self._offset + size, len(self._payload))
        data = self._payload[self._offset : end]
        self._offset = end
        return data


@pytest.fixture
def avwiki_mod(tmp_path):
    return _load_module_with_stub_config(tmp_path)


def test_parse_manifest_missing_fields(avwiki_mod):
    with pytest.raises(ValueError):
        avwiki_mod._parse_manifest({})

    with pytest.raises(ValueError):
        avwiki_mod._parse_manifest({"latestVersion": "1.0.0", "package": {"url": "x"}})


def test_check_and_update_hash_mismatch_does_not_replace(avwiki_mod, tmp_path):
    target = Path(avwiki_mod.AVWIKI_PATH)
    target.mkdir(parents=True, exist_ok=True)
    old_file = target / "旧.md"
    old_file.write_text("old", encoding="utf-8")

    zip_bytes = _build_zip_bytes({"新.md": "new"})
    manifest = {
        "latestVersion": "2026.04.07",
        "package": {
            "url": "https://example.test/avwiki/package.zip",
            "sha256": "deadbeef",
        },
    }

    def fake_urlopen(req, timeout=0):
        url = getattr(req, "full_url", req)
        if url.endswith("latest.json"):
            return _Resp(json.dumps(manifest).encode("utf-8"))
        return _Resp(zip_bytes)

    with patch.object(avwiki_mod, "urlopen", side_effect=fake_urlopen):
        result = avwiki_mod.check_and_update_avwiki()

    assert result.success is False
    assert old_file.read_text(encoding="utf-8") == "old"


def test_check_and_update_replace_success(avwiki_mod):
    target = Path(avwiki_mod.AVWIKI_PATH)
    target.mkdir(parents=True, exist_ok=True)
    (target / "旧.md").write_text("old", encoding="utf-8")

    zip_bytes = _build_zip_bytes(
        {
            "avwiki/作品.md": "# 新作品",
            "avwiki/女优.md": "# 新女优",
        }
    )
    sha = avwiki_mod.hashlib.sha256(zip_bytes).hexdigest()
    manifest = {
        "latestVersion": "2026.04.07",
        "releaseNotes": "更新词条",
        "package": {
            "url": "https://example.test/avwiki/package.zip",
            "sha256": sha,
        },
    }

    def fake_urlopen(req, timeout=0):
        url = getattr(req, "full_url", req)
        if url.endswith("latest.json"):
            return _Resp(json.dumps(manifest).encode("utf-8"))
        return _Resp(zip_bytes)

    with patch.object(avwiki_mod, "urlopen", side_effect=fake_urlopen):
        result = avwiki_mod.check_and_update_avwiki()

    assert result.success is True
    assert (target / "作品.md").exists()
    assert not (target / "旧.md").exists()


def test_check_and_update_rolls_back_on_replace_error(avwiki_mod, monkeypatch):
    target = Path(avwiki_mod.AVWIKI_PATH)
    target.mkdir(parents=True, exist_ok=True)
    old_file = target / "旧.md"
    old_file.write_text("old", encoding="utf-8")

    zip_bytes = _build_zip_bytes({"新.md": "new"})
    sha = avwiki_mod.hashlib.sha256(zip_bytes).hexdigest()
    manifest = {
        "latestVersion": "2026.04.07",
        "package": {
            "url": "https://example.test/avwiki/package.zip",
            "sha256": sha,
        },
    }

    def fake_urlopen(req, timeout=0):
        url = getattr(req, "full_url", req)
        if url.endswith("latest.json"):
            return _Resp(json.dumps(manifest).encode("utf-8"))
        return _Resp(zip_bytes)

    original_rename = Path.rename

    def flaky_rename(self, target_path):
        if "_incoming_" in self.name and Path(target_path).name == "avwiki":
            raise OSError("rename failed")
        return original_rename(self, target_path)

    monkeypatch.setattr(Path, "rename", flaky_rename)

    with patch.object(avwiki_mod, "urlopen", side_effect=fake_urlopen):
        result = avwiki_mod.check_and_update_avwiki()

    assert result.success is False
    assert old_file.exists()
    assert old_file.read_text(encoding="utf-8") == "old"
