"""Turn a Game into the data a card template sees.

Templates never look up songs or format dates themselves; everything they print is
prepared here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from muzbingo.models import Game, Song
from muzbingo.render.templates import CardTemplate

MONTHS_SHORT = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "nl": ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
}
MONTHS_LONG = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
           "september", "oktober", "november", "december"],
}
DEFAULT_DATE_FORMATS = {
    "en": "{day} {month_short} {year}",
    "nl": "{day:02d}/{month:02d}/{year}",
}


class RenderError(Exception):
    """The cards could not be rendered."""


def format_date(value: date | None, language: str, formats: dict[str, str] | None = None) -> str:
    """Format a date with a template format string.

    Available fields: ``{day}``, ``{month}``, ``{year}``, ``{month_short}``, ``{month_long}``,
    e.g. ``"{day:02d}/{month:02d}/{year}"`` → 19/12/2026.
    """
    if value is None:
        return ""
    formats = {**DEFAULT_DATE_FORMATS, **(formats or {})}
    fmt = formats.get(language) or formats["en"]
    lang = language if language in MONTHS_SHORT else "en"
    try:
        return fmt.format(
            day=value.day,
            month=value.month,
            year=value.year,
            month_short=MONTHS_SHORT[lang][value.month - 1],
            month_long=MONTHS_LONG[lang][value.month - 1],
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise RenderError(f"Invalid date format {fmt!r}: {exc}") from exc


def text_length(song: Song) -> int:
    return len(song.shown_title) + len(song.shown_artist)


def fit_class(song: Song, budget: int) -> str:
    """Font-size class for a cell: 'normal', 'small', or 'tiny' (= too long, shorten it)."""
    n = text_length(song)
    if n <= budget * 0.75:
        return "normal"
    if n <= budget:
        return "small"
    return "tiny"


def is_too_long(song: Song, template: CardTemplate, cols: int) -> bool:
    return text_length(song) > template.char_budget(cols)


def build_context(
    game: Game,
    template: CardTemplate,
    *,
    background_url: str | None = None,
    logo_url: str | None = None,
) -> dict[str, Any]:
    if not game.cards:
        raise RenderError("There are no cards to print; generate the cards first")

    songs = game.songs_by_id()
    budget = template.char_budget(game.cols)
    cards = []
    for card in game.cards:
        rows = []
        for row in card.cells:
            cells = []
            for song_id in row:
                song = songs.get(song_id)
                if song is None:
                    raise RenderError(
                        f"Card {card.number} contains a song that is no longer in the playlist; "
                        "regenerate the cards"
                    )
                cells.append(
                    {
                        "title": song.shown_title,
                        "artist": song.shown_artist,
                        "size": fit_class(song, budget),
                    }
                )
            rows.append(cells)
        cards.append({"number": card.number, "rows": rows})

    return {
        "game": {
            "title": game.title,
            "rows": game.rows,
            "cols": game.cols,
            "event_date": game.event_date,
            "language": game.language,
        },
        "cards": cards,
        "date_text": format_date(game.event_date, game.language, template.date_formats),
        "labels": template.label_set(game.language),
        "background_url": background_url,
        "logo_url": logo_url,
        "template_url": template.path.resolve().as_uri() + "/",
        "options": {"page_size": template.page_size, "orientation": template.orientation},
    }
