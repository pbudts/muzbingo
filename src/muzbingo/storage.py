"""Save and load games as ``.muzbingo`` files (UTF-8 JSON)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from muzbingo.models import FORMAT_VERSION, Game, utc_now

FILE_EXTENSION = ".muzbingo"


class StorageError(Exception):
    """The game file could not be read or written."""


def game_to_json(game: Game) -> str:
    return json.dumps(game.to_dict(), ensure_ascii=False, indent=2)


def game_from_json(text: str | bytes, name: str = "game file") -> Game:
    """Parse a game file's contents. ``name`` is only used in error messages."""
    try:
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageError(f"Could not read {name}: {exc}") from exc

    version = data.get("format_version") if isinstance(data, dict) else None
    if not isinstance(version, int):
        raise StorageError(f"{name} is not a MuzBingo game file")
    if version > FORMAT_VERSION:
        raise StorageError(f"{name} was made with a newer version of MuzBingo; please update the app")
    # Future: migrate older versions here, one step at a time.
    try:
        return Game.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise StorageError(f"{name} is damaged: {exc}") from exc


def save_game(game: Game, path: str | Path) -> Path:
    """Write the game atomically: a crash mid-save never leaves a half-written file."""
    path = Path(path)
    game.updated_at = utc_now()
    text = game_to_json(game)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise StorageError(f"Could not save {path.name}: {exc}") from exc
    return path


def load_game(path: str | Path) -> Game:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StorageError(f"Could not read {path.name}: {exc}") from exc
    return game_from_json(raw, path.name)
