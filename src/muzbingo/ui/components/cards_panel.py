"""Cards tab: generate cards, preview them, download the PDF."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from muzbingo.i18n import _
from muzbingo.render import RenderError, TemplateError
from muzbingo.services import ServiceError
from muzbingo.ui import context
from muzbingo.ui.layout import notify_error, safe_filename

if TYPE_CHECKING:
    from muzbingo.ui.pages.game import GamePage

# The card page is A4 landscape: 297 × 210 mm = 1123 × 794 CSS pixels.
PAGE_PX = (1123, 794)
PREVIEW_SCALE = 0.62


def cards_panel(page: GamePage) -> None:
    service = page.service
    game = service.game
    state = {"number": 1, "version": 0}

    @ui.refreshable
    def status() -> None:
        s = service.playlist_status()
        if not game.cards:
            ui.label(_("No cards yet.")).classes("text-base font-medium")
        else:
            ui.label(
                _("{n} cards of {rows}×{cols}").format(n=len(game.cards), rows=game.rows, cols=game.cols)
            ).classes("text-base font-medium").mark("cards-summary")
        if game.cards_outdated:
            ui.label(
                _("The playlist or the card settings changed since these cards were made. "
                  "Generate new cards before printing.")
            ).classes("w-full rounded px-3 py-2 text-sm bg-amber-50 text-amber-900").mark("outdated")
        if not s.can_generate:
            ui.label(s.message).classes("w-full rounded px-3 py-2 text-sm bg-red-50 text-red-900")
        with ui.row().classes("items-center gap-2"):
            ui.button(
                _("Generate cards") if not game.cards else _("Generate new cards"),
                icon="casino",
                on_click=generate,
            ).props("unelevated" if not game.cards or game.cards_outdated else "outline").mark("generate")
            pdf_button = ui.button(_("Download PDF"), icon="picture_as_pdf").props("unelevated").mark(
                "download-pdf"
            )
            pdf_button.on_click(lambda: download_pdf(pdf_button))
            pdf_button.set_enabled(bool(game.cards) and not game.cards_outdated)

    @ui.refreshable
    def preview() -> None:
        if not game.cards:
            return
        state["number"] = min(max(state["number"], 1), len(game.cards))
        with ui.row().classes("items-center gap-2"):
            ui.label(_("Preview of card")).classes("text-sm text-gray-600")
            ui.pagination(
                1, len(game.cards), value=state["number"], direction_links=True,
                on_change=lambda e: show_card(e.value),
            ).props("max-pages=7 boundary-numbers")
        w, h = PAGE_PX
        src = f"/preview/{game.id}/{state['number']}?v={state['version']}"
        with ui.element("div").classes("rounded shadow overflow-hidden bg-white").style(
            f"width:{w * PREVIEW_SCALE:.0f}px; height:{h * PREVIEW_SCALE:.0f}px; max-width:100%"
        ):
            ui.element("iframe").props(f'src="{src}" title="{_("Card preview")}"').style(
                f"width:{w}px; height:{h}px; border:0; transform:scale({PREVIEW_SCALE}); "
                "transform-origin:0 0"
            ).mark("preview")

    def show_card(number: int | None) -> None:
        state["number"] = number or 1
        preview.refresh()

    def on_page_changed() -> None:
        state["version"] += 1  # reload the iframe: title, pictures or texts may have changed
        status.refresh()
        preview.refresh()

    page.on_change(on_page_changed)

    async def generate() -> None:
        if game.cards and not game.cards_outdated:
            with ui.dialog() as dialog, ui.card():
                ui.label(_("Generate new cards?")).classes("text-lg")
                ui.label(_("All cards change. Cards you already printed will no longer match this game."))
                with ui.row().classes("w-full justify-end"):
                    ui.button(_("Cancel"), on_click=lambda: dialog.submit(False)).props("flat")
                    ui.button(_("Generate"), on_click=lambda: dialog.submit(True))
            if not await dialog:
                return
        try:
            cards = service.generate()
        except ServiceError as exc:
            notify_error(str(exc))
            return
        ui.notify(_("{n} cards generated.").format(n=len(cards)), type="positive")
        page.changed()

    async def download_pdf(button: ui.button) -> None:
        pdf_service = context.get().pdf
        if pdf_service is None:
            notify_error(_("PDF export is not available: Qt WebEngine could not be started."))
            return
        button.props("loading")
        try:
            pdf = await pdf_service.render(game, service.template())
        except (RenderError, TemplateError) as exc:
            notify_error(str(exc))
            return
        finally:
            button.props(remove="loading")
        ui.download.content(pdf, safe_filename(game.title, ".pdf"), media_type="application/pdf")

    with ui.card().classes("w-full gap-3"):
        status()
        preview()
