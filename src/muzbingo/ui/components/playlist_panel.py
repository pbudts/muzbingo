"""Playlist tab: import, editable song table with length warnings, add/delete songs."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import events, ui

from muzbingo.i18n import _
from muzbingo.importers import SUPPORTED_EXTENSIONS, ColumnMapping, MappingRequired, PlaylistImportError
from muzbingo.render import TemplateError
from muzbingo.services import ServiceError
from muzbingo.ui.layout import notify_error

if TYPE_CHECKING:
    from muzbingo.ui.pages.game import GamePage


def playlist_panel(page: GamePage) -> None:
    service = page.service
    state = {"only_warnings": False}

    def too_long(song) -> bool:
        try:
            return service.too_long(song)
        except TemplateError:
            return False

    def row_data() -> list[dict]:
        rows = []
        for n, song in enumerate(service.game.playlist, start=1):
            warn = too_long(song)
            if state["only_warnings"] and not warn:
                continue
            edited = bool(song.display_title or song.display_artist)
            rows.append(
                {
                    "id": song.id,
                    "n": n,
                    "title": song.shown_title,
                    "artist": song.shown_artist,
                    "warn": "⚠" if warn else "",
                    "original": f"{song.title} — {song.artist}" if edited else "",
                }
            )
        return rows

    @ui.refreshable
    def status() -> None:
        s = service.playlist_status()
        n_warn = sum(1 for song in service.game.playlist if too_long(song))
        with ui.row().classes("w-full items-center gap-4"):
            ui.label(_("{n} songs").format(n=s.n_songs)).classes("text-base font-medium").mark("song-count")
            ui.label(_("{needed} per card").format(needed=s.needed)).classes("text-sm text-gray-600")
            if n_warn:
                ui.label(
                    _("⚠ {n} too long for a cell: click a title or artist to shorten it").format(n=n_warn)
                ).classes("text-sm text-orange-800")
        if s.message:
            color = "bg-red-50 text-red-900" if not s.can_generate else "bg-amber-50 text-amber-900"
            ui.label(s.message).classes(f"w-full rounded px-3 py-2 text-sm {color}")

    def empty_text() -> str:
        if service.game.playlist and state["only_warnings"]:
            return _('All texts fit on the cards. Switch off "Only songs that are too long" to see all songs.')
        return _("No songs yet. Import a playlist to get started.")

    def refresh() -> None:
        grid.options["rowData"] = row_data()
        grid.options["overlayNoRowsTemplate"] = empty_text()
        grid.update()
        status.refresh()

    page.on_change(refresh)  # e.g. a new grid size changes which texts are too long

    # -- actions --------------------------------------------------------------

    def on_cell_edited(e: events.GenericEventArguments) -> None:
        column, data = e.args.get("colId"), e.args.get("data") or {}
        if column not in ("title", "artist"):
            return
        try:
            service.edit_song(data["id"], **{column: e.args.get("newValue") or ""})
        except ServiceError as exc:
            notify_error(str(exc))
        page.changed()

    async def selected_ids() -> list[str]:
        rows = await grid.get_selected_rows()
        if not rows:
            ui.notify(_("Select songs first, with the checkboxes in front of them."))
        return [row["id"] for row in rows]

    async def reset_selected() -> None:
        for song_id in await selected_ids():
            service.reset_song(song_id)
        page.changed()

    async def delete_selected() -> None:
        ids = await selected_ids()
        if not ids:
            return
        on_cards = service.songs_on_cards() & set(ids)
        with ui.dialog() as dialog, ui.card():
            ui.label(_("Delete {n} songs?").format(n=len(ids))).classes("text-lg")
            if on_cards:
                ui.label(
                    _("{n} of them are on the generated cards; you will need to generate new cards.").format(
                        n=len(on_cards)
                    )
                ).classes("text-orange-800")
            with ui.row().classes("w-full justify-end"):
                ui.button(_("Cancel"), on_click=lambda: dialog.submit(False)).props("flat")
                ui.button(_("Delete"), color="negative", on_click=lambda: dialog.submit(True))
        if await dialog:
            for song_id in ids:
                service.delete_song(song_id)
            page.changed()

    async def add_song() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(_("Add a song")).classes("text-lg font-medium")
            title = ui.input(_("Title")).classes("w-full")
            artist = ui.input(_("Artist")).classes("w-full")
            with ui.row().classes("w-full justify-end"):
                ui.button(_("Cancel"), on_click=lambda: dialog.submit(False)).props("flat")
                ui.button(_("Add"), on_click=lambda: dialog.submit(True))
        if await dialog:
            try:
                service.add_song(title.value, artist.value)
            except ServiceError as exc:
                notify_error(str(exc))
            page.changed()

    def toggle_warnings(value: bool) -> None:
        state["only_warnings"] = value
        refresh()

    # -- layout ---------------------------------------------------------------

    with ui.card().classes("w-full gap-3"):
        status()
        with ui.row().classes("w-full items-center gap-2"):
            ui.button(_("Import playlist"), icon="upload_file", on_click=lambda: import_dialog(page)).props(
                "unelevated"
            ).mark("import-playlist")
            ui.button(_("Add song"), icon="add", on_click=add_song).props("flat")
            ui.button(_("Use original text"), icon="restart_alt", on_click=reset_selected).props("flat").tooltip(
                _("Print the original title and artist again for the selected songs")
            )
            ui.button(_("Delete"), icon="delete", on_click=delete_selected).props("flat")
            ui.space()
            ui.switch(_("Only songs that are too long"), on_change=lambda e: toggle_warnings(e.value)).mark(
                "only-too-long"
            )

        grid = ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "#", "field": "n", "width": 70, "sortable": True},
                    {"headerName": _("Title (on the card)"), "field": "title", "editable": True, "flex": 3,
                     "sortable": True},
                    {"headerName": _("Artist (on the card)"), "field": "artist", "editable": True, "flex": 2,
                     "sortable": True},
                    {"headerName": "", "field": "warn", "width": 50,
                     "headerTooltip": _("Too long for a cell")},
                    {"headerName": _("Original (if edited)"), "field": "original", "flex": 3,
                     "cellStyle": {"color": "#777", "fontSize": "12px"}},
                ],
                "rowData": row_data(),
                "rowSelection": {"mode": "multiRow"},
                ":getRowId": "params => params.data.id",
                "stopEditingWhenCellsLoseFocus": True,
                "singleClickEdit": True,
                "overlayNoRowsTemplate": empty_text(),
            },
            theme="quartz",
        ).classes("w-full").style("height: 60vh").mark("playlist-grid")
        grid.on("cellValueChanged", on_cell_edited)
        ui.label(
            _("Click a title or artist to change what is printed on the cards. The original stays saved.")
        ).classes("text-xs text-gray-500")

    if not service.game.playlist and page.initial_tab == "playlist":
        ui.timer(0.3, lambda: import_dialog(page), once=True)


async def import_dialog(page: GamePage) -> None:
    """Upload a playlist file; ask for the columns if they can't be detected."""
    service = page.service
    tmp_dir = Path(tempfile.mkdtemp(prefix="muzbingo-import-"))
    state: dict = {"path": None}

    with ui.dialog() as dialog, ui.card().classes("w-[40rem] max-w-full gap-3"):
        ui.label(_("Import playlist")).classes("text-lg font-medium")
        ui.markdown(
            _(
                "Choose a **CSV** or **Excel** file with a title and an artist column.\n\n"
                "From Spotify: export the playlist as CSV, for example with "
                "[Exportify](https://exportify.app), and choose that file here."
            )
        ).classes("text-sm")
        append = ui.checkbox(_("Add to the current playlist instead of replacing it"))
        append.set_visibility(bool(service.game.playlist))
        if service.game.cards:
            ui.label(
                _("After the import you will need to generate new cards.")
            ).classes("text-sm text-orange-800")
        mapping_area = ui.column().classes("w-full")
        ui.upload(label=_("Click + to choose a file, or drop it here"), on_upload=lambda e: on_upload(e), auto_upload=True).props(
            f'accept="{",".join(SUPPORTED_EXTENSIONS)}" flat bordered'
        ).classes("w-full").mark("playlist-upload")
        with ui.row().classes("w-full justify-end"):
            ui.button(_("Close"), on_click=dialog.close).props("flat")

    async def on_upload(e: events.UploadEventArguments) -> None:
        path = tmp_dir / Path(e.file.name).name
        await e.file.save(path)
        e.sender.reset()
        state["path"] = path
        run_import(None)

    def run_import(mapping: ColumnMapping | None) -> None:
        try:
            result = service.import_playlist(state["path"], mapping, append=append.value)
        except MappingRequired as exc:
            ask_mapping(exc)
            return
        except (PlaylistImportError, ServiceError) as exc:
            notify_error(str(exc))
            return
        message = _("Imported {n} songs.").format(n=len(result.songs))
        if result.warnings:
            message += " " + _("{n} rows were skipped (empty or duplicate).").format(n=len(result.warnings))
        ui.notify(message, type="positive", multi_line=True)
        dialog.close()
        page.changed()

    def ask_mapping(exc: MappingRequired) -> None:
        mapping_area.clear()
        with mapping_area:
            ui.label(_("Which columns hold the song title and the artist?")).classes("font-medium")
            with ui.row().classes("w-full no-wrap gap-2"):
                title = ui.select(exc.headers, label=_("Title column")).classes("w-1/2")
                artist = ui.select(exc.headers, label=_("Artist column")).classes("w-1/2")
            if exc.preview:
                columns = [{"name": str(i), "label": h or "—", "field": str(i), "align": "left"}
                           for i, h in enumerate(exc.headers)]
                rows = [{str(i): v for i, v in enumerate(r)} for r in exc.preview[:5]]
                ui.table(columns=columns, rows=rows, row_key="0").props("dense flat").classes(
                    "w-full text-xs"
                )

            def confirm() -> None:
                if not title.value or not artist.value or title.value == artist.value:
                    notify_error(_("Choose two different columns."))
                    return
                run_import(ColumnMapping(title=title.value, artist=artist.value))

            ui.button(_("Import"), on_click=confirm).props("unelevated")

    dialog.on("hide", lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
    dialog.open()
