"""Only the person who started MuzBingo may use it.

The server listens on 127.0.0.1, but other programs and websites on the same PC could
still send it requests. At startup a random token is created; opening the URL with
``?token=...`` sets a session cookie, and every request (pages, assets, websockets)
must carry that cookie.

When bound to a loopback address, the ``Host`` header must be 127.0.0.1 or localhost,
which blocks DNS-rebinding attacks from websites.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from starlette.datastructures import Headers, QueryParams
from starlette.requests import HTTPConnection
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

COOKIE_NAME = "muzbingo_session"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}

DENIED_PAGE = """<!doctype html><meta charset="utf-8"><title>MuzBingo</title>
<body style="font-family:sans-serif;max-width:36em;margin:4em auto;line-height:1.5">
<h1>MuzBingo</h1>
<p>Open MuzBingo with the link that was shown when it started (it ends with <code>?token=…</code>).</p>
</body>"""


def new_token() -> str:
    return secrets.token_urlsafe(24)


class TokenAuthMiddleware:
    def __init__(self, app: ASGIApp, *, token: str, check_host: bool = True) -> None:
        self.app = app
        self.token = token
        self.check_host = check_host

    def _has_valid_cookie(self, scope: Scope) -> bool:
        cookie = HTTPConnection(scope).cookies.get(COOKIE_NAME, "")
        return secrets.compare_digest(cookie.encode(), self.token.encode())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if self.check_host:
            host = Headers(scope=scope).get("host", "")
            hostname = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
            if hostname not in LOOPBACK_HOSTS:
                await self._deny(scope, receive, send, PlainTextResponse("Invalid host", 400))
                return

        if self._has_valid_cookie(scope):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            query = QueryParams(scope.get("query_string", b""))
            given = query.get("token", "")
            if given and secrets.compare_digest(given.encode(), self.token.encode()):
                # Valid link: remember it in a cookie and continue without the token in the URL.
                rest = urlencode([(k, v) for k, v in query.multi_items() if k != "token"])
                response = RedirectResponse(scope["path"] + (f"?{rest}" if rest else ""), status_code=303)
                response.set_cookie(COOKIE_NAME, self.token, httponly=True, samesite="strict")
                await response(scope, receive, send)
                return

        await self._deny(scope, receive, send, HTMLResponse(DENIED_PAGE, 403))

    @staticmethod
    async def _deny(scope: Scope, receive: Receive, send: Send, response) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
        else:
            await response(scope, receive, send)
