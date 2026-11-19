"""Register the MuzBingo pages and routes on NiceGUI's app.

Kept separate from ``server.py`` so tests can set up the UI in NiceGUI's simulated
environment without starting a real server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import app

from muzbingo import settings
from muzbingo.i18n import set_language
from muzbingo.services import Library
from muzbingo.ui import context, routes
from muzbingo.ui.pages import game, library

if TYPE_CHECKING:
    from muzbingo.services.pdf_service import PdfService


QUASAR_LANGUAGES = {"en": "en-GB", "nl": "nl"}


def apply_language(language: str) -> None:
    """Use ``language`` for the UI from the next page load on (our texts and Quasar's)."""
    set_language(language)
    app.config.language = QUASAR_LANGUAGES.get(language, "en-GB")


def setup(library_: Library, pdf: PdfService | None) -> None:
    apply_language(settings.get().language())
    context.set_context(context.AppContext(library=library_, pdf=pdf))
    routes.register(app)
    library.register()
    game.register()
