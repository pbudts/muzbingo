"""Everything the UI can do with one game. Every change is saved immediately.

The UI only talks to this class (and the library), so the rules live here and are
tested without a browser.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from muzbingo.generator import GenerationError, generate_for_game
from muzbingo.i18n import _
from muzbingo.importers import ColumnMapping, ImportResult, import_playlist
from muzbingo.models import Card, Game, Image, Song
from muzbingo.render import CardTemplate, is_too_long, load_template
from muzbingo.services.library import Library

MIN_SIZE, MAX_SIZE = 2, 8  # rows and columns
MAX_CARDS = 500
CARD_LANGUAGES = {"en": "English", "nl": "Nederlands"}
IMAGE_KINDS = ("background", "logo")


class ServiceError(Exception):
    """A user-facing error: the message is shown in the UI as is."""


@dataclass(frozen=True)
class PlaylistStatus:
    n_songs: int
    needed: int  # songs needed for one card
    can_generate: bool
    message: str  # "" when all is fine


class GameService:
    def __init__(self, library: Library, game: Game, on_saved: Callable[[Game], None] | None = None):
        self.library = library
        self.game = game
        self.on_saved = on_saved
        self._template: CardTemplate | None = None

    @classmethod
    def open(cls, library: Library, game_id: str) -> GameService:
        return cls(library, library.load(game_id))

    def save(self) -> None:
        self.library.save(self.game)
        if self.on_saved:
            self.on_saved(self.game)

    # -- settings ----------------------------------------------------------

    def template(self) -> CardTemplate:
        if self._template is None or self._template.name != self.game.template:
            self._template = load_template(self.game.template)
        return self._template

    def update(
        self,
        *,
        title: str | None = None,
        event_date: date | None | str = "",
        rows: int | None = None,
        cols: int | None = None,
        n_cards: int | None = None,
        seed: int | None = None,
        language: str | None = None,
        template: str | None = None,
    ) -> None:
        """Change settings. ``event_date=None`` clears the date; leave it out to keep it."""
        g = self.game
        if title is not None:
            g.title = title.strip() or g.title
        if event_date != "":
            g.event_date = event_date  # type: ignore[assignment]
        if rows is not None:
            g.rows = self._check_range(rows, MIN_SIZE, MAX_SIZE, _("Rows"))
        if cols is not None:
            g.cols = self._check_range(cols, MIN_SIZE, MAX_SIZE, _("Columns"))
        if n_cards is not None:
            g.n_cards = self._check_range(n_cards, 1, MAX_CARDS, _("Number of cards"))
        if seed is not None:
            g.seed = int(seed)
        if language is not None:
            if language not in CARD_LANGUAGES:
                raise ServiceError(_("Unknown card language: {language}").format(language=language))
            g.language = language
        if template is not None:
            load_template(template)  # raises TemplateError for an unknown template
            g.template = template
        self.save()

    @staticmethod
    def _check_range(value: int, low: int, high: int, label: str) -> int:
        value = int(value)
        if not low <= value <= high:
            raise ServiceError(
                _("{label} must be between {low} and {high}").format(label=label, low=low, high=high)
            )
        return value

    def set_image(self, kind: str, image: Image | None) -> None:
        if kind not in IMAGE_KINDS:
            raise ValueError(kind)
        setattr(self.game, kind, image)
        self.save()

    # -- playlist ----------------------------------------------------------

    def import_playlist(
        self, path: Path, mapping: ColumnMapping | None = None, *, append: bool = False
    ) -> ImportResult:
        """Read a playlist file and replace (or extend) the playlist.

        Raises ``MappingRequired`` when the columns must be chosen by the user.
        """
        result = import_playlist(path, mapping)
        if append:
            known_ids = {s.id for s in self.game.playlist}
            known_keys = {(s.artist.casefold(), s.title.casefold()) for s in self.game.playlist}
            added = []
            for song in result.songs:
                if song.id in known_ids or (song.artist.casefold(), song.title.casefold()) in known_keys:
                    result.warnings.append(
                        _("Already in the playlist: {artist} – {title}").format(
                            artist=song.artist, title=song.title
                        )
                    )
                    continue
                added.append(song)
            self.game.playlist.extend(added)
            result.songs = added
        else:
            self.game.playlist = result.songs
        self.save()
        return result

    def song(self, song_id: str) -> Song:
        for song in self.game.playlist:
            if song.id == song_id:
                return song
        raise ServiceError(_("This song is no longer in the playlist"))

    def edit_song(self, song_id: str, *, title: str | None = None, artist: str | None = None) -> Song:
        """Set the text printed on the cards. Empty or original text removes the override."""
        song = self.song(song_id)
        if title is not None:
            title = " ".join(title.split())
            song.display_title = title if title and title != song.title else None
        if artist is not None:
            artist = " ".join(artist.split())
            song.display_artist = artist if artist and artist != song.artist else None
        self.save()
        return song

    def reset_song(self, song_id: str) -> Song:
        song = self.song(song_id)
        song.display_title = song.display_artist = None
        self.save()
        return song

    def add_song(self, title: str, artist: str) -> Song:
        title, artist = " ".join(title.split()), " ".join(artist.split())
        if not title or not artist:
            raise ServiceError(_("Enter both a title and an artist"))
        song = Song(title=title, artist=artist)
        key = (artist.casefold(), title.casefold())
        if any(s.id == song.id or (s.artist.casefold(), s.title.casefold()) == key for s in self.game.playlist):
            raise ServiceError(_("This song is already in the playlist"))
        self.game.playlist.append(song)
        self.save()
        return song

    def delete_song(self, song_id: str) -> None:
        song = self.song(song_id)
        self.game.playlist.remove(song)
        self.save()

    def songs_on_cards(self) -> set[str]:
        return {sid for card in self.game.cards for sid in card.song_ids}

    def too_long(self, song: Song) -> bool:
        return is_too_long(song, self.template(), self.game.cols)

    def playlist_status(self) -> PlaylistStatus:
        n, needed = len(self.game.playlist), self.game.songs_per_card
        if n < needed:
            message = _(
                "A {rows}×{cols} card needs {needed} songs; the playlist has {n}. Add songs or use a smaller grid."
            ).format(rows=self.game.rows, cols=self.game.cols, needed=needed, n=n)
            return PlaylistStatus(n, needed, False, message)
        if n < 2 * needed:
            message = _(
                "Tip: with fewer than {double} songs, cards look much alike and games end quickly."
            ).format(double=2 * needed)
            return PlaylistStatus(n, needed, True, message)
        return PlaylistStatus(n, needed, True, "")

    # -- cards -------------------------------------------------------------

    def generate(self) -> list[Card]:
        try:
            cards = generate_for_game(self.game)
        except GenerationError as exc:
            raise ServiceError(str(exc)) from exc
        self.save()
        return cards
