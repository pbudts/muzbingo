"""Make PDFs for the web UI without blocking it.

Qt objects may only be used on the Qt (main) thread, while the web server runs its
asyncio loop in another thread. ``PdfService`` bridges the two: ``await
service.render(game)`` renders the HTML in the server thread, hands the printing to
the Qt thread through a queued signal, and resumes when the PDF is ready.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from muzbingo.models import Game
from muzbingo.render import CardTemplate, RenderError, export_html, load_template


class PdfService:
    """Create on the Qt thread, after the QApplication exists."""

    def __init__(self) -> None:
        from PySide6.QtCore import QObject, Qt, Signal

        from muzbingo.render.pdf import start_print

        class _Bridge(QObject):
            job = Signal(object)

            def run(self, job: tuple) -> None:  # runs on the Qt thread
                html_file, pdf_file, template, done = job
                start_print(
                    html_file,
                    pdf_file,
                    done,
                    page_size=template.page_size,
                    orientation=template.orientation,
                )

        self._bridge = _Bridge()
        self._bridge.job.connect(self._bridge.run, Qt.ConnectionType.QueuedConnection)

    async def render(self, game: Game, template: CardTemplate | None = None) -> bytes:
        """Return the PDF with all cards of ``game``."""
        template = template or load_template(game.template)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()
        tmp = tempfile.TemporaryDirectory(prefix="muzbingo-")
        html_file = export_html(game, Path(tmp.name) / "cards.html", template)
        pdf_file = Path(tmp.name) / "cards.pdf"

        def finish(error: str | None) -> None:  # on the asyncio thread
            try:
                if future.done():  # e.g. cancelled because the browser went away
                    return
                if error:
                    future.set_exception(RenderError(error))
                else:
                    future.set_result(pdf_file.read_bytes())
            finally:
                tmp.cleanup()

        def done(error: str | None) -> None:  # on the Qt thread
            try:
                loop.call_soon_threadsafe(finish, error)
            except RuntimeError:  # the server's loop is already closed (shutting down)
                tmp.cleanup()

        self._bridge.job.emit((html_file, pdf_file, template, done))
        return await future
