"""Domain model: Game, Song, Card and Image, plus (de)serialisation to plain dicts.

The dict form is what ``storage`` writes as JSON. Keep ``FORMAT_VERSION`` in sync
with any change to that form, and add a migration in ``storage`` when it changes.
"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def make_song_id(artist: str, title: str) -> str:
    """Stable id for a song without a Spotify URI, derived from the original texts."""
    key = f"{artist.strip().casefold()}\x1f{title.strip().casefold()}"
    return "h:" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def new_seed() -> int:
    return random.SystemRandom().randrange(1, 1_000_000)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Song:
    title: str
    artist: str
    id: str = ""
    display_title: str | None = None
    display_artist: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = make_song_id(self.artist, self.title)

    @property
    def shown_title(self) -> str:
        """Text printed on the card: the edited title if set, else the original."""
        return self.display_title if self.display_title else self.title

    @property
    def shown_artist(self) -> str:
        return self.display_artist if self.display_artist else self.artist

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "title": self.title, "artist": self.artist}
        if self.display_title:
            d["display_title"] = self.display_title
        if self.display_artist:
            d["display_artist"] = self.display_artist
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Song:
        return cls(
            id=d["id"],
            title=d["title"],
            artist=d["artist"],
            display_title=d.get("display_title"),
            display_artist=d.get("display_artist"),
            extra=dict(d.get("extra", {})),
        )


@dataclass
class Card:
    number: int
    cells: list[list[str]]  # song ids, rows × cols

    @property
    def song_ids(self) -> list[str]:
        return [sid for row in self.cells for sid in row]

    def to_dict(self) -> dict[str, Any]:
        return {"number": self.number, "cells": self.cells}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Card:
        return cls(number=int(d["number"]), cells=[list(row) for row in d["cells"]])


@dataclass
class Image:
    filename: str
    mime: str
    data: bytes

    @classmethod
    def from_file(cls, path: str | Path) -> Image:
        path = Path(path)
        mime = IMAGE_MIME_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
        if not mime or not mime.startswith("image/"):
            raise ValueError(f"Not a supported image file: {path.name}")
        return cls(filename=path.name, mime=mime, data=path.read_bytes())

    @property
    def suffix(self) -> str:
        for suffix, mime in IMAGE_MIME_TYPES.items():
            if mime == self.mime and suffix != ".jpeg":
                return suffix
        return Path(self.filename).suffix or ".img"

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "mime": self.mime,
            "data": base64.b64encode(self.data).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Image:
        return cls(filename=d["filename"], mime=d["mime"], data=base64.b64decode(d["data"]))


@dataclass
class Game:
    title: str = "Music Bingo"
    rows: int = 4
    cols: int = 5
    n_cards: int = 30
    event_date: date | None = None
    seed: int = field(default_factory=new_seed)
    language: str = "en"
    template: str = "classic"
    background: Image | None = None
    logo: Image | None = None
    playlist: list[Song] = field(default_factory=list)
    cards: list[Card] = field(default_factory=list)
    played: list[str] = field(default_factory=list)
    cards_basis: str | None = None  # basis() at the moment the cards were generated
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def songs_per_card(self) -> int:
        return self.rows * self.cols

    def songs_by_id(self) -> dict[str, Song]:
        return {song.id: song for song in self.playlist}

    def card(self, number: int) -> Card | None:
        return next((c for c in self.cards if c.number == number), None)

    def basis(self) -> str:
        """Fingerprint of everything the cards depend on.

        Display texts, title, date, pictures and template are not part of it: changing
        those only changes how the cards look, not which songs are on them.
        """
        ids = "\x1f".join(sorted(s.id for s in self.playlist))
        key = f"{self.rows}x{self.cols}|{self.n_cards}|{self.seed}|{ids}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    @property
    def cards_outdated(self) -> bool:
        """True if cards exist but the songs, grid, card count or seed changed since."""
        return bool(self.cards) and self.cards_basis != self.basis()

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": FORMAT_VERSION,
            "id": self.id,
            "title": self.title,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "rows": self.rows,
            "cols": self.cols,
            "n_cards": self.n_cards,
            "seed": self.seed,
            "language": self.language,
            "template": self.template,
            "background": self.background.to_dict() if self.background else None,
            "logo": self.logo.to_dict() if self.logo else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "playlist": [s.to_dict() for s in self.playlist],
            "cards": [c.to_dict() for c in self.cards],
            "played": list(self.played),
            "cards_basis": self.cards_basis,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Game:
        return cls(
            id=d["id"],
            title=d["title"],
            event_date=date.fromisoformat(d["event_date"]) if d.get("event_date") else None,
            rows=int(d["rows"]),
            cols=int(d["cols"]),
            n_cards=int(d.get("n_cards") or len(d.get("cards", [])) or 30),
            seed=int(d["seed"]),
            language=d.get("language", "en"),
            template=d.get("template", "classic"),
            background=Image.from_dict(d["background"]) if d.get("background") else None,
            logo=Image.from_dict(d["logo"]) if d.get("logo") else None,
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            playlist=[Song.from_dict(s) for s in d.get("playlist", [])],
            cards=[Card.from_dict(c) for c in d.get("cards", [])],
            played=list(d.get("played", [])),
            cards_basis=d.get("cards_basis"),
        )
