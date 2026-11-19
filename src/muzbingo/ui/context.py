"""Shared state of the running UI: the library and the PDF service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from muzbingo.services import GameService, Library

if TYPE_CHECKING:
    from muzbingo.services.pdf_service import PdfService


@dataclass
class AppContext:
    library: Library
    pdf: PdfService | None  # None when Qt WebEngine is not available (e.g. some tests)
    _services: dict[str, GameService] = field(default_factory=dict)

    def game_service(self, game_id: str) -> GameService:
        """The service of an open game, shared by all pages that show it.

        Keeping it for the whole session keeps the undo history when the page is
        reloaded or the user goes back to "My games" and opens the game again.
        Raises ``LibraryError`` when the game doesn't exist.
        """
        service = self._services.get(game_id)
        if service is None or not service.is_current:
            service = GameService.open(self.library, game_id)
            self._services[game_id] = service
        return service


_context: AppContext | None = None


def set_context(context: AppContext) -> None:
    global _context
    _context = context


def get() -> AppContext:
    if _context is None:
        raise RuntimeError("muzbingo.ui.app.setup() has not been called")
    return _context
