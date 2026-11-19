"""Read an Excel workbook (.xlsx / .xlsm) into headers and rows."""

from __future__ import annotations

from pathlib import Path

from muzbingo.importers.base import PlaylistImportError
from muzbingo.i18n import _


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def read_xlsx(path: str | Path, sheet: str | None = None) -> tuple[list[str], list[list[str]]]:
    from openpyxl import load_workbook  # imported lazily: only needed for Excel files

    try:
        workbook = load_workbook(Path(path), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several unrelated exception types
        raise PlaylistImportError(_("Could not open the Excel file: {error}").format(error=exc)) from exc
    try:
        if sheet is not None and sheet not in workbook.sheetnames:
            raise PlaylistImportError(_("Sheet not found: {sheet}").format(sheet=repr(sheet)))
        worksheet = workbook[sheet] if sheet else workbook.worksheets[0]
        rows = [[_to_text(v) for v in row] for row in worksheet.iter_rows(values_only=True)]
    finally:
        workbook.close()

    # The header is the first non-empty row; this allows a title row or blank rows above it.
    while rows and not any(c.strip() for c in rows[0]):
        rows.pop(0)
    if not rows:
        raise PlaylistImportError(_("The sheet is empty"))
    headers = [h.strip() for h in rows[0]]
    return headers, rows[1:]
