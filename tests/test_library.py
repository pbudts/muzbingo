import pytest

from muzbingo.services import Library, LibraryError


@pytest.fixture
def library(tmp_path):
    return Library(tmp_path / "games")


def test_create_list_load(library):
    assert library.list() == []
    a = library.create("Kerstfeest")
    b = library.create("  ")
    b.title = "Changed"
    library.save(b)

    summaries = library.list()
    assert [s.title for s in summaries] == ["Changed", "Kerstfeest"]  # newest first
    assert library.load(a.id) == a


def test_save_keeps_changes(library, game):
    library.save(game)
    game.playlist[0].display_title = "Short"
    library.save(game)
    assert library.load(game.id).playlist[0].display_title == "Short"
    assert library.list()[0].n_cards == len(game.cards)


def test_duplicate(library, game):
    game.played = [game.playlist[0].id]
    library.save(game)
    copy = library.duplicate(game.id)

    assert copy.id != game.id
    assert copy.title == "Test Bingo (copy)"
    assert copy.cards == game.cards
    assert copy.played == []
    assert len(library.list()) == 2


def test_delete_moves_to_trash(library, game):
    library.save(game)
    library.delete(game.id)
    assert library.list() == []
    assert len(list(library.trash.iterdir())) == 1
    with pytest.raises(LibraryError):
        library.load(game.id)


def test_import_never_overwrites(library, game):
    library.save(game)
    data = library.export_bytes(game.id)

    imported = library.import_bytes(data)

    assert imported.id != game.id
    assert imported.cards == game.cards
    assert len(library.list()) == 2


def test_import_rejects_other_files(library):
    with pytest.raises(LibraryError):
        library.import_bytes(b"not a game", "x.muzbingo")


def test_ids_are_checked(library):
    with pytest.raises(LibraryError):
        library.load("../../etc/passwd")
    assert not library.exists("../x")


def test_unreadable_files_are_skipped_in_list(library, game):
    library.save(game)
    (library.root / "broken.muzbingo").write_text("{", encoding="utf-8")
    assert [s.id for s in library.list()] == [game.id]
