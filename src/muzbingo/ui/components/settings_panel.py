"""Settings tab: title, date, grid, number of cards, seed, template, language, pictures."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import events, run, ui

from muzbingo.i18n import _
from muzbingo.models import IMAGE_MIME_TYPES, Image, new_seed
from muzbingo import paths
from muzbingo.render import HttpUrls, TemplateError, list_templates
from muzbingo.render.templates import copy_template
from muzbingo.services import ServiceError
from muzbingo.services.game_service import CARD_LANGUAGES, MAX_CARDS, MAX_SIZE, MIN_SIZE
from muzbingo.ui.layout import notify_error
from muzbingo.ui.routes import ASSETS_PREFIX

if TYPE_CHECKING:
    from muzbingo.ui.pages.game import GamePage

MAX_IMAGE_BYTES = 25 * 1024 * 1024
GRID_PRESETS = ((4, 5), (5, 5))


def settings_panel(page: GamePage) -> None:
    service = page.service
    game = service.game

    def apply(**changes) -> None:
        try:
            if service.update(**changes):
                ui.notify(
                    _("New cards generated for the {rows}×{cols} grid.").format(rows=game.rows, cols=game.cols),
                    type="positive",
                )
        except (ServiceError, TemplateError, ValueError) as exc:
            notify_error(str(exc))
        page.changed()

    def on_date(value: str | None) -> None:
        if not value:
            apply(event_date=None)
            return
        try:
            apply(event_date=date.fromisoformat(value))
        except ValueError:
            pass  # still typing; Quasar's mask keeps the format right

    with ui.grid(columns="repeat(auto-fit, minmax(320px, 1fr))").classes("w-full gap-4"):
        # -- the event ------------------------------------------------------
        with ui.card().classes("gap-2"):
            ui.label(_("Event")).classes("text-base font-medium")
            ui.input(
                _("Title"), value=game.title, on_change=lambda e: apply(title=e.value)
            ).props("debounce=600").classes("w-full").mark("title")
            with ui.input(
                _("Event date"),
                value=game.event_date.isoformat() if game.event_date else "",
                on_change=lambda e: on_date(e.value),
            ).props('clearable mask="####-##-##" placeholder="YYYY-MM-DD"').classes("w-full") as date_input:
                with ui.menu().props("no-parent-event") as date_menu:
                    ui.date(mask="YYYY-MM-DD").bind_value(date_input).props("first-day-of-week=1")
                with date_input.add_slot("append"):
                    ui.icon("event").classes("cursor-pointer").on("click", date_menu.open)
            ui.select(
                CARD_LANGUAGES,
                label=_("Language on the cards"),
                value=game.language,
                on_change=lambda e: apply(language=e.value),
            ).classes("w-full")

        # -- the cards --------------------------------------------------------
        with ui.card().classes("gap-2"):
            ui.label(_("Cards")).classes("text-base font-medium")
            with ui.row().classes("items-center gap-2"):
                ui.label(_("Grid")).classes("text-sm text-gray-600 w-16")
                for rows, cols in GRID_PRESETS:
                    ui.button(
                        f"{rows}×{cols}", on_click=lambda r=rows, c=cols: set_grid(r, c)
                    ).props("outline dense").classes("px-3")
            with ui.row().classes("w-full gap-2 no-wrap"):
                rows_input = ui.number(
                    _("Rows"), value=game.rows, min=MIN_SIZE, max=MAX_SIZE, step=1, precision=0,
                    on_change=lambda e: e.value and apply(rows=int(e.value)),
                ).classes("w-1/2")
                cols_input = ui.number(
                    _("Columns"), value=game.cols, min=MIN_SIZE, max=MAX_SIZE, step=1, precision=0,
                    on_change=lambda e: e.value and apply(cols=int(e.value)),
                ).classes("w-1/2")
            ui.number(
                _("Number of cards"), value=game.n_cards, min=1, max=MAX_CARDS, step=1, precision=0,
                on_change=lambda e: e.value and apply(n_cards=int(e.value)),
            ).props("debounce=400").classes("w-full")
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                seed_input = ui.number(
                    _("Shuffle number"), value=game.seed, step=1, precision=0,
                    on_change=lambda e: e.value is not None and apply(seed=int(e.value)),
                ).props("debounce=600").classes("grow").tooltip(
                    _("The same shuffle number always gives the same cards.")
                )
                ui.button(icon="casino", on_click=lambda: seed_input.set_value(new_seed())).props(
                    "flat round"
                ).tooltip(_("New shuffle number"))

        def set_grid(rows: int, cols: int) -> None:
            apply(rows=rows, cols=cols)  # one change, so the cards are regenerated once
            rows_input.set_value(rows)  # these trigger no further change: the values match
            cols_input.set_value(cols)

        # -- the look ---------------------------------------------------------
        with ui.card().classes("gap-2"):
            ui.label(_("Look")).classes("text-base font-medium")
            templates = {t.name: t.display_name for t in list_templates()}
            with ui.row().classes("w-full items-center no-wrap gap-1"):
                template_select = ui.select(
                    templates,
                    label=_("Card template"),
                    value=game.template if game.template in templates else None,
                    on_change=lambda e: (apply(template=e.value), pictures.refresh()),
                ).classes("grow").mark("template")
                ui.button(icon="file_copy", on_click=lambda: copy_dialog()).props("flat round").tooltip(
                    _("Make a copy of this template to change its layout")
                ).mark("copy-template")

            async def copy_dialog() -> None:
                source = game.template
                with ui.dialog() as dialog, ui.card().classes("w-[32rem] max-w-full gap-3"):
                    ui.label(_("Copy the card template")).classes("text-lg font-medium")
                    ui.label(
                        _("The copy goes to your templates folder. Change its style.css, cards.html.j2 "
                          "and pictures there with a text editor; the preview shows the result.")
                    ).classes("text-sm text-gray-600")
                    name = ui.input(
                        _("Name of the copy"),
                        value=_("{name} (my copy)").format(name=templates.get(source, source)),
                    ).classes("w-full").mark("copy-name")
                    with ui.row().classes("w-full justify-end"):
                        ui.button(_("Cancel"), on_click=lambda: dialog.submit(None)).props("flat")
                        ui.button(_("Copy"), on_click=lambda: dialog.submit(name.value)).mark("copy-ok")
                display_name = await dialog
                if not display_name:
                    return
                try:
                    template = copy_template(source, display_name)
                except (TemplateError, OSError) as exc:
                    notify_error(str(exc))
                    return
                templates[template.name] = template.display_name
                template_select.set_options(templates, value=template.name)
                folder.refresh()
                ui.notify(
                    _("Copied to {path}").format(path=template.path), type="positive", multi_line=True
                )

            @ui.refreshable
            def folder() -> None:
                ui.label(
                    _("Your own templates: {path}").format(path=paths.user_templates_dir())
                ).classes("text-xs text-gray-500 break-all")

            folder()

            @ui.refreshable
            def pictures() -> None:
                for kind, label in (("logo", _("Logo")), ("background", _("Background picture"))):
                    picture_row(kind, label)

            def picture_row(kind: str, label: str) -> None:
                image: Image | None = getattr(game, kind)
                try:
                    template = service.template()
                    fallback = template.asset(getattr(template, kind))
                    url = HttpUrls(ASSETS_PREFIX).image_url(game, template, kind, image, fallback)
                except TemplateError:
                    url = None
                with ui.row().classes("w-full items-center no-wrap gap-3"):
                    with ui.element("div").classes(
                        "w-24 h-16 rounded border flex items-center justify-center bg-gray-100 overflow-hidden"
                    ):
                        if url:
                            ui.image(url).props("fit=contain").classes("w-full h-full")
                        else:
                            ui.icon("hide_image").classes("text-gray-400")
                    with ui.column().classes("gap-0 grow"):
                        ui.label(label).classes("text-sm font-medium")
                        ui.label(image.filename if image else _("Template default")).classes(
                            "text-xs text-gray-600"
                        )
                    with ui.button(icon="upload").props("flat round").tooltip(_("Choose a picture")):
                        with ui.menu().classes("p-2"):
                            ui.upload(
                                label=_("Choose a picture"),
                                on_upload=lambda e, k=kind: upload_picture(e, k),
                                auto_upload=True,
                                max_file_size=MAX_IMAGE_BYTES,
                                on_rejected=lambda: notify_error(_("This picture is too large (max. 25 MB).")),
                            ).props('accept="image/png,image/jpeg,image/svg+xml,image/webp" flat')
                    if image is not None:
                        ui.button(icon="restart_alt", on_click=lambda k=kind: clear_picture(k)).props(
                            "flat round"
                        ).tooltip(_("Use the template default"))

            async def upload_picture(e: events.UploadEventArguments, kind: str) -> None:
                mime = IMAGE_MIME_TYPES.get(Path(e.file.name).suffix.lower())
                if mime is None:
                    notify_error(_("Please choose a PNG, JPG, SVG or WebP picture."))
                    return
                data = await e.file.read()
                try:
                    # Scaling a big photo takes a moment; keep the UI responsive.
                    await run.io_bound(
                        service.set_image, kind, Image(filename=e.file.name, mime=mime, data=data)
                    )
                except ServiceError as exc:
                    notify_error(str(exc))
                    return
                stored = getattr(game, kind)
                if stored is not None and len(stored.data) < len(data):
                    ui.notify(
                        _("The picture was made smaller for printing ({before} → {after} MB).").format(
                            before=f"{len(data) / 1e6:.1f}", after=f"{len(stored.data) / 1e6:.1f}"
                        )
                    )
                pictures.refresh()
                page.changed()

            def clear_picture(kind: str) -> None:
                service.set_image(kind, None)
                pictures.refresh()
                page.changed()

            pictures()
            ui.label(
                _("Tip: a logo with a transparent background (PNG or SVG) looks best.")
            ).classes("text-xs text-gray-500")
