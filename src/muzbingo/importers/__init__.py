"""Import a playlist from a CSV or Excel file.

Typical use::

    try:
        result = import_playlist(path)
    except MappingRequired as e:
        # ask the user which of e.headers are title and artist, then:
        result = import_playlist(path, ColumnMapping(title=..., artist=...))
"""

from __future__ import annotations

from pathlib import Path

from muzbingo.importers.base import (
    ColumnMapping,
    ImportResult,
    MappingRequired,
    PlaylistImportError,
    detect_mapping,
    rows_to_songs,
)
from muzbingo.importers.csv_importer import read_csv
from muzbingo.importers.excel_importer import read_xlsx
from muzbingo.i18n import _

SUPPORTED_EXTENSIONS = (".csv", ".txt", ".xlsx", ".xlsm")

__all__ = [
    "ColumnMapping",
    "ImportResult",
    "MappingRequired",
    "PlaylistImportError",
    "SUPPORTED_EXTENSIONS",
    "detect_mapping",
    "import_playlist",
    "read_table",
]


def read_table(path: str | Path, sheet: str | None = None) -> tuple[list[str], list[list[str]]]:
    """Read any supported file into ``(headers, rows)``."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return read_csv(path)
    if suffix in (".xlsx", ".xlsm"):
        return read_xlsx(path, sheet)
    raise PlaylistImportError(_("Unsupported file type: {type}").format(type=suffix or path.name))


def import_playlist(
    path: str | Path, mapping: ColumnMapping | None = None, sheet: str | None = None
) -> ImportResult:
    headers, rows = read_table(path, sheet)
    return rows_to_songs(headers, rows, mapping)
