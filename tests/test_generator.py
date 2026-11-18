from collections import Counter

import pytest

from muzbingo.generator import GenerationError, generate_cards


def test_shape_and_numbering(songs):
    cards = generate_cards(songs, 10, rows=4, cols=5, seed=1)

    assert [c.number for c in cards] == list(range(1, 11))
    for card in cards:
        assert len(card.cells) == 4
        assert all(len(row) == 5 for row in card.cells)


def test_no_song_twice_on_a_card_and_cards_unique(songs):
    cards = generate_cards(songs, 50, rows=5, cols=5, seed=7)

    for card in cards:
        assert len(set(card.song_ids)) == 25
    assert len({frozenset(c.song_ids) for c in cards}) == 50


def test_same_seed_same_cards(songs):
    a = generate_cards(songs, 20, 4, 5, seed=123)
    b = generate_cards(songs, 20, 4, 5, seed=123)
    c = generate_cards(songs, 20, 4, 5, seed=124)
    assert a == b
    assert a != c


def test_songs_are_spread_evenly(songs):
    cards = generate_cards(songs, 30, 4, 5, seed=5)  # 600 cells over 60 songs = 10 each
    counts = Counter(sid for card in cards for sid in card.song_ids)

    assert len(counts) == 60
    assert max(counts.values()) - min(counts.values()) <= 2


def test_accepts_song_ids(songs):
    ids = [s.id for s in songs]
    assert generate_cards(ids, 3, 4, 5, seed=9) == generate_cards(songs, 3, 4, 5, seed=9)


def test_playlist_too_small(songs):
    with pytest.raises(GenerationError, match="needs 25 songs"):
        generate_cards(songs[:24], 1, 5, 5, seed=1)


def test_more_cards_than_possible(songs):
    # 4 songs on a 2×2 card: only one combination exists
    assert len(generate_cards(songs[:4], 1, 2, 2, seed=1)) == 1
    with pytest.raises(GenerationError, match="different cards"):
        generate_cards(songs[:4], 2, 2, 2, seed=1)


def test_invalid_input(songs):
    with pytest.raises(GenerationError):
        generate_cards(songs, 0, 4, 5, seed=1)
    with pytest.raises(GenerationError):
        generate_cards(songs + songs[:1], 1, 4, 5, seed=1)
