import pytest

from muzbingo.models import Card, Game, Song


def make_songs(n: int) -> list[Song]:
    return [Song(title=f"Title {i}", artist=f"Artist {i}") for i in range(1, n + 1)]


@pytest.fixture
def songs() -> list[Song]:
    return make_songs(60)


@pytest.fixture
def game(songs) -> Game:
    from muzbingo.generator import generate_cards

    g = Game(title="Test Bingo", rows=4, cols=5, seed=42, playlist=songs)
    g.cards = generate_cards(g.playlist, 5, g.rows, g.cols, g.seed)
    return g


@pytest.fixture
def simple_card() -> Card:
    return Card(number=1, cells=[["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]])
