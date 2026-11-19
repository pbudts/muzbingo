"""Host tab: tick off songs while playing, see who could have bingo, check a card."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import events, ui

from muzbingo.i18n import _
from muzbingo.patterns import CheckResult, Pattern
from muzbingo.render import HostOrder
from muzbingo.render.host_sheet import ordered_songs
from muzbingo.services import ServiceError
from muzbingo.ui.layout import notify_error

if TYPE_CHECKING:
    from muzbingo.ui.pages.game import GamePage


def pattern_labels() -> dict[str, str]:
    return {
        Pattern.ONE_LINE.value: _("One line"),
        Pattern.TWO_LINES.value: _("Two lines"),
        Pattern.FULL_CARD.value: _("Full card"),
    }


def order_labels() -> dict[str, str]:
    return {
        HostOrder.SHUFFLED.value: _("Play order (shuffled)"),
        HostOrder.PLAYLIST.value: _("Playlist order"),
        HostOrder.ARTIST.value: _("Sorted by artist"),
        HostOrder.TITLE.value: _("Sorted by title"),
    }


def host_panel(page: GamePage) -> None:
    service = page.service
    game = service.game
    # Kept on the service, so they survive a page reload like the undo history.
    state = getattr(service, "host_state", None)
    if state is None:
        state = service.host_state = {"order": HostOrder.SHUFFLED.value, "pattern": Pattern.ONE_LINE.value,
                                      "number": None}

    def pattern() -> Pattern:
        return Pattern(state["pattern"])

    # -- the songs ------------------------------------------------------------

    def row_for(song, n: int) -> dict:
        position = game.played.index(song.id) + 1 if song.id in game.played else None
        return {
            "id": song.id,
            "n": n,
            "title": song.shown_title,
            "artist": song.shown_artist,
            "played": position is not None,
            "position": position,
        }

    def row_data() -> list[dict]:
        number = {song.id: n for n, song in enumerate(game.playlist, start=1)}
        return [row_for(song, number[song.id]) for song in ordered_songs(game, state["order"])]

    @ui.refreshable
    def progress() -> None:
        n_played, n = len(game.played), len(game.playlist)
        ui.label(_("{played} of {n} songs played").format(played=n_played, n=n)).classes(
            "text-base font-medium"
        ).mark("played-count")
        ui.linear_progress(n_played / n if n else 0, show_value=False).classes("w-full").props("rounded")

    def on_cell_changed(e: events.GenericEventArguments) -> None:
        if e.args.get("colId") != "played":
            return
        song_id = (e.args.get("data") or {}).get("id")
        before = set(service.winners(pattern()))
        try:
            service.set_played(song_id, bool(e.args.get("newValue")))
        except ServiceError as exc:
            notify_error(str(exc))
            return
        after_played_change(before)

    def after_played_change(winners_before: set[int]) -> None:
        # Update the rows in place. Don't touch grid.options: any change there makes
        # NiceGUI rebuild the table, which loses the search filter and scroll position.
        grid.run_grid_method("applyTransaction", {"update": row_data()})
        new = sorted(set(service.winners(pattern())) - winners_before)
        if new:
            ui.notify(
                _("{pattern} on card {cards}!").format(
                    pattern=pattern_labels()[state["pattern"]], cards=", ".join(map(str, new))
                ),
                type="positive", position="top", timeout=8000,
            )
        progress.refresh()
        winners.refresh()
        check_result.refresh()
        page.changed(skip=on_page_changed)

    def set_order(value: str) -> None:
        state["order"] = value
        grid.options["rowData"] = row_data()
        grid.update()

    async def start_again() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label(_("Start again?")).classes("text-lg")
            ui.label(_("All songs are marked as not played. You can undo this."))
            with ui.row().classes("w-full justify-end"):
                ui.button(_("Cancel"), on_click=lambda: dialog.submit(False)).props("flat")
                ui.button(_("Start again"), color="negative", on_click=lambda: dialog.submit(True))
        if await dialog:
            service.clear_played()
            page.changed()

    # -- the round: who has bingo? ----------------------------------------------

    @ui.refreshable
    def winners() -> None:
        if not game.cards:
            ui.label(_("Generate the cards first (Cards tab).")).classes("text-sm text-gray-600")
            return
        numbers = service.winners(pattern())
        if not numbers:
            ui.label(_("No card has this yet.")).classes("text-sm text-gray-600").mark("winners")
            return
        ui.label(_("These cards have it:")).classes("text-sm").mark("winners")
        with ui.row().classes("gap-2"):
            for number in numbers:
                ui.button(str(number), on_click=lambda n=number: check(n)).props(
                    "unelevated dense color=positive"
                ).classes("px-3").tooltip(_("Show card {number}").format(number=number))

    def set_pattern(value: str) -> None:
        state["pattern"] = value
        winners.refresh()
        check_result.refresh()

    # -- check one card ---------------------------------------------------------

    def check(number: int | None) -> None:
        state["number"] = int(number) if number else None
        number_input.set_value(state["number"])
        check_result.refresh()

    @ui.refreshable
    def check_result() -> None:
        number = state["number"]
        if not number:
            return
        try:
            result = service.check(number, pattern())
        except ServiceError as exc:
            ui.label(str(exc)).classes("w-full rounded px-3 py-2 bg-red-50 text-red-900").mark("check-result")
            return
        verdict(number, result)
        card_grid(number, result)

    def verdict(number: int, result: CheckResult) -> None:
        name = pattern_labels()[state["pattern"]].lower()
        if result.won:
            rows = ", ".join(str(i + 1) for i in result.complete_rows)
            text = _("Bingo! Card {number} has {pattern}.").format(number=number, pattern=name)
            if pattern() is not Pattern.FULL_CARD:
                text += " " + _("Complete rows: {rows}.").format(rows=rows)
            ui.label(text).classes(
                "w-full rounded px-3 py-2 text-lg font-bold bg-green-100 text-green-900"
            ).mark("check-result")
        else:
            missing = len(result.missing)
            ui.label(
                _("Not yet: card {number} needs {missing} more songs for {pattern}.").format(
                    number=number, missing=missing, pattern=name
                )
            ).classes("w-full rounded px-3 py-2 text-base bg-amber-50 text-amber-900").mark("check-result")

    def card_grid(number: int, result: CheckResult) -> None:
        card = game.card(number)
        songs = game.songs_by_id()
        played = set(game.played)
        missing = set(result.missing)
        with ui.element("div").classes("w-full grid gap-1").style(
            f"grid-template-columns: repeat({len(card.cells[0])}, minmax(0, 1fr))"
        ):
            for r, row in enumerate(card.cells):
                complete = r in result.complete_rows
                for song_id in row:
                    song = songs.get(song_id)
                    if song_id in played:
                        color = "bg-green-600 text-white" if complete else "bg-green-100 text-green-900"
                    elif song_id in missing:
                        color = "bg-amber-50 text-amber-900 border border-amber-300"
                    else:
                        color = "bg-gray-100 text-gray-700"
                    with ui.column().classes(f"gap-0 rounded p-1 min-h-[3.2rem] justify-center {color}"):
                        ui.label(song.shown_title if song else "?").classes(
                            "text-xs font-bold leading-tight"
                        )
                        ui.label(song.shown_artist if song else _("(removed song)")).classes(
                            "text-[10px] leading-tight opacity-80"
                        )
        ui.label(
            _("Green: played. Dark green: complete row. Outlined: still needed.")
        ).classes("text-xs text-gray-500")

    # -- layout -----------------------------------------------------------------

    with ui.element("div").classes("w-full grid gap-4 grid-cols-1 lg:grid-cols-[3fr_2fr]"):
        with ui.card().classes("gap-3 min-w-0"):
            progress()
            with ui.row().classes("w-full items-center gap-2"):
                search = ui.input(placeholder=_("Search title or artist")).props(
                    "clearable dense outlined"
                ).classes("grow").mark("host-search")
                with search.add_slot("prepend"):
                    ui.icon("search")
                ui.select(
                    order_labels(), value=state["order"], on_change=lambda e: set_order(e.value)
                ).props("dense outlined").classes("w-56")
                ui.button(_("Start again"), icon="restart_alt", on_click=start_again).props("flat")
            grid = ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": _("Played"), "field": "played", "cellDataType": "boolean",
                         "editable": True, "width": 95},
                        {"headerName": "#", "field": "n", "width": 70, "sortable": True},
                        {"headerName": _("Title"), "field": "title", "flex": 3},
                        {"headerName": _("Artist"), "field": "artist", "flex": 2},
                        {"headerName": _("Order"), "field": "position", "width": 90,
                         "headerTooltip": _("When the song was played: 1 = first")},
                    ],
                    "rowData": row_data(),
                    ":getRowId": "params => params.data.id",
                    ":getRowStyle": "params => params.data.played ? {opacity: 0.55} : null",
                    "overlayNoRowsTemplate": _("No songs yet. Import a playlist on the Playlist tab."),
                },
                theme="quartz",
            ).classes("w-full").style("height: 65vh").mark("host-grid")
            grid.on("cellValueChanged", on_cell_changed)
            search.on_value_change(
                lambda e: grid.run_grid_method("setGridOption", "quickFilterText", e.value or "")
            )
            ui.label(_("Tick a song when you play it. Ctrl+Z undoes a tick.")).classes(
                "text-xs text-gray-500"
            )

        with ui.column().classes("gap-4 min-w-0"):
            with ui.card().classes("w-full gap-2"):
                ui.label(_("This round")).classes("text-base font-medium")
                ui.toggle(pattern_labels(), value=state["pattern"], on_change=lambda e: set_pattern(e.value)).props(
                    "no-caps unelevated toggle-color=primary"
                ).mark("pattern")
                winners()
            with ui.card().classes("w-full gap-2"):
                ui.label(_("Check a card")).classes("text-base font-medium")
                with ui.row().classes("w-full items-center no-wrap gap-2"):
                    number_input = ui.number(
                        _("Card number"), value=state["number"], min=1, step=1, precision=0
                    ).props("dense outlined").classes("grow").mark("check-number")
                    number_input.on("keydown.enter", lambda: check(number_input.value))
                    ui.button(_("Check"), icon="fact_check", on_click=lambda: check(number_input.value)).props(
                        "unelevated"
                    ).mark("check")
                if game.cards_outdated:
                    ui.label(
                        _("The settings changed after these cards were made. Check only with the "
                          "cards you printed from them.")
                    ).classes("text-xs rounded px-2 py-1 bg-amber-50 text-amber-900")
                check_result()

    def on_page_changed() -> None:
        grid.options["rowData"] = row_data()
        grid.update()
        progress.refresh()
        winners.refresh()
        check_result.refresh()

    page.on_change(on_page_changed)
