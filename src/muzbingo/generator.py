"""Generate randomized bingo cards.

Cards are dealt from a shuffled "deck" of all songs, reshuffled when it runs out, so
every song appears on about the same number of cards. The same inputs and seed
always produce the same cards.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

from muzbingo.models import Card, Song

MAX_RETRIES = 1000


class GenerationError(ValueError):
    """The requested cards can't be generated from this playlist."""


def generate_cards(
    songs: Sequence[Song] | Sequence[str],
    n_cards: int,
    rows: int,
    cols: int,
    seed: int,
) -> list[Card]:
    ids = [s.id if isinstance(s, Song) else s for s in songs]
    per_card = rows * cols

    if rows < 1 or cols < 1:
        raise GenerationError("The grid needs at least one row and one column")
    if n_cards < 1:
        raise GenerationError("The number of cards must be at least 1")
    if len(set(ids)) != len(ids):
        raise GenerationError("The playlist contains duplicate songs")
    if len(ids) < per_card:
        raise GenerationError(
            f"A {rows}×{cols} card needs {per_card} songs, but the playlist has only {len(ids)}"
        )
    if math.comb(len(ids), per_card) < n_cards:
        raise GenerationError(
            f"Only {math.comb(len(ids), per_card)} different cards are possible with this playlist"
        )

    rng = random.Random(seed)
    deck: list[str] = []

    def deal() -> list[str]:
        chosen: list[str] = []
        on_card: set[str] = set()
        skipped: list[str] = []
        while len(chosen) < per_card:
            if not deck:
                deck.extend(rng.sample(ids, len(ids)))
            song_id = deck.pop()
            if song_id in on_card:  # can happen right after a reshuffle
                skipped.append(song_id)
                continue
            chosen.append(song_id)
            on_card.add(song_id)
        deck.extend(skipped)  # dealt first on the next card
        return chosen

    cards: list[Card] = []
    seen: set[frozenset[str]] = set()
    retries = 0
    while len(cards) < n_cards:
        chosen = deal()
        key = frozenset(chosen)
        if key in seen:
            retries += 1
            if retries > MAX_RETRIES:
                raise GenerationError(
                    "Could not generate enough different cards; add songs or use fewer cards"
                )
            continue
        seen.add(key)
        cells = [chosen[r * cols : (r + 1) * cols] for r in range(rows)]
        cards.append(Card(number=len(cards) + 1, cells=cells))
    return cards
