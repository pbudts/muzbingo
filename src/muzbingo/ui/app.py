"""Register the MuzBingo pages and routes on NiceGUI's app.

Kept separate from ``server.py`` so tests can set up the UI in NiceGUI's simulated
environment without starting a real server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import app

from muzbingo.services import Library
from muzbingo.ui import context, routes
from muzbingo.ui.pages import game, library

if TYPE_CHECKING:
    from muzbingo.services.pdf_service import PdfService


def setup(library_: Library, pdf: PdfService | None) -> None:
    context.set_context(context.AppContext(library=library_, pdf=pdf))
    routes.register(app)
    library.register()
    game.register()
