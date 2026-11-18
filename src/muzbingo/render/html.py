"""Render a game's cards to an HTML document with Jinja2.

Where the HTML finds its CSS and pictures depends on who shows it, so the caller
passes an ``AssetUrls`` object:

- ``FileUrls``: ``file://`` URLs, for the PDF and the HTML export.
- ``HttpUrls``: routes on the local web server, for the preview in the UI (a page
  served over http:// may not load file:// URLs).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError as JinjaError

from muzbingo.models import Card, Game, Image
from muzbingo.render.context import RenderError, build_context
from muzbingo.render.templates import CardTemplate

IMAGE_KINDS = ("background", "logo")


class AssetUrls(Protocol):
    def template_url(self, template: CardTemplate) -> str:
        """URL of the template folder, ending with "/"."""

    def image_url(
        self, game: Game, template: CardTemplate, kind: str, image: Image | None, fallback: Path | None
    ) -> str | None:
        """URL of the game's own picture, else of the template default, else None."""


class FileUrls:
    """file:// URLs. The game's own pictures are written to ``asset_dir`` first."""

    def __init__(self, asset_dir: Path):
        self.asset_dir = asset_dir

    def template_url(self, template: CardTemplate) -> str:
        return template.path.resolve().as_uri() + "/"

    def image_url(self, game, template, kind, image, fallback):
        if image is not None:
            self.asset_dir.mkdir(parents=True, exist_ok=True)
            path = self.asset_dir / f"{kind}{image.suffix}"
            path.write_bytes(image.data)
            return path.resolve().as_uri()
        if fallback is not None:
            return fallback.resolve().as_uri()
        return None


class HttpUrls:
    """URLs served by ``muzbingo.ui.routes`` under ``prefix``."""

    def __init__(self, prefix: str = "/assets"):
        self.prefix = prefix.rstrip("/")

    def template_url(self, template: CardTemplate) -> str:
        return f"{self.prefix}/templates/{template.name}/"

    def image_url(self, game, template, kind, image, fallback):
        if image is not None:
            version = hashlib.sha1(image.data).hexdigest()[:10]  # new URL when the picture changes
            return f"{self.prefix}/games/{game.id}/{kind}?v={version}"
        if fallback is not None:
            return f"{self.prefix}/templates/{template.name}/{fallback.name}"
        return None


def make_environment(template: CardTemplate) -> Environment:
    return Environment(
        loader=FileSystemLoader(template.path),
        autoescape=True,
        undefined=StrictUndefined,  # a typo in a template fails loudly instead of printing nothing
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(
    game: Game, template: CardTemplate, urls: AssetUrls, cards: list[Card] | None = None
) -> str:
    """Render ``cards`` (default: all cards of the game) with the template."""
    context = build_context(
        game,
        template,
        cards=cards,
        template_url=urls.template_url(template),
        background_url=urls.image_url(
            game, template, "background", game.background, template.asset(template.background)
        ),
        logo_url=urls.image_url(game, template, "logo", game.logo, template.asset(template.logo)),
    )
    try:
        return make_environment(template).get_template(template.entry).render(**context)
    except JinjaError as exc:
        raise RenderError(f"Error in template '{template.name}': {exc}") from exc
