"""Start page: "My games"."""

from __future__ import annotations

from nicegui import events, ui

from muzbingo import settings
from muzbingo.i18n import _, current_language
from muzbingo.render import TemplateError, load_template
from muzbingo.services import LibraryError
from muzbingo.storage import FILE_EXTENSION
from muzbingo.ui import context
from muzbingo.ui.layout import frame, notify_error, safe_filename


def new_game_defaults() -> dict:
    """A new game starts with the last used template, grid and number of cards."""
    remembered = settings.get()
    defaults = {"rows": remembered.rows, "cols": remembered.cols, "n_cards": remembered.n_cards,
                "language": current_language()}
    try:
        load_template(remembered.template)
        defaults["template"] = remembered.template
    except TemplateError:
        pass  # e.g. a user template that was removed: keep the default
    return defaults


def register() -> None:
    @ui.page("/")
    def library_page() -> None:
        frame(_("My games"))
        library = context.get().library

        @ui.refreshable
        def games_list() -> None:
            summaries = library.list()
            if not summaries:
                with ui.card().classes("w-full items-center py-10"):
                    ui.icon("library_music", size="3em").classes("text-gray-400")
                    ui.label(_("No games yet. Create your first game to get started.")).classes(
                        "text-gray-600"
                    )
                return
            for summary in summaries:
                with ui.card().classes("w-full").mark("game-card"):
                    with ui.row().classes("w-full items-center no-wrap"):
                        with ui.column().classes("gap-0 grow cursor-pointer").on(
                            "click", lambda s=summary: ui.navigate.to(f"/game/{s.id}")
                        ):
                            ui.label(summary.title).classes("text-lg font-medium")
                            details = [
                                summary.event_date.strftime("%d/%m/%Y") if summary.event_date else None,
                                _("{n} songs").format(n=summary.n_songs),
                                _("{n} cards").format(n=summary.n_cards),
                            ]
                            ui.label(" · ".join(d for d in details if d)).classes("text-sm text-gray-600")
                        ui.button(
                            _("Open"), on_click=lambda s=summary: ui.navigate.to(f"/game/{s.id}")
                        ).props("unelevated")
                        with ui.button(icon="more_vert").props("flat round"):
                            with ui.menu():
                                ui.menu_item(_("Duplicate"), on_click=lambda s=summary: duplicate(s.id))
                                ui.menu_item(_("Download game file"), on_click=lambda s=summary: download(s))
                                ui.menu_item(_("Delete"), on_click=lambda s=summary: confirm_delete(s))

        def duplicate(game_id: str) -> None:
            try:
                library.duplicate(game_id)
            except LibraryError as exc:
                notify_error(str(exc))
            games_list.refresh()

        def download(summary) -> None:
            try:
                ui.download.content(
                    library.export_bytes(summary.id), safe_filename(summary.title, FILE_EXTENSION)
                )
            except LibraryError as exc:
                notify_error(str(exc))

        async def confirm_delete(summary) -> None:
            with ui.dialog() as dialog, ui.card():
                ui.label(_('Delete "{title}"?').format(title=summary.title)).classes("text-lg")
                ui.label(_("The game is moved to the trash folder in the MuzBingo data folder."))
                with ui.row().classes("w-full justify-end"):
                    ui.button(_("Cancel"), on_click=lambda: dialog.submit(False)).props("flat")
                    ui.button(_("Delete"), color="negative", on_click=lambda: dialog.submit(True))
            if await dialog:
                try:
                    library.delete(summary.id)
                except LibraryError as exc:
                    notify_error(str(exc))
                games_list.refresh()

        async def new_game() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label(_("New game")).classes("text-lg font-medium")
                title = ui.input(_("Title"), placeholder=_("e.g. Christmas party 2026")).classes(
                    "w-full"
                ).mark("new-title")
                title.on("keydown.enter", lambda: dialog.submit(title.value))
                with ui.row().classes("w-full justify-end"):
                    ui.button(_("Cancel"), on_click=lambda: dialog.submit(None)).props("flat")
                    ui.button(_("Create"), on_click=lambda: dialog.submit(title.value)).mark("create")
            name = await dialog
            if name is None:
                return
            game = library.create(name or _("Music Bingo"), **new_game_defaults())
            ui.navigate.to(f"/game/{game.id}?tab=playlist")

        async def import_game(e: events.UploadEventArguments) -> None:
            try:
                game = library.import_bytes(await e.file.read(), e.file.name)
            except LibraryError as exc:
                notify_error(str(exc))
                return
            finally:
                e.sender.reset()
            ui.notify(_('Imported "{title}"').format(title=game.title), type="positive")
            games_list.refresh()

        with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
            with ui.row().classes("w-full items-center"):
                ui.label(_("My games")).classes("text-2xl font-medium grow")
                ui.button(_("New game"), icon="add", on_click=new_game).props("unelevated").mark("new-game")
            games_list()
            with ui.expansion(_("Import a game file"), icon="upload_file").classes("w-full"):
                ui.label(
                    _("Add a {ext} file, for example one you downloaded on another computer.").format(
                        ext=FILE_EXTENSION
                    )
                ).classes("text-sm text-gray-600")
                ui.upload(label=_("Click + to choose a file, or drop it here"), on_upload=import_game, auto_upload=True).props(
                    f'accept="{FILE_EXTENSION}" flat bordered'
                ).classes("w-full")
