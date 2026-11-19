"""Game page: tabs for settings, playlist and cards."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import events, ui

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
        self._listeners: list[Callable[[], None]] = []  # of the panels; reset when they are rebuilt
        self._page_listeners: list[Callable[[], None]] = []  # of the page frame (title, undo buttons)
        self.rebuild: Callable[[], Any] = lambda: None

    def on_change(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def on_any_change(self, listener: Callable[[], None]) -> None:
        """Like ``on_change``, for parts of the page that are not rebuilt."""
        self._page_listeners.append(listener)

    def changed(self) -> None:
        """Call after any change, so every panel can update what it shows."""
        for listener in [*self._listeners, *self._page_listeners]:
            listener()

    def reset_listeners(self) -> None:
        self._listeners.clear()

    async def undo(self) -> None:
        if self.service.undo():
            await self._after_history_step()
        else:
            ui.notify(_("Nothing to undo"))

    async def redo(self) -> None:
        if self.service.redo():
            await self._after_history_step()
        else:
            ui.notify(_("Nothing to redo"))

    async def _after_history_step(self) -> None:
        # Any setting may have changed, so rebuild the panels instead of patching them.
        result = self.rebuild()
        if result is not None:
            await result
        for listener in self._page_listeners:
            listener()


def register() -> None:
    from muzbingo.ui.components.cards_panel import cards_panel
    from muzbingo.ui.components.playlist_panel import playlist_panel
    from muzbingo.ui.components.settings_panel import settings_panel

    @ui.page("/game/{game_id}")
    def game_page(game_id: str, tab: str = "settings") -> None:
        try:
            service = context.get().game_service(game_id)
        except LibraryError as exc:
            frame(back=True)
            with ui.column().classes("w-full max-w-3xl mx-auto p-4"):
                ui.label(str(exc)).classes("text-lg")
                ui.button(_("Back to My games"), on_click=lambda: ui.navigate.to("/"))
            return

        tab = tab if tab in TABS else "settings"
        page = GamePage(service, tab)
        title_label = frame(service.game.title, back=True, actions=lambda: history_buttons(page))
        if title_label is not None:
            page.on_any_change(lambda: title_label.set_text(service.game.title))
        ui.keyboard(on_key=lambda e: on_key(page, e))

        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-2"):
            with ui.tabs().classes("w-full").props("align=left") as tabs:
                ui.tab("settings", _("Settings"), icon="tune")
                ui.tab("playlist", _("Playlist"), icon="queue_music")
                ui.tab("cards", _("Cards"), icon="grid_view")

            @ui.refreshable
            def panels() -> None:
                page.reset_listeners()
                with ui.tab_panels(tabs, value=tabs.value).classes(
                    "w-full bg-transparent"
                ).props("animated=false"):
                    with ui.tab_panel("settings").classes("p-0"):
                        settings_panel(page)
                    with ui.tab_panel("playlist").classes("p-0"):
                        playlist_panel(page)
                    with ui.tab_panel("cards").classes("p-0"):
                        cards_panel(page)

            tabs.set_value(tab)
            page.rebuild = panels.refresh
            panels()


def history_buttons(page: GamePage) -> None:
    undo = ui.button(icon="undo", on_click=page.undo).props("flat round color=white").mark("undo")
    undo.tooltip(_("Undo (Ctrl+Z)"))
    redo = ui.button(icon="redo", on_click=page.redo).props("flat round color=white").mark("redo")
    redo.tooltip(_("Redo (Ctrl+Y)"))

    def update() -> None:
        undo.set_enabled(page.service.can_undo)
        redo.set_enabled(page.service.can_redo)

    page.on_any_change(update)
    update()


async def on_key(page: GamePage, e: events.KeyEventArguments) -> None:
    # ui.keyboard ignores keys typed in input fields, so text fields keep their own undo.
    if not e.action.keydown or not (e.modifiers.ctrl or e.modifiers.meta) or e.action.repeat:
        return
    key = e.key.name.lower()
    if key == "z" and not e.modifiers.shift:
        await page.undo()
    elif key == "y" or (key == "z" and e.modifiers.shift):
        await page.redo()
