"""Render a game's cards: Jinja2 template → HTML → PDF."""

from __future__ import annotations

import tempfile
from pathlib import Path

from muzbingo.models import Game
from muzbingo.render.context import RenderError, format_date, is_too_long
from muzbingo.render.html import AssetUrls, FileUrls, HttpUrls, render_html
from muzbingo.render.templates import CardTemplate, TemplateError, list_templates, load_template

__all__ = [
    "AssetUrls",
    "CardTemplate",
    "FileUrls",
    "HttpUrls",
    "RenderError",
    "TemplateError",
    "export_html",
    "export_pdf",
    "format_date",
    "is_too_long",
    "list_templates",
    "load_template",
    "render_html",
]


def export_html(game: Game, html_path: str | Path, template: CardTemplate | None = None) -> Path:
    """Write the cards as an HTML file (useful to work on a template in a browser).

    The game's own images are written to a ``<name>_files`` folder next to the file.
    """
    html_path = Path(html_path).resolve()
    template = template or load_template(game.template)
    urls = FileUrls(html_path.with_name(html_path.stem + "_files"))
    html = render_html(game, template, urls)
    html_path.write_text(html, encoding="utf-8")
    return html_path


def export_pdf(game: Game, pdf_path: str | Path, template: CardTemplate | None = None) -> Path:
    """Write all cards to one PDF, one card per page."""
    from muzbingo.render.pdf import print_pdf  # imports Qt; keep it out of HTML-only use

    pdf_path = Path(pdf_path).resolve()
    template = template or load_template(game.template)
    with tempfile.TemporaryDirectory(prefix="muzbingo-") as tmp:
        html_file = export_html(game, Path(tmp) / "cards.html", template)
        print_pdf(
            html_file,
            pdf_path,
            page_size=template.page_size,
            orientation=template.orientation,
        )
    return pdf_path
