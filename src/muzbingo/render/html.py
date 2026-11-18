"""Render a game's cards to an HTML document with Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError as JinjaError

from muzbingo.models import Game, Image
from muzbingo.render.context import RenderError, build_context
from muzbingo.render.templates import CardTemplate


def make_environment(template: CardTemplate) -> Environment:
    return Environment(
        loader=FileSystemLoader(template.path),
        autoescape=True,
        undefined=StrictUndefined,  # a typo in a template fails loudly instead of printing nothing
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _image_url(image: Image | None, fallback: Path | None, asset_dir: Path, stem: str) -> str | None:
    """URL for a picture: the game's own image (written to asset_dir) or the template default.

    Images are referenced as file URLs rather than embedded data URLs, which keeps the
    HTML small however many cards there are.
    """
    if image is not None:
        asset_dir.mkdir(parents=True, exist_ok=True)
        path = asset_dir / f"{stem}{image.suffix}"
        path.write_bytes(image.data)
        return path.resolve().as_uri()
    if fallback is not None:
        return fallback.resolve().as_uri()
    return None


def render_html(game: Game, template: CardTemplate, asset_dir: Path) -> str:
    context = build_context(
        game,
        template,
        background_url=_image_url(game.background, template.asset(template.background), asset_dir, "background"),
        logo_url=_image_url(game.logo, template.asset(template.logo), asset_dir, "logo"),
    )
    try:
        return make_environment(template).get_template(template.entry).render(**context)
    except JinjaError as exc:
        raise RenderError(f"Error in template '{template.name}': {exc}") from exc
