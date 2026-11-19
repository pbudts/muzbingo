"""Shared import logic: column detection, normalisation and deduplication.

The file readers (CSV, Excel) only turn a file into ``headers`` + ``rows`` of strings;
everything else happens here, so both formats behave identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from muzbingo.models import Song
from muzbingo.i18n import _

TITLE_ALIASES = ("track name", "title", "song", "song title", "titel", "name", "naam")
ARTIST_ALIASES = ("artist name(s)", "artist", "artists", "artist name", "artiest", "artiesten", "performer")
ID_ALIASES = ("track uri", "spotify uri", "uri")


class PlaylistImportError(Exception):
    """The file could not be read as a playlist."""


class MappingRequired(PlaylistImportError):
    """The title/artist columns could not be detected; the user has to choose them."""

    def __init__(self, headers: list[str], preview: list[list[str]]):
        super().__init__("Could not detect the title and artist columns")
        self.headers = headers
        self.preview = preview


@dataclass
class ColumnMapping:
    title: str
    artist: str
    id: str | None = None


@dataclass
class ImportResult:
    songs: list[Song]
    mapping: ColumnMapping
    headers: list[str]
    warnings: list[str] = field(default_factory=list)


def _norm_header(h: str) -> str:
    return " ".join(h.strip().casefold().split())


def _find(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    by_norm = {_norm_header(h): h for h in reversed(headers)}  # first occurrence wins
    for alias in aliases:
        if alias in by_norm:
            return by_norm[alias]
    return None


def detect_mapping(headers: list[str]) -> ColumnMapping | None:
    title = _find(headers, TITLE_ALIASES)
    artist = _find(headers, ARTIST_ALIASES)
    if not title or not artist or title == artist:
        return None
    return ColumnMapping(title=title, artist=artist, id=_find(headers, ID_ALIASES))


def normalise_text(text: str) -> str:
    return " ".join(text.split())


def normalise_artist(text: str) -> str:
    """Keep all artist names, joined with ", ".

    Spotify exports separate several artists with ";". Commas are left alone, because
    they also occur inside single names ("Earth, Wind & Fire").
    """
    parts = [normalise_text(p) for p in text.split(";")]
    return ", ".join(p for p in parts if p)


def rows_to_songs(
    headers: list[str], rows: list[list[str]], mapping: ColumnMapping | None
) -> ImportResult:
    if mapping is None:
        mapping = detect_mapping(headers)
        if mapping is None:
            raise MappingRequired(headers, rows[:10])

    index = {h: i for i, h in reversed(list(enumerate(headers)))}
    for column in (mapping.title, mapping.artist, mapping.id):
        if column is not None and column not in index:
            raise PlaylistImportError(_("Column not found: {column}").format(column=repr(column)))

    def cell(row: list[str], column: str | None) -> str:
        if column is None:
            return ""
        i = index[column]
        return row[i] if i < len(row) else ""

    songs: list[Song] = []
    warnings: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()

    for line_no, row in enumerate(rows, start=2):  # row 1 is the header
        if not any(c.strip() for c in row):
            continue
        title = normalise_text(cell(row, mapping.title))
        artist = normalise_artist(cell(row, mapping.artist))
        if not title or not artist:
            warnings.append(f"Row {line_no}: skipped, missing title or artist")
            continue
        song = Song(title=title, artist=artist, id=cell(row, mapping.id).strip())
        key = (artist.casefold(), title.casefold())
        if key in seen_keys or song.id in seen_ids:
            warnings.append(f"Row {line_no}: skipped duplicate '{artist} – {title}'")
            continue
        seen_keys.add(key)
        seen_ids.add(song.id)
        songs.append(song)

    if not songs:
        raise PlaylistImportError(_("No songs found in the file"))
    return ImportResult(songs=songs, mapping=mapping, headers=headers, warnings=warnings)
