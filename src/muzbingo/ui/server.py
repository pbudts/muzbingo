"""Run the web UI.

Threads:
- The **main thread** runs the Qt event loop. PDF printing (Qt WebEngine) happens
  there. In ``serve`` mode Qt runs offscreen without any window.
- **uvicorn** runs in a background thread with its own asyncio loop, serving FastAPI
  with NiceGUI mounted on it.

``serve`` blocks until Ctrl+C (or until the app window is closed, in phase 5).
"""

from __future__ import annotations

import ipaddress
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from muzbingo import paths, settings
from muzbingo.i18n import current_language
from muzbingo.services import Library

log = logging.getLogger(__name__)


class ServerError(Exception):
    """The server could not start."""


@dataclass
class RunningServer:
    url: str  # including ?token=...
    port: int
    stop: callable  # type: ignore[valid-type]


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_app(library: Library, pdf, token: str, *, check_host: bool):
    from fastapi import FastAPI
    from nicegui import ui

    from muzbingo.ui.app import QUASAR_LANGUAGES, setup
    from muzbingo.ui.auth import TokenAuthMiddleware

    fastapi_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    setup(library, pdf)
    ui.run_with(
        fastapi_app,
        title="MuzBingo",
        favicon="🎵",
        storage_secret=token,
        show_welcome_message=False,
        language=QUASAR_LANGUAGES.get(current_language(), "en-GB"),  # run_with resets it otherwise
    )
    fastapi_app.add_middleware(TokenAuthMiddleware, token=token, check_host=check_host)
    return fastapi_app


def start_server(host: str, port: int, data_dir: Path | None = None) -> RunningServer:
    """Start the web server in a background thread. Call on the Qt (main) thread."""
    import uvicorn

    from muzbingo.render.pdf import ensure_qt_app
    from muzbingo.services.pdf_service import PdfService
    from muzbingo.ui.auth import new_token

    ensure_qt_app()
    pdf = PdfService()
    if data_dir is not None:
        paths.set_data_dir(data_dir)  # games, user templates and settings all live there
        settings.reset()
    library = Library(paths.games_dir())
    token = new_token()
    app = build_app(library, pdf, token, check_host=_is_loopback(host))

    config = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="on")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="muzbingo-server", daemon=True)
    thread.start()

    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise ServerError(
                f"Could not start the server on {host}:{port}. "
                "Is the port already in use? Try another one with --port."
            )
        time.sleep(0.05)

    actual_port = server.servers[0].sockets[0].getsockname()[1]
    shown_host = "localhost" if _is_loopback(host) else host
    if shown_host in ("0.0.0.0", "::"):
        shown_host = "<this-computer's-address>"

    def stop() -> None:
        server.should_exit = True
        thread.join(10)

    return RunningServer(url=f"http://{shown_host}:{actual_port}/?token={token}", port=actual_port, stop=stop)


def serve(host: str = "127.0.0.1", port: int = 8080, data_dir: Path | None = None) -> int:
    """Run the UI for use in a browser, until Ctrl+C."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    try:
        running = start_server(host, port, data_dir)
    except ServerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("MuzBingo is running. Open this link in your browser:\n")
    print(f"    {running.url}\n")
    if _is_loopback(host):
        print("From another computer, forward the port first, e.g.:")
        print(f"    ssh -L {running.port}:localhost:{running.port} <this machine>")
        print("(VS Code Remote-SSH does this automatically: see the Ports panel.)\n")
    print(f"Games are stored in: {paths.games_dir()}")
    print(f"Your own card templates go in: {paths.user_templates_dir()}")
    print("Press Ctrl+C to stop.")

    app = QApplication.instance()
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    # Qt's event loop doesn't let Python handle Ctrl+C by itself; wake it up regularly.
    ticker = QTimer()
    ticker.timeout.connect(lambda: None)
    ticker.start(200)
    try:
        app.exec()
    finally:
        print("\nStopping…")
        running.stop()
    return 0
