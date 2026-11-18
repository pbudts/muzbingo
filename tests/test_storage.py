import json

import pytest

from muzbingo.models import Image
from muzbingo.storage import StorageError, load_game, save_game


def test_save_and_load(tmp_path, game):
    game.background = Image(filename="bg.jpg", mime="image/jpeg", data=bytes(range(256)))
    path = save_game(game, tmp_path / "game.muzbingo")

    loaded = load_game(path)

    assert loaded == game
    assert not list(tmp_path.glob("*.tmp"))


def test_file_is_readable_json(tmp_path, game):
    game.title = "Kerstfeest — ‘26"
    path = save_game(game, tmp_path / "game.muzbingo")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format_version"] == 1
    assert data["title"] == "Kerstfeest — ‘26"
    assert "Kerstfeest" in path.read_text(encoding="utf-8")  # not \u-escaped


def test_rejects_other_files(tmp_path):
    bad = tmp_path / "bad.muzbingo"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(StorageError):
        load_game(bad)

    bad.write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(StorageError, match="not a MuzBingo"):
        load_game(bad)

    with pytest.raises(StorageError):
        load_game(tmp_path / "missing.muzbingo")


def test_rejects_newer_format(tmp_path, game):
    data = game.to_dict()
    data["format_version"] = 99
    path = tmp_path / "new.muzbingo"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StorageError, match="newer version"):
        load_game(path)


def test_damaged_file(tmp_path):
    path = tmp_path / "broken.muzbingo"
    path.write_text('{"format_version": 1, "title": "x"}', encoding="utf-8")
    with pytest.raises(StorageError, match="damaged"):
        load_game(path)
