"""User settings, stored as JSON in the data folder (``settings.json``).

Holds the UI language and the choices that new games start with (the last used
template, grid and number of cards). A broken or missing file gives the defaults;
the app never fails to start because of its settings.
"""

from __future__ import annotations

import json
import locale
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from muzbingo import paths
from muzbingo.i18n import LANGUAGES


@dataclass
class Settings:
    ui_language: str | None = None  # None: follow the system language
    template: str = "classic"
    rows: int = 4
    cols: int = 5
    n_cards: int = 30

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        defaults = cls()
        if settings.ui_language not in (None, *LANGUAGES):
            settings.ui_language = None
        for name in ("rows", "cols", "n_cards"):
            if not isinstance(getattr(settings, name), int) or getattr(settings, name) < 1:
                setattr(settings, name, getattr(defaults, name))
        if not isinstance(settings.template, str) or not settings.template:
            settings.template = defaults.template
        return settings

    def language(self) -> str:
        """The UI language to use: the chosen one, else the system's, else English."""
        return self.ui_language or system_language()


def system_language() -> str:
    candidates = [os.environ.get(name, "") for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for value in candidates:
        value = value.lower()
        if value.startswith(("nl", "dutch")):  # Windows reports e.g. "Dutch_Belgium"
            return "nl"
        if value and not value.startswith(("c", "posix")):
            return "en"
    return "en"


_current: Settings | None = None


def load(path: Path | None = None) -> Settings:
    path = path or paths.settings_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Settings.from_dict(data if isinstance(data, dict) else {})
    except (OSError, ValueError, TypeError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> None:
    path = path or paths.settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(settings), f, indent=2)
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def get() -> Settings:
    """The settings of this run, loaded on first use."""
    global _current
    if _current is None:
        _current = load()
    return _current


def update(**changes) -> Settings:
    """Change and save settings; saving problems are ignored (settings are a convenience)."""
    settings = get()
    for name, value in changes.items():
        if not hasattr(settings, name):
            raise AttributeError(name)
        setattr(settings, name, value)
    try:
        save(settings)
    except OSError:
        pass
    return settings


def reset() -> None:
    """Forget the loaded settings (after the data folder changed, and in tests)."""
    global _current
    _current = None
