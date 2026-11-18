"""Read a CSV file (e.g. a Spotify/Exportify export) into headers and rows."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from muzbingo.importers.base import PlaylistImportError

ENCODINGS = ("utf-8-sig", "cp1252")
DELIMITERS = ",;\t"


def _decode(raw: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise PlaylistImportError("Unknown text encoding (expected UTF-8 or Windows-1252)")


def _delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except csv.Error:
        # Fall back to whichever candidate appears most in the header line.
        header = text.splitlines()[0] if text else ""
        return max(DELIMITERS, key=header.count)


def read_csv(path: str | Path) -> tuple[list[str], list[list[str]]]:
    text = _decode(Path(path).read_bytes())
    if not text.strip():
        raise PlaylistImportError("The file is empty")
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(text)))
    headers = [h.strip() for h in rows[0]]
    return headers, rows[1:]
