"""merge_service.crawled_work_from_extension_payload；多源合并见 ``tests/support/merge_crawl_legacy``。"""

import importlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.support.merge_crawl_legacy import exclude_genre_set, merge_crawl_results

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

    utils_pkg = sys.modules.setdefault("utils", types.ModuleType("utils"))
    utils_pkg.__path__ = [str(_ROOT / "utils")]
    if "utils.utils" not in sys.modules:
        uu = types.ModuleType("utils.utils")
        uu.translate_text_sync = lambda text, fallback="": text
        sys.modules["utils.utils"] = uu

    cfg = sys.modules.setdefault("config", types.ModuleType("config"))
    if not hasattr(cfg, "resource_path"):

        def resource_path(relative_path):
            return str(_ROOT / relative_path)

        cfg.resource_path = resource_path
    if not hasattr(cfg, "get_translation_engine"):
        cfg.get_translation_engine = lambda: ""

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
    from tests.support import merge_crawl_legacy

    merge_crawl_legacy._exclude_genre_cache = None
    yield
    merge_crawl_legacy._exclude_genre_cache = None


@patch("tests.support.merge_crawl_legacy.resource_path")
def test_exclude_genre_set_loads_json(mock_resource_path, tmp_path):
    cfg = tmp_path / "exclude_genre.json"
    cfg.write_text(
        json.dumps({"exclude_genre": ["drop_me", "x"]}),
        encoding="utf-8",
    )
    mock_resource_path.return_value = str(cfg)

    s = exclude_genre_set()
    assert s == frozenset({"drop_me", "x"})


@patch("tests.support.merge_crawl_legacy.resource_path")
def test_exclude_genre_set_caches(mock_resource_path, tmp_path):
    cfg = tmp_path / "exclude_genre.json"
    cfg.write_text(json.dumps({"exclude_genre": ["a"]}), encoding="utf-8")
    mock_resource_path.return_value = str(cfg)

    exclude_genre_set()
    exclude_genre_set()
    assert mock_resource_path.call_count == 1


@patch("tests.support.merge_crawl_legacy.resource_path", return_value="/nonexistent")
@patch("tests.support.merge_crawl_legacy.logging")
def test_exclude_genre_set_missing_file_returns_empty(_log, _rp):
    s = exclude_genre_set()
    assert s == frozenset()


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_field_precedence(_eg):
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
    out = merge_crawl_results(results, "ABC-123")

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


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_series_fallback_when_avdan_blank(_eg):
    results = {
        "javlib": {},
        "avdanyuwiki": {"series": ""},
        "javdb": {"series": "FromDB"},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "X-001")
    assert out.series == "FromDB"


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_series_fallback_when_avdan_dash(_eg):
    results = {
        "javlib": {},
        "avdanyuwiki": {"series": "----"},
        "javtxt": {"series": "FromTXT"},
        "javdb": {},
    }
    out = merge_crawl_results(results, "X-002")
    assert out.series == "FromTXT"


@patch(
    "tests.support.merge_crawl_legacy.exclude_genre_set",
    return_value=frozenset({"bad"}),
)
def test_merge_genre_excludes_configured(_eg):
    results = {
        "javlib": {"genre": ["ok", "bad"]},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "Y-1")
    assert "ok" in out.tag_list
    assert "bad" not in out.tag_list


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_leaves_cn_title_empty_for_translation_in_data_update(_eg):
    """合并阶段不译；中文标题在 ``DataUpdate.apply_title_story_translation`` 中补全。"""
    results = {
        "javlib": {"title": "JP Only"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {"cn_title": ""},
    }
    out = merge_crawl_results(results, "Z-9")
    assert out.cn_title == ""
    assert out.jp_title == "JP Only"


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_runtime_invalid_becomes_zero(_eg):
    results = {
        "javlib": {"length": "not-int"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "R-1")
    assert out.runtime == 0


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_runtime_from_javlib_length_when_no_avdan_runtime(_eg):
    results = {
        "javlib": {"length": "88"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "R-2")
    assert out.runtime == 88


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_skips_fanza_pl_when_maker_sod(_eg):
    """SOD 片商不插入 awsimgsrc PL 优先封面。"""
    results = {
        "javlib": {},
        "avdanyuwiki": {"maker": "SODクリエイト"},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "ABC-999")
    assert not any(
        u.startswith("https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/")
        for u in out.cover_url_list
    )


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_skips_fanza_pl_when_release_before_2019(_eg):
    """发售年份严格早于 ``_FANZA_PL_MIN_RELEASE_YEAR``(2018) 时不插入 awsimgsrc PL。"""
    results = {
        "javlib": {"release_date": "2017-06-01"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "IPX-100")
    assert not any(
        u.startswith("https://awsimgsrc.dmm.co.jp/") for u in out.cover_url_list
    )


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_inserts_fanza_pl_when_release_2019_or_later(_eg):
    """2019 年及以后仍插入 awsimgsrc PL（在无片商/前缀跳过时）。"""
    results = {
        "javlib": {"release_date": "2019-01-15"},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "IPX-100")
    assert any(
        u.startswith("https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/")
        for u in out.cover_url_list
    )


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_skips_fanza_pl_when_serial_prefix_start(_eg):
    """番号前缀在配置列表中时不插入 awsimgsrc PL。"""
    results = {
        "javlib": {},
        "avdanyuwiki": {"maker": "----"},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "STARS-123")
    assert not any(
        u.startswith("https://awsimgsrc.dmm.co.jp/") for u in out.cover_url_list
    )


@patch("tests.support.merge_crawl_legacy.exclude_genre_set", return_value=frozenset())
def test_merge_cover_list_image_as_list(_eg):
    results = {
        "javlib": {"image": ["https://a.jpg", "https://b.jpg"]},
        "avdanyuwiki": {},
        "javdb": {},
        "javtxt": {},
    }
    out = merge_crawl_results(results, "C-1")
    assert "https://a.jpg" in out.cover_url_list
    assert "https://b.jpg" in out.cover_url_list


def test_crawled_work_from_extension_payload_maps_fields():
    payload = {
        "serial_number": "ABC-001",
        "director": "D",
        "release_date": "2020-01-01",
        "runtime": 99,
        "cn_title": "中",
        "jp_title": "日",
        "cn_story": "cs",
        "jp_story": "js",
        "maker": "M",
        "series": "S",
        "label": "L",
        "tag_list": ["t1"],
        "actress_list": ["a1"],
        "actor_list": ["x1"],
        "cover_url_list": ["https://c.jpg"],
        "fanart_url_list": ["https://f.jpg"],
    }
    out = merge_service.crawled_work_from_extension_payload(payload)
    assert out.serial_number == "ABC-001"
    assert out.runtime == 99
    assert out.jp_title == "日"
    assert out.cover_url_list == ["https://c.jpg"]
