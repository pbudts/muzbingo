"""UI tests with NiceGUI's simulated user: fast, no browser needed."""

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


async def test_settings_change_marks_cards_outdated(user: User, library, saved_game):
    from muzbingo.generator import generate_for_game

    generate_for_game(saved_game)
    library.save(saved_game)
    await user.open(f"/game/{saved_game.id}?tab=cards")
    await user.should_not_see(marker="outdated")
    user.find(marker="cards-summary")  # cards are shown

    user.find("5×5").click()  # grid preset on the settings tab
    await user.should_see(marker="outdated")
    assert library.load(saved_game.id).cols == 5


async def test_edit_song_in_table(user: User, library, saved_game):
    await user.open(f"/game/{saved_game.id}?tab=playlist")
    song = saved_game.playlist[0]
    user.find(marker="playlist-grid").trigger(
        "cellValueChanged", {"colId": "title", "newValue": "Short", "data": {"id": song.id}}
    )
    assert library.load(saved_game.id).playlist[0].display_title == "Short"


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
