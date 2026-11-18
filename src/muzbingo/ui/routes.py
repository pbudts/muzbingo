"""Plain HTTP routes next to the NiceGUI pages.

- ``/assets/templates/<name>/<file>``: files of a card template (CSS, fonts, pictures)
- ``/assets/games/<id>/<background|logo>``: a game's own pictures
- ``/preview/<id>/<card number>``: one card rendered as HTML, shown in an iframe

The preview uses ``HttpUrls``, so the template finds its files through these routes.
"""

from __future__ import annotations

import html

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from muzbingo.render import HttpUrls, RenderError, TemplateError, load_template, render_html
from muzbingo.services import LibraryError
from muzbingo.ui import context

ASSETS_PREFIX = "/assets"


def _message_page(text: str) -> HTMLResponse:
    return HTMLResponse(
        f'<body style="font-family:sans-serif;color:#555;display:flex;align-items:center;'
        f'justify-content:center;height:90vh;margin:0">{html.escape(text)}</body>'
    )


def register(app: FastAPI) -> None:
    @app.get(ASSETS_PREFIX + "/templates/{name}/{path:path}")
    def template_asset(name: str, path: str) -> FileResponse:
        try:
            template = load_template(name)
        except TemplateError:
            raise HTTPException(404) from None
        root = template.path.resolve()
        file = (root / path).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise HTTPException(404)
        return FileResponse(file)

    @app.get(ASSETS_PREFIX + "/games/{game_id}/{kind}")
    def game_image(game_id: str, kind: str) -> Response:
        if kind not in ("background", "logo"):
            raise HTTPException(404)
        try:
            game = context.get().library.load(game_id)
        except LibraryError:
            raise HTTPException(404) from None
        image = getattr(game, kind)
        if image is None:
            raise HTTPException(404)
        return Response(content=image.data, media_type=image.mime)

    @app.get("/preview/{game_id}/{number}")
    def preview(game_id: str, number: int) -> HTMLResponse:
        try:
            game = context.get().library.load(game_id)
            card = game.card(number)
            if card is None:
                return _message_page("No card to show yet. Generate the cards first.")
            template = load_template(game.template)
            return HTMLResponse(render_html(game, template, HttpUrls(ASSETS_PREFIX), cards=[card]))
        except (LibraryError, RenderError, TemplateError) as exc:
            return _message_page(str(exc))
