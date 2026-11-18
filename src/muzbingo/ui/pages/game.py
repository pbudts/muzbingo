"""Game page: tabs for settings, playlist and cards."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from muzbingo.i18n import _
from muzbingo.services import GameService, LibraryError
from muzbingo.ui import context
from muzbingo.ui.layout import frame

TABS = ("settings", "playlist", "cards")


class GamePage:
    """State shared by the panels of one open game page."""

    def __init__(self, service: GameService, initial_tab: str = "settings"):
        self.service = service
        self.initial_tab = initial_tab
        self._listeners: list[Callable[[], None]] = []

    def on_change(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def changed(self) -> None:
        """Call after any change, so every panel can update what it shows."""
        for listener in self._listeners:
            listener()


def register() -> None:
    from muzbingo.ui.components.cards_panel import cards_panel
    from muzbingo.ui.components.playlist_panel import playlist_panel
    from muzbingo.ui.components.settings_panel import settings_panel

    @ui.page("/game/{game_id}")
    def game_page(game_id: str, tab: str = "settings") -> None:
        try:
            service = GameService.open(context.get().library, game_id)
        except LibraryError as exc:
            frame(back=True)
            with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
                ui.label(str(exc)).classes("text-lg")
                ui.button(_("Back to My games"), on_click=lambda: ui.navigate.to("/"))
            return

        tab = tab if tab in TABS else "settings"
        title_label = frame(service.game.title, back=True)
        page = GamePage(service, tab)
        if title_label is not None:
            page.on_change(lambda: title_label.set_text(service.game.title))

        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-2"):
            with ui.tabs().classes("w-full").props("align=left") as tabs:
                ui.tab("settings", _("Settings"), icon="tune")
                ui.tab("playlist", _("Playlist"), icon="queue_music")
                ui.tab("cards", _("Cards"), icon="grid_view")
            with ui.tab_panels(tabs, value=tab).classes(
                "w-full bg-transparent"
            ).props("animated=false"):
                with ui.tab_panel("settings").classes("p-0"):
                    settings_panel(page)
                with ui.tab_panel("playlist").classes("p-0"):
                    playlist_panel(page)
                with ui.tab_panel("cards").classes("p-0"):
                    cards_panel(page)
