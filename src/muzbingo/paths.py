"""Where MuzBingo finds its bundled files and keeps user data.

Works the same when running from source and from a PyInstaller build. Deliberately
free of Qt, so the core and its tests don't need a Qt installation.

Portable mode: in a frozen (built) app, a ``portable.txt`` file next to the
executable makes all user data live in a ``data/`` folder beside it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MuzBingo"

_data_dir_override: Path | None = None


def set_data_dir(path: Path | None) -> None:
    """Use ``path`` as the data folder (``muzbingo serve --data-dir``), or the default again."""
    global _data_dir_override
    _data_dir_override = Path(path).resolve() if path else None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def package_dir() -> Path:
    """Folder holding the ``muzbingo`` package files (templates, translations)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "muzbingo"
    return Path(__file__).resolve().parent


def app_dir() -> Path:
    """Folder of the executable (frozen) or of the project checkout (source)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def is_portable() -> bool:
    return is_frozen() and (app_dir() / "portable.txt").exists()


def user_data_dir() -> Path:
    if _data_dir_override is not None:
        return _data_dir_override
    if is_portable():
        return app_dir() / "data"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def bundled_templates_dir() -> Path:
    return package_dir() / "templates"


def user_templates_dir() -> Path:
    return user_data_dir() / "templates"


def template_search_path() -> list[Path]:
    """User templates first, so a user template can override a bundled one by name."""
    return [user_templates_dir(), bundled_templates_dir()]


def games_dir(data_dir: Path | None = None) -> Path:
    return (data_dir or user_data_dir()) / "games"


def settings_file(data_dir: Path | None = None) -> Path:
    return (data_dir or user_data_dir()) / "settings.json"
