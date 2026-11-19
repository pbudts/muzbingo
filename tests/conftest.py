import pytest

from muzbingo import paths, settings
from muzbingo.i18n import set_language
from muzbingo.models import Card, Game, Song


def make_songs(n: int) -> list[Song]:
    return [Song(title=f"Title {i}", artist=f"Artist {i}") for i in range(1, n + 1)]


@pytest.fixture
def songs() -> list[Song]:
    return make_songs(60)


@pytest.fixture
def game(songs) -> Game:
    from muzbingo.generator import generate_for_game

    g = Game(title="Test Bingo", rows=4, cols=5, n_cards=5, seed=42, playlist=songs)
    generate_for_game(g)
    return g


@pytest.fixture
def simple_card() -> Card:
    return Card(number=1, cells=[["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]])


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Never read or write the real user data folder (settings, templates) in tests."""
    monkeypatch.setattr(paths, "_data_dir_override", tmp_path / "muzbingo-data")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("LANGUAGE", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    settings.reset()
    set_language("en")
    yield
    settings.reset()
    set_language("en")
