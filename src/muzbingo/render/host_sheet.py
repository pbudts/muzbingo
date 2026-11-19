"""The host sheet: the whole playlist as a checklist on A4 portrait.

The host ticks off songs while playing. The sheet doesn't depend on the card
template; its HTML is ``host_sheet.html.j2`` next to this file.
"""

from __future__ import annotations

import random
from collections import Counter
from enum import Enum
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from muzbingo.models import Game, Song
from muzbingo.render.context import RenderError, format_date
from muzbingo.i18n import _

PAGE_SIZE, ORIENTATION = "A4", "portrait"

LABELS = {
    "en": {
        "songs": "songs", "cards": "cards", "played": "Played", "title": "Title", "artist": "Artist",
        "on_cards": "On cards", "not_on_cards": "on no card",
        "order": {"playlist": "Playlist order", "artist": "Sorted by artist", "title": "Sorted by title",
                  "shuffled": "Play order (shuffled)"},
    },
    "nl": {
        "songs": "nummers", "cards": "kaarten", "played": "Gespeeld", "title": "Titel", "artist": "Artiest",
        "on_cards": "Op kaarten", "not_on_cards": "op geen kaart",
        "order": {"playlist": "Volgorde van de playlist", "artist": "Gesorteerd op artiest",
                  "title": "Gesorteerd op titel", "shuffled": "Speelvolgorde (geschud)"},
    },
}


class HostOrder(str, Enum):
    PLAYLIST = "playlist"
    ARTIST = "artist"
    TITLE = "title"
    SHUFFLED = "shuffled"  # a random play order, the same every time for a game


def ordered_songs(game: Game, order: HostOrder | str) -> list[Song]:
    order = HostOrder(order)
    songs = list(game.playlist)
    if order is HostOrder.ARTIST:
        songs.sort(key=lambda s: (s.shown_artist.casefold(), s.shown_title.casefold()))
    elif order is HostOrder.TITLE:
        songs.sort(key=lambda s: (s.shown_title.casefold(), s.shown_artist.casefold()))
    elif order is HostOrder.SHUFFLED:
        random.Random(f"{game.seed}:host").shuffle(songs)
    return songs


def render_host_sheet(game: Game, order: HostOrder | str = HostOrder.PLAYLIST) -> str:
    """The host sheet as a self-contained HTML document."""
    if not game.playlist:
        raise RenderError(_("The playlist is empty"))
    order = HostOrder(order)
    labels = LABELS.get(game.language, LABELS["en"])
    position = {song.id: n for n, song in enumerate(game.playlist, start=1)}
    on_cards = Counter(sid for card in game.cards for sid in card.song_ids)
    rows = [
        {
            "n": position[song.id],
            "title": song.shown_title,
            "artist": song.shown_artist,
            "cards": on_cards.get(song.id, 0),
        }
        for song in ordered_songs(game, order)
    ]
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("host_sheet.html.j2").render(
        game={"title": game.title, "rows": game.rows, "cols": game.cols, "language": game.language},
        n_cards=len(game.cards),
        date_text=format_date(game.event_date, game.language),
        order_text=labels["order"][order.value],
        labels=labels,
        rows=rows,
        show_cards=bool(game.cards),
    )
