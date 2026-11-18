"""Shared state of the running UI: the library and the PDF service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from muzbingo.services import Library

if TYPE_CHECKING:
    from muzbingo.services.pdf_service import PdfService


@dataclass
class AppContext:
    library: Library
    pdf: PdfService | None  # None when Qt WebEngine is not available (e.g. some tests)


_context: AppContext | None = None


def set_context(context: AppContext) -> None:
    global _context
    _context = context


def get() -> AppContext:
    if _context is None:
        raise RuntimeError("muzbingo.ui.app.setup() has not been called")
    return _context
