"""Shared page frame and small helpers."""

from __future__ import annotations

import re
from collections.abc import Callable

from nicegui import ui

from muzbingo.i18n import _

ACCENT = "#d1006f"


def frame(
    title: str = "", *, back: bool = False, actions: Callable[[], None] | None = None
) -> ui.label | None:
    """Header bar used on every page. Returns the title label, if any.

    ``actions`` adds buttons at the right of the bar.
    """
    ui.colors(primary="#4b2a8c", secondary=ACCENT, accent=ACCENT)
    ui.query("body").style("background:#f6f4fa")
    with ui.header().classes("items-center gap-3 px-4 py-2").style("background:#2b1a5e"):
        if back:
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
                "flat round color=white"
            ).tooltip(_("Back to My games"))
        ui.label("♫ MuzBingo").classes("text-lg font-bold cursor-pointer").on(
            "click", lambda: ui.navigate.to("/")
        )
        label = None
        if title:
            ui.label("·").classes("opacity-50")
            label = ui.label(title).classes("text-lg").mark("page-title")
        if actions:
            ui.space()
            actions()
    return label


def safe_filename(text: str, suffix: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "", text).strip() or "muzbingo"
    return f"{name}{suffix}"


def notify_error(message: str) -> None:
    ui.notify(message, type="negative", multi_line=True, close_button=True, timeout=10000)
