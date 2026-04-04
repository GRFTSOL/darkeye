"""utils.updater：版本解析、新旧比较、check_for_updates 网络桩。"""

import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_UPDATER = "utils.updater"


def _get_updater_module():
    if _UPDATER in sys.modules:
        return sys.modules[_UPDATER]

    cfg_mod = sys.modules.get("config")
    real_config = cfg_mod is not None and getattr(cfg_mod, "__file__", None)
    if real_config:
        return importlib.import_module(_UPDATER)

    stub = types.ModuleType("config")
    stub.get_latest_json_url = lambda: "https://example.test/app/latest.json"
    sys.modules["config"] = stub

    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = [str(_ROOT / "utils")]
    sys.modules["utils"] = utils_pkg

    spec = importlib.util.spec_from_file_location(
        _UPDATER,
        _ROOT / "utils" / "updater.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_UPDATER] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def updater_mod():
    return _get_updater_module()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("V0.10.0", (0, 10, 0)),
        ("2.0", (2, 0)),
    ],
)
def test_parse_version_tuple_ok(updater_mod, raw, expected):
    assert updater_mod._parse_version_tuple(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "1.a.2"],
)
def test_parse_version_tuple_bad(updater_mod, raw):
    assert updater_mod._parse_version_tuple(raw) is None


@pytest.mark.parametrize(
    "remote, local, want_newer",
    [
        ("1.2.1", "1.2.0", True),
        ("1.2.0", "1.2.0", False),
        ("1.1.9", "1.2.0", False),
        ("2.0.0", "1.9.9", True),
    ],
)
def test_is_newer_version_semantic(updater_mod, remote, local, want_newer):
    assert updater_mod._is_newer_version(remote, local) is want_newer


def test_is_newer_version_unparseable_falls_back_to_string_inequality(updater_mod):
    assert updater_mod._is_newer_version("alpha", "beta") is True
    assert updater_mod._is_newer_version("same", "same") is False


def test_check_for_updates_no_update(updater_mod):
    payload = {
        "latestVersion": "1.0.0",
        "releaseNotes": "",
        "package": {"url": "https://dl/x.zip"},
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    with patch.object(updater_mod, "urlopen", return_value=_Resp()):
        r = updater_mod.check_for_updates(
            "1.0.0",
            latest_json_url="https://example/l.json",
        )

    assert r.success is True
    assert r.is_update_available is False
    assert r.latest_version == "1.0.0"
    assert r.package_url == "https://dl/x.zip"


def test_check_for_updates_has_update(updater_mod):
    payload = {
        "latestVersion": "2.0.0",
        "releaseNotes": "fix",
        "package": {"url": "https://dl/y.zip"},
    }

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    with patch.object(updater_mod, "urlopen", return_value=_Resp()):
        r = updater_mod.check_for_updates(
            "1.0.0",
            latest_json_url="https://example/l.json",
        )

    assert r.success is True
    assert r.is_update_available is True
    assert r.latest_version == "2.0.0"
    assert "2.0.0" in r.message
    assert r.release_notes == "fix"


def test_check_for_updates_missing_latest_version(updater_mod):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({}).encode("utf-8")

    with patch.object(updater_mod, "urlopen", return_value=_Resp()):
        r = updater_mod.check_for_updates(
            "1.0.0",
            latest_json_url="https://example/l.json",
        )

    assert r.success is False
    assert "latestVersion" in r.message


def test_check_for_updates_network_error(updater_mod):
    with patch.object(
        updater_mod,
        "urlopen",
        side_effect=OSError("no network"),
    ):
        r = updater_mod.check_for_updates(
            "1.0.0",
            latest_json_url="https://example/l.json",
        )

    assert r.success is False
    assert r.title == "更新检查失败"
