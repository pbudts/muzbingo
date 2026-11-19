"""UI tests with NiceGUI's simulated user: fast, no browser needed."""

import asyncio

import pytest
from nicegui import ui
from nicegui.testing import User

from muzbingo.models import Game
from muzbingo.services import Library
from tests.conftest import make_songs

pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.fixture(autouse=True)
def games_dir(tmp_path, monkeypatch):
    path = tmp_path / "games"
    monkeypatch.setenv("MUZBINGO_TEST_GAMES", str(path))
    return path


@pytest.fixture
def library(games_dir):
    return Library(games_dir)


@pytest.fixture
def saved_game(library) -> Game:
    game = Game(title="Kerstfeest", rows=4, cols=5, n_cards=6, seed=1, playlist=make_songs(45))
    library.save(game)
    return game


async def eventually(condition, timeout: float = 2.0) -> None:
    """Wait for background UI tasks (async click handlers) to finish."""
    for _ in range(int(timeout / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    assert condition()


async def test_empty_library(user: User):
    await user.open("/")
    await user.should_see("No games yet")


async def test_create_game(user: User, library):
    await user.open("/")
    user.find(marker="new-game").click()
    await user.should_see(marker="new-title")  # the dialog opens asynchronously
    user.find(marker="new-title").type("Kerstfeest 2026")
    user.find(marker="create").click()
    await user.should_see("Import playlist")  # the game page, playlist tab
    assert [s.title for s in library.list()] == ["Kerstfeest 2026"]


async def test_library_lists_games(user: User, saved_game):
    await user.open("/")
    await user.should_see("Kerstfeest")
    await user.should_see("45 songs · 0 cards")


async def test_unknown_game(user: User):
    await user.open("/game/00000000-0000-0000-0000-000000000000")
    await user.should_see("does not exist")


async def test_rename_game(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}")
    user.find(marker="title").clear().type("Nieuwjaar")
    await user.should_see("Nieuwjaar", marker="page-title")
    assert library.load(saved_game.id).title == "Nieuwjaar"


async def test_generate_cards(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}?tab=cards")
    await user.should_see("No cards yet.")
    user.find(marker="generate").click()
    await user.should_see("6 cards generated.")
    await user.should_see("6 cards of 4×5", marker="cards-summary")
    assert len(library.load(saved_game.id).cards) == 6


async def test_grid_change_regenerates_cards(user: User, library, saved_game):
    from muzbingo.generator import generate_for_game

    generate_for_game(saved_game)
    library.save(saved_game)
    await user.open(f"/game/{saved_game.id}?tab=cards")
    user.find(marker="cards-summary")  # cards are shown

    user.find("5×5").click()  # grid preset on the settings tab
    await user.should_see("New cards generated for the 5×5 grid.")
    await user.should_not_see(marker="outdated")
    game = library.load(saved_game.id)
    assert (game.rows, game.cols) == (5, 5)
    assert len(game.cards[0].cells) == 5 and not game.cards_outdated

    old_cards = [card.cells for card in saved_game.cards]
    user.find(marker="undo").click()  # one step back: the 4×5 grid with the old cards
    await eventually(lambda: library.load(saved_game.id).rows == 4)
    game = library.load(saved_game.id)
    assert (game.rows, game.cols) == (4, 5)
    assert [card.cells for card in game.cards] == old_cards


async def test_edit_song_in_table(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}?tab=playlist")
    song = saved_game.playlist[0]
    user.find(marker="playlist-grid").trigger(
        "cellValueChanged", {"colId": "title", "newValue": "Short", "data": {"id": song.id}}
    )
    assert library.load(saved_game.id).playlist[0].display_title == "Short"


async def test_only_too_long_empty_text(user: User, saved_game):
    await user.open(f"/game/{saved_game.id}?tab=playlist")
    grid = user.find(marker="playlist-grid").elements.pop()
    user.find(marker="only-too-long").click()
    assert grid.options["rowData"] == []  # the sample songs all fit
    assert "All texts fit" in grid.options["overlayNoRowsTemplate"]


async def test_preview_route(user: User, library, saved_game):
    from muzbingo.generator import generate_for_game

    generate_for_game(saved_game)
    library.save(saved_game)
    response = await user.http_client.get(f"/preview/{saved_game.id}/1")
    assert response.status_code == 200
    assert "Card 1" in response.text
    assert "/assets/templates/classic/style.css" in response.text

    css = await user.http_client.get("/assets/templates/classic/style.css")
    assert css.status_code == 200


async def test_undo_and_redo_buttons(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}")
    user.find(marker="title").clear().type("Nieuwjaar")
    assert library.load(saved_game.id).title == "Nieuwjaar"
    user.find(marker="undo").click()
    await user.should_see("Kerstfeest", marker="page-title")
    assert library.load(saved_game.id).title == "Kerstfeest"
    assert user.find(marker="title").elements.pop().value == "Kerstfeest"  # the panels were rebuilt
    user.find(marker="redo").click()
    await user.should_see("Nieuwjaar", marker="page-title")
    assert library.load(saved_game.id).title == "Nieuwjaar"


async def test_shorten_titles_dialog(user: User, library, saved_game):
    saved_game.playlist[0].title = "Hey Jude - Remastered 2015"
    library.save(saved_game)
    await user.open(f"/game/{saved_game.id}?tab=playlist")
    user.find(marker="shorten-titles").click()
    await user.should_see(marker="cleanup-grid")
    grid = user.find(marker="cleanup-grid").elements.pop()
    assert grid.options["rowData"][0]["new"] == "Hey Jude"


async def test_copy_template(user: User, saved_game, tmp_path, monkeypatch):
    from muzbingo import paths

    monkeypatch.setattr(paths, "_data_dir_override", tmp_path / "data")
    await user.open(f"/game/{saved_game.id}")
    user.find(marker="copy-template").click()
    await user.should_see(marker="copy-name")
    user.find(marker="copy-name").clear().type("Our party")
    user.find(marker="copy-ok").click()
    await user.should_see("Copied to")
    assert (tmp_path / "data" / "templates" / "our-party" / "template.toml").is_file()


async def test_undo_survives_reload(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}")
    user.find(marker="title").clear().type("Nieuwjaar")
    await user.open(f"/game/{saved_game.id}")  # e.g. after "back to My games"
    user.find(marker="undo").click()
    await user.should_see("Kerstfeest", marker="page-title")
    assert library.load(saved_game.id).title == "Kerstfeest"


async def test_changed_file_is_reloaded(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}")
    user.find(marker="title").clear().type("Nieuwjaar")
    game = library.load(saved_game.id)
    game.title = "Changed elsewhere"
    library.save(game)
    await user.open(f"/game/{saved_game.id}")
    await user.should_see("Changed elsewhere", marker="page-title")
