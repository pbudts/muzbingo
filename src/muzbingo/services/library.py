"""The "My games" library: one ``.muzbingo`` file per game in a folder.

Games are saved on every change (autosave), so there is no "save as" or unsaved
state. Deleted games are moved to ``trash/`` rather than removed.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from muzbingo.models import Game, utc_now
from muzbingo.storage import FILE_EXTENSION, StorageError, game_from_json, game_to_json, load_game, save_game

_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class LibraryError(Exception):
    """A library operation failed (unknown game, unreadable file, ...)."""


@dataclass(frozen=True)
class GameSummary:
    id: str
    title: str
    event_date: date | None
    n_songs: int
    n_cards: int
    updated_at: datetime


class Library:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.trash = self.root / "trash"
        self._summaries: dict[Path, tuple[float, GameSummary]] = {}

    # -- paths -------------------------------------------------------------

    def path_for(self, game_id: str) -> Path:
        if not _ID_RE.match(game_id or ""):
            raise LibraryError(f"Invalid game id: {game_id!r}")
        return self.root / f"{game_id}{FILE_EXTENSION}"

    def exists(self, game_id: str) -> bool:
        try:
            return self.path_for(game_id).is_file()
        except LibraryError:
            return False

    def version(self, game_id: str) -> int | None:
        """Changes whenever the game file is written; None if the game doesn't exist."""
        try:
            return self.path_for(game_id).stat().st_mtime_ns
        except (OSError, LibraryError):
            return None

    # -- reading -----------------------------------------------------------

    def list(self) -> list[GameSummary]:
        """All games, most recently changed first. Unreadable files are skipped."""
        if not self.root.is_dir():
            return []
        summaries = []
        for path in self.root.glob(f"*{FILE_EXTENSION}"):
            mtime = path.stat().st_mtime
            cached = self._summaries.get(path)
            if cached and cached[0] == mtime:
                summaries.append(cached[1])
                continue
            try:
                game = load_game(path)
            except StorageError:
                continue
            summary = GameSummary(
                id=game.id,
                title=game.title,
                event_date=game.event_date,
                n_songs=len(game.playlist),
                n_cards=len(game.cards),
                updated_at=game.updated_at,
            )
            self._summaries[path] = (mtime, summary)
            summaries.append(summary)
        return sorted(summaries, key=lambda s: s.updated_at, reverse=True)

    def load(self, game_id: str) -> Game:
        path = self.path_for(game_id)
        if not path.is_file():
            raise LibraryError("This game does not exist (anymore)")
        try:
            return load_game(path)
        except StorageError as exc:
            raise LibraryError(str(exc)) from exc

    def export_bytes(self, game_id: str) -> bytes:
        return game_to_json(self.load(game_id)).encode("utf-8")

    # -- writing -----------------------------------------------------------

    def save(self, game: Game) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            save_game(game, self.path_for(game.id))
        except StorageError as exc:
            raise LibraryError(str(exc)) from exc

    def create(self, title: str, **fields) -> Game:
        game = Game(title=title.strip() or "Music Bingo", **fields)
        self.save(game)
        return game

    def duplicate(self, game_id: str) -> Game:
        """Copy a game (e.g. last year's party): new id, cards kept, played songs cleared."""
        game = self.load(game_id)
        game.id = str(uuid.uuid4())
        game.title = f"{game.title} (copy)"
        game.played = []
        game.created_at = utc_now()
        self.save(game)
        return game

    def import_bytes(self, data: bytes, name: str = "game file") -> Game:
        """Add a game from a downloaded ``.muzbingo`` file.

        If a game with the same id is already in the library, the import gets a new id,
        so it never overwrites anything.
        """
        try:
            game = game_from_json(data, name)
        except StorageError as exc:
            raise LibraryError(str(exc)) from exc
        if not _ID_RE.match(game.id) or self.exists(game.id):
            game.id = str(uuid.uuid4())
        self.save(game)
        return game

    def delete(self, game_id: str) -> None:
        """Move the game to the trash folder."""
        path = self.path_for(game_id)
        if not path.is_file():
            raise LibraryError("This game does not exist (anymore)")
        self.trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        os.replace(path, self.trash / f"{game_id}-{stamp}{FILE_EXTENSION}")
        self._summaries.pop(path, None)
