"""Everything the UI can do with one game. Every change is saved immediately.

The UI only talks to this class (and the library), so the rules live here and are
tested without a browser.
"""

from __future__ import annotations

import copy
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from muzbingo.cleanup import clean_title
from muzbingo.generator import GenerationError, generate_for_game
from muzbingo.i18n import _
from muzbingo.importers import ColumnMapping, ImportResult, import_playlist
from muzbingo.images import ImageError, prepare_image
from muzbingo.models import Card, Game, Image, Song
from muzbingo.render import CardTemplate, is_too_long, load_template
from muzbingo.services.library import Library

MIN_SIZE, MAX_SIZE = 2, 8  # rows and columns
MAX_CARDS = 500
CARD_LANGUAGES = {"en": "English", "nl": "Nederlands"}
IMAGE_KINDS = ("background", "logo")
HISTORY_SIZE = 50
COALESCE_SECONDS = 3.0  # repeated edits of the same field within this time undo as one step


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
        self._undo: list[Game] = []
        self._redo: list[Game] = []
        self._last_change: tuple[str, float] = ("", 0.0)
        self._version = library.version(game.id)

    @classmethod
    def open(cls, library: Library, game_id: str) -> GameService:
        return cls(library, library.load(game_id))

    def save(self) -> None:
        self.library.save(self.game)
        self._version = self.library.version(self.game.id)
        if self.on_saved:
            self.on_saved(self.game)

    @property
    def is_current(self) -> bool:
        """False when the game file was changed or removed by something else."""
        version = self.library.version(self.game.id)
        return version is not None and version == self._version

    # -- undo ----------------------------------------------------------------

    @contextmanager
    def _change(self, key: str = "") -> Iterator[None]:
        """Wrap every change: makes it undoable, saves it, and rolls back on errors.

        Changes with the same non-empty ``key`` shortly after each other (typing in
        the title field) are undone as one step.
        """
        before = copy.deepcopy(self.game)
        try:
            yield
        except Exception:
            self._restore(before)
            raise
        if self.game == before:
            return
        now = time.monotonic()
        last_key, last_time = self._last_change
        if not (key and key == last_key and now - last_time < COALESCE_SECONDS and self._undo):
            self._undo.append(before)
            del self._undo[:-HISTORY_SIZE]
        self._last_change = (key, now)
        self._redo.clear()
        self.save()

    def _restore(self, snapshot: Game) -> None:
        # Update in place: the UI panels keep a reference to self.game.
        self.game.__dict__.update(copy.deepcopy(snapshot).__dict__)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(copy.deepcopy(self.game))
        self._restore(self._undo.pop())
        self._last_change = ("", 0.0)
        self.save()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(copy.deepcopy(self.game))
        self._restore(self._redo.pop())
        self._last_change = ("", 0.0)
        self.save()
        return True

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
    ) -> bool:
        """Change settings. ``event_date=None`` clears the date; leave it out to keep it.

        Changing the grid size regenerates existing cards right away (old cards don't fit
        the new grid anyway), in the same undo step. Returns True when that happened.
        """
        fields = [name for name, value in (("title", title), ("rows", rows), ("cols", cols),
                  ("n_cards", n_cards), ("seed", seed), ("language", language), ("template", template))
                  if value is not None] + (["event_date"] if event_date != "" else [])
        with self._change("update:" + ",".join(fields)):
            old_grid = (self.game.rows, self.game.cols)
            self._update(title, event_date, rows, cols, n_cards, seed, language, template)
            return self._regenerate_for_new_grid(old_grid)

    def _regenerate_for_new_grid(self, old_grid: tuple[int, int]) -> bool:
        g = self.game
        if (g.rows, g.cols) == old_grid or not g.cards or len(g.playlist) < g.songs_per_card:
            return False
        try:
            generate_for_game(g)
        except GenerationError:
            return False  # the cards stay marked as out of date, with the reason shown
        return True

    def _update(self, title, event_date, rows, cols, n_cards, seed, language, template) -> None:
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

    @staticmethod
    def _check_range(value: int, low: int, high: int, label: str) -> int:
        value = int(value)
        if not low <= value <= high:
            raise ServiceError(
                _("{label} must be between {low} and {high}").format(label=label, low=low, high=high)
            )
        return value

    def set_image(self, kind: str, image: Image | None) -> None:
        """Set the game's own logo or background (``None``: the template default).

        Large photos are scaled down to what printing needs.
        """
        if kind not in IMAGE_KINDS:
            raise ValueError(kind)
        if image is not None:
            try:
                image = prepare_image(image, kind)
            except ImageError as exc:
                raise ServiceError(_("This picture could not be read: {error}").format(error=exc)) from exc
        with self._change():
            setattr(self.game, kind, image)

    # -- playlist ----------------------------------------------------------

    def import_playlist(
        self, path: Path, mapping: ColumnMapping | None = None, *, append: bool = False
    ) -> ImportResult:
        """Read a playlist file and replace (or extend) the playlist.

        Raises ``MappingRequired`` when the columns must be chosen by the user.
        """
        result = import_playlist(path, mapping)
        with self._change():
            self._apply_import(result, append)
        return result

    def _apply_import(self, result: ImportResult, append: bool) -> None:
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

    def song(self, song_id: str) -> Song:
        for song in self.game.playlist:
            if song.id == song_id:
                return song
        raise ServiceError(_("This song is no longer in the playlist"))

    def edit_song(self, song_id: str, *, title: str | None = None, artist: str | None = None) -> Song:
        """Set the text printed on the cards. Empty or original text removes the override."""
        song = self.song(song_id)
        column = "title" if title is not None else "artist"
        with self._change(f"edit:{song_id}:{column}"):
            if title is not None:
                self._set_display_title(song, title)
            if artist is not None:
                artist = " ".join(artist.split())
                song.display_artist = artist if artist and artist != song.artist else None
        return song

    @staticmethod
    def _set_display_title(song: Song, title: str) -> None:
        title = " ".join(title.split())
        song.display_title = title if title and title != song.title else None

    def reset_song(self, song_id: str) -> Song:
        self.reset_songs([song_id])
        return self.song(song_id)

    def reset_songs(self, song_ids: list[str]) -> None:
        """Print the original title and artist again."""
        songs = [self.song(song_id) for song_id in song_ids]
        with self._change():
            for song in songs:
                song.display_title = song.display_artist = None

    def add_song(self, title: str, artist: str) -> Song:
        title, artist = " ".join(title.split()), " ".join(artist.split())
        if not title or not artist:
            raise ServiceError(_("Enter both a title and an artist"))
        song = Song(title=title, artist=artist)
        key = (artist.casefold(), title.casefold())
        if any(s.id == song.id or (s.artist.casefold(), s.title.casefold()) == key for s in self.game.playlist):
            raise ServiceError(_("This song is already in the playlist"))
        with self._change():
            self.game.playlist.append(song)
        return song

    def delete_song(self, song_id: str) -> None:
        self.delete_songs([song_id])

    def delete_songs(self, song_ids: list[str]) -> None:
        ids = {self.song(song_id).id for song_id in song_ids}  # raises for unknown songs
        with self._change():
            self.game.playlist = [s for s in self.game.playlist if s.id not in ids]

    # -- bulk cleanup ------------------------------------------------------

    def cleanup_suggestions(self) -> list[tuple[Song, str]]:
        """Songs whose printed title can be shortened, with the suggested title."""
        suggestions = []
        for song in self.game.playlist:
            shorter = clean_title(song.shown_title)
            if shorter != song.shown_title:
                suggestions.append((song, shorter))
        return suggestions

    def apply_cleanup(self, song_ids: list[str]) -> int:
        """Shorten the printed titles of these songs; returns how many changed."""
        wanted = set(song_ids)
        changes = [(song, shorter) for song, shorter in self.cleanup_suggestions() if song.id in wanted]
        with self._change():
            for song, shorter in changes:
                self._set_display_title(song, shorter)
        return len(changes)

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
            with self._change():
                cards = generate_for_game(self.game)
        except GenerationError as exc:
            raise ServiceError(str(exc)) from exc
        return cards
