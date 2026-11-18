"""Print an HTML file to PDF with Qt WebEngine (Chromium).

This is the only module that knows which engine makes the PDF.

- ``start_print`` is non-blocking: it must be called on the Qt thread and reports back
  through a callback. ``muzbingo.services.pdf_service`` uses it from the web UI.
- ``print_pdf`` blocks until the PDF is written, by running a local event loop. The
  command-line tool uses it.

Both need a QApplication; ``ensure_qt_app`` creates one when missing, using the
offscreen platform on Linux machines without a display.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from muzbingo.render.context import RenderError

_app_ref: list[object] = []  # keeps a QApplication we created alive
_active_pages: set[object] = set()  # keeps pages alive while they print

DoneCallback = Callable[[str | None], None]  # receives an error message, or None on success


def ensure_qt_app() -> None:
    try:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWebEngineCore import QWebEnginePage  # noqa: F401  (checks WebEngine is present)
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RenderError(
            f"PDF export needs PySide6 with Qt WebEngine ({exc}); install it with: pip install PySide6"
        ) from exc

    if QApplication.instance() is not None:
        return
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    _app_ref.append(QApplication(sys.argv[:1]))


def start_print(
    html_file: Path,
    pdf_file: Path,
    done: DoneCallback,
    *,
    page_size: str = "A4",
    orientation: str = "landscape",
    timeout_s: int = 300,
) -> None:
    """Start printing ``html_file`` to ``pdf_file``. Call on the Qt thread.

    ``done`` is called exactly once, on the Qt thread.
    """
    from PySide6.QtCore import QMarginsF, QTimer, QUrl
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtWebEngineCore import QWebEnginePage

    size_id = getattr(QPageSize.PageSizeId, page_size, None)
    if size_id is None:
        done(f"Unknown page size: {page_size}")
        return
    layout = QPageLayout(
        QPageSize(size_id),
        QPageLayout.Orientation.Landscape if orientation == "landscape" else QPageLayout.Orientation.Portrait,
        QMarginsF(0, 0, 0, 0),
    )
    pdf_file = Path(pdf_file).resolve()
    page = QWebEnginePage()
    timer = QTimer()
    timer.setSingleShot(True)
    state = {"printing": False, "finished": False}
    _active_pages.add(page)

    def finish(error: str | None) -> None:
        if state["finished"]:
            return
        state["finished"] = True
        timer.stop()
        _active_pages.discard(page)
        page.deleteLater()
        done(error)

    def on_loaded(ok: bool) -> None:
        if state["printing"] or state["finished"]:
            return
        if not ok:
            finish("Could not load the rendered cards")
            return
        state["printing"] = True
        page.printToPdf(str(pdf_file), layout)

    def on_printed(_path: str, ok: bool) -> None:
        finish(None if ok else f"Could not write {pdf_file.name}")

    page.loadFinished.connect(on_loaded)
    page.pdfPrintingFinished.connect(on_printed)
    timer.timeout.connect(lambda: finish("Timed out while creating the PDF"))
    timer.start(timeout_s * 1000)
    page.load(QUrl.fromLocalFile(str(Path(html_file).resolve())))


def print_pdf(
    html_file: Path,
    pdf_file: Path,
    *,
    page_size: str = "A4",
    orientation: str = "landscape",
    timeout_s: int = 300,
) -> None:
    """Print and wait until the PDF is written. Raises RenderError on failure."""
    ensure_qt_app()
    from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop

    loop = QEventLoop()
    result: list[str | None] = []

    def done(error: str | None) -> None:
        result.append(error)
        loop.quit()

    start_print(html_file, pdf_file, done, page_size=page_size, orientation=orientation, timeout_s=timeout_s)
    if not result:
        loop.exec()
    # Delete the page now, not at application exit (avoids a WebEngine warning).
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    if result and result[0]:
        raise RenderError(result[0])
