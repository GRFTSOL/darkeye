from __future__ import annotations

from pathlib import Path

from core.importers.mdcz_movie_nfo_import import (
    _save_and_move_extrafanart_files,
    parse_mdcz_movie_nfo,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_mdcz_nfo_uniqueid_cover_and_actor_name_only(tmp_path: Path) -> None:
    nfo = tmp_path / "movie.nfo"
    (tmp_path / "fanart.jpg").write_bytes(b"jpg")
    _write_text(
        nfo,
        """<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <uniqueid type="jav321" default="true">cawd-584</uniqueid>
  <releasedate>2023-11-03</releasedate>
  <title>t</title>
  <plot>p</plot>
  <actor>
    <name>設楽ゆうひ</name>
    <type>Actor</type>
    <thumb>.actors/設楽ゆうひ.jpg</thumb>
    <order>0</order>
    <sortorder>0</sortorder>
  </actor>
</movie>""",
    )

    parsed, err = parse_mdcz_movie_nfo(nfo)
    assert err is None
    assert parsed is not None
    assert parsed.serial_number == "CAWD-584"
    assert parsed.release_date == "2023-11-03"
    assert parsed.cover_local_path == str((tmp_path / "fanart.jpg").resolve())
    assert parsed.actor_names == ["設楽ゆうひ"]


def test_parse_mdcz_scene_images_match_extrafanart(tmp_path: Path) -> None:
    nfo = tmp_path / "movie.nfo"
    ext = tmp_path / "extrafanart"
    ext.mkdir(parents=True, exist_ok=True)
    (ext / "cawd00584jp-1.jpg").write_bytes(b"1")

    _write_text(
        nfo,
        """<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <id>CAWD-584</id>
  <mdcz>
    <scene_images>
      <image>http://pics.example.com/cawd00584jp-1.jpg</image>
      <image>http://pics.example.com/cawd00584jp-2.jpg</image>
    </scene_images>
  </mdcz>
</movie>""",
    )

    parsed, err = parse_mdcz_movie_nfo(nfo)
    assert err is None
    assert parsed is not None

    assert len(parsed.extrafanart_pairs) == 1
    url, dest_name, src = parsed.extrafanart_pairs[0]
    assert url.endswith("cawd00584jp-1.jpg")
    assert dest_name == "cawd00584jp-1.jpg"
    assert src == (ext / "cawd00584jp-1.jpg").resolve()

    by_url = {(x["url"], x["file"]) for x in parsed.fanart_items}
    assert ("http://pics.example.com/cawd00584jp-1.jpg", "cawd00584jp-1.jpg") in by_url
    assert ("http://pics.example.com/cawd00584jp-2.jpg", "") in by_url
    assert len(by_url) == 2


def test_parse_mdcz_scene_images_fallback_match_by_order(tmp_path: Path) -> None:
    nfo = tmp_path / "movie.nfo"
    ext = tmp_path / "extrafanart"
    ext.mkdir(parents=True, exist_ok=True)
    # 故意使用与 URL 不同的本地命名，验证按顺序一一对应兜底
    (ext / "001.jpg").write_bytes(b"1")
    (ext / "002.jpg").write_bytes(b"2")

    _write_text(
        nfo,
        """<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <id>IPX-607</id>
  <mdcz>
    <scene_images>
      <image>http://pics.example.com/ipx607jp-1.jpg</image>
      <image>http://pics.example.com/ipx607jp-2.jpg</image>
    </scene_images>
  </mdcz>
</movie>""",
    )

    parsed, err = parse_mdcz_movie_nfo(nfo)
    assert err is None
    assert parsed is not None
    assert len(parsed.extrafanart_pairs) == 2
    assert parsed.extrafanart_pairs[0][2].name == "001.jpg"
    assert parsed.extrafanart_pairs[1][2].name == "002.jpg"
    by_url = {(x["url"], x["file"]) for x in parsed.fanart_items}
    assert ("http://pics.example.com/ipx607jp-1.jpg", "ipx607jp-1.jpg") in by_url
    assert ("http://pics.example.com/ipx607jp-2.jpg", "ipx607jp-2.jpg") in by_url


def test_save_and_move_extrafanart_files_delete_source(
    tmp_path: Path, monkeypatch
) -> None:
    src = tmp_path / "extrafanart" / "cawd00584jp-1.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"fanart")

    calls: list[tuple[str, str, str]] = []

    def _fake_rename_save_image(path: str, name: str, typ: str) -> None:
        calls.append((path, name, typ))

    monkeypatch.setattr(
        "core.importers.mdcz_movie_nfo_import.rename_save_image", _fake_rename_save_image
    )

    out = _save_and_move_extrafanart_files(
        [("http://pics.example.com/cawd00584jp-1.jpg", "cawd00584jp-1.jpg", src)]
    )
    assert out == [
        {"url": "http://pics.example.com/cawd00584jp-1.jpg", "file": "cawd00584jp-1.jpg"}
    ]
    assert calls == [(str(src), "cawd00584jp-1.jpg", "fanart")]
    assert not src.exists()
