"""merge_service：字段合并、genre 排除、runtime 与翻译路径。"""

import importlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_MERGE_SERVICE_MODULE = "core.crawler.merge_service"


def _get_merge_service():
    """加载 merge_service；必要时绕过 ``core/__init__``（避免拖入 Qt / 数据库）。"""
    if _MERGE_SERVICE_MODULE in sys.modules:
        return sys.modules[_MERGE_SERVICE_MODULE]

    core_mod = sys.modules.get("core")
    real_core = core_mod is not None and getattr(core_mod, "__file__", None)
    if real_core:
        return importlib.import_module(_MERGE_SERVICE_MODULE)

    sys.modules.setdefault("utils", types.ModuleType("utils"))
    if "utils.utils" not in sys.modules:
        uu = types.ModuleType("utils.utils")
        uu.translate_text_sync = lambda text, fallback="": text
        sys.modules["utils.utils"] = uu

    sys.modules.setdefault("config", types.ModuleType("config"))
    if not hasattr(sys.modules["config"], "resource_path"):

        def resource_path(relative_path):
            return str(_ROOT / relative_path)

        sys.modules["config"].resource_path = resource_path

    core_pkg = types.ModuleType("core")
    core_pkg.__path__ = [str(_ROOT / "core")]
    sys.modules["core"] = core_pkg
    sys.modules["core.schema"] = types.ModuleType("core.schema")

    mspec = importlib.util.spec_from_file_location(
        "core.schema.model",
        _ROOT / "core" / "schema" / "model.py",
    )
    model_mod = importlib.util.module_from_spec(mspec)
    sys.modules["core.schema.model"] = model_mod
    mspec.loader.exec_module(model_mod)

    cr_pkg = types.ModuleType("core.crawler")
    cr_pkg.__path__ = [str(_ROOT / "core" / "crawler")]
    sys.modules["core.crawler"] = cr_pkg

    msspec = importlib.util.spec_from_file_location(
        _MERGE_SERVICE_MODULE,
        _ROOT / "core" / "crawler" / "merge_service.py",
    )
    ms = importlib.util.module_from_spec(msspec)
    sys.modules[_MERGE_SERVICE_MODULE] = ms
    msspec.loader.exec_module(ms)
    return ms


merge_service = _get_merge_service()


@pytest.fixture(autouse=True)
def clear_exclude_genre_cache():
    merge_service._exclude_genre_cache = None
    yield
    merge_service._exclude_genre_cache = None


@patch("core.crawler.merge_service.resource_path")
def test_exclude_genre_set_loads_json(mock_resource_path, tmp_path):
    cfg = tmp_path / "exclude_genre.json"
    cfg.write_text(
        json.dumps({"exclude_genre": ["drop_me", "x"]}),
        encoding="utf-8",
    )
    mock_resource_path.return_value = str(cfg)

    s = merge_service.exclude_genre_set()
    assert s == frozenset({"drop_me", "x"})


@patch("core.crawler.merge_service.resource_path")
def test_exclude_genre_set_caches(mock_resource_path, tmp_path):
    cfg = tmp_path / "exclude_genre.json"
    cfg.write_text(json.dumps({"exclude_genre": ["a"]}), encoding="utf-8")
    mock_resource_path.return_value = str(cfg)

    merge_service.exclude_genre_set()
    merge_service.exclude_genre_set()
    assert mock_resource_path.call_count == 1


@patch("core.crawler.merge_service.resource_path", return_value="/nonexistent")
@patch("core.crawler.merge_service.logging")
def test_exclude_genre_set_missing_file_returns_empty(_log, _rp):
    s = merge_service.exclude_genre_set()
    assert s == frozenset()


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync", return_value="译名")
def test_merge_field_precedence(_tr, _eg):
    results = {
        "javlib": {
            "release_date": "javlib-date",
            "director": "d-lib",
            "length": "120",
            "image": "https://javlib/cover.jpg",
            "genre": ["JLibG"],
        },
        "avdanyuwiki": {
            "release_date": "avdan-date",
            "director": "d-avdan",
            "runtime": "90",
            "cover": "https://avdan/cover.jpg",
            "tag_list": ["WikiTag"],
            "maker": "mk-avdan",
            "series": "S-AV",
            "label": "lb-avdan",
            "actress_list": ["A1"],
            "actor_list": ["Actor1"],
        },
        "javdb": {
            "release_date": "db-date",
            "title": "DB Title",
            "genre": ["DBG"],
            "cover": "https://db/cover.jpg",
        },
        "javtxt": {"cn_title": "中文名", "jp_title": ""},
    }
    out = merge_service.merge_crawl_results(results, "ABC-123")

    assert out.serial_number == "ABC-123"
    # release_date：javlib 优先
    assert out.release_date == "javlib-date"
    # director：avdanyuwiki 优先
    assert out.director == "d-avdan"
    # runtime：来自 avdanyuwiki
    assert out.runtime == 90
    assert "WikiTag" in out.tag_list and "JLibG" in out.tag_list
    assert out.cn_title == "中文名"
    assert out.jp_title == "DB Title"
    assert out.maker == "mk-avdan"
    assert out.series == "S-AV"
    assert "https://javlib/cover.jpg" in out.cover_url_list
    assert "https://avdan/cover.jpg" in out.cover_url_list
    assert "https://fourhoi.com/abc-123/cover-n.jpg" in out.cover_url_list
    assert "https://db/cover.jpg" in out.cover_url_list


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync", return_value="译名")
def test_merge_series_fallback_when_avdan_blank(_tr, _eg):
    results = {
        "javlib": {},
        "avdanyuwiki": {"series": ""},
        "javdb": {"series": "FromDB"},
        "javtxt": {},
    }
    out = merge_service.merge_crawl_results(results, "X-001")
    assert out.series == "FromDB"


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync", return_value="译名")
def test_merge_series_fallback_when_avdan_dash(_tr, _eg):
    results = {
        "javlib": {},
        "avdanyuwiki": {"series": "----"},
        "javtxt": {"series": "FromTXT"},
        "javdb": {},
    }
    out = merge_service.merge_crawl_results(results, "X-002")
    assert out.series == "FromTXT"


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset({"bad"}))
@patch("core.crawler.merge_service.translate_text_sync", return_value="t")
def test_merge_genre_excludes_configured(_tr, _eg):
    results = {
        "javlib": {"genre": ["ok", "bad"]},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_service.merge_crawl_results(results, "Y-1")
    assert "ok" in out.tag_list
    assert "bad" not in out.tag_list


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync")
def test_merge_calls_translate_when_cn_title_empty(mock_tr, _eg):
    mock_tr.return_value = "翻译标题"
    results = {
        "javlib": {"title": "JP Only"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {"cn_title": ""},
    }
    out = merge_service.merge_crawl_results(results, "Z-9")
    mock_tr.assert_called()
    assert out.cn_title == "翻译标题"


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync", return_value="x")
def test_merge_runtime_invalid_becomes_zero(_tr, _eg):
    results = {
        "javlib": {"length": "not-int"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_service.merge_crawl_results(results, "R-1")
    assert out.runtime == 0


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync", return_value="x")
def test_merge_runtime_from_javlib_length_when_no_avdan_runtime(_tr, _eg):
    results = {
        "javlib": {"length": "88"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_service.merge_crawl_results(results, "R-2")
    assert out.runtime == 88


@patch("core.crawler.merge_service.exclude_genre_set", return_value=frozenset())
@patch("core.crawler.merge_service.translate_text_sync", return_value="x")
def test_merge_cover_list_image_as_list(_tr, _eg):
    results = {
        "javlib": {"image": ["https://a.jpg", "https://b.jpg"]},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_service.merge_crawl_results(results, "C-1")
    assert "https://a.jpg" in out.cover_url_list
    assert "https://b.jpg" in out.cover_url_list
