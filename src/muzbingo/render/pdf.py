"""Print an HTML file to PDF with Qt WebEngine (Chromium).

This is the only module that knows which engine makes the PDF. ``QWebEnginePage``
works asynchronously; ``print_pdf`` wraps it in a local event loop so callers get a
plain blocking function. It needs a QApplication; one is created when missing, using
the offscreen platform on Linux machines without a display.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from muzbingo.render.context import RenderError

_app_ref: list[object] = []  # keeps a QApplication we created alive


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


def print_pdf(
    html_file: Path,
    pdf_file: Path,
    *,
    page_size: str = "A4",
    orientation: str = "landscape",
    timeout_s: int = 300,
) -> None:
    ensure_qt_app()

    from PySide6.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
    from PySide6.QtGui import QPageLayout, QPageSize
    from PySide6.QtWebEngineCore import QWebEnginePage

    size_id = getattr(QPageSize.PageSizeId, page_size, None)
    if size_id is None:
        raise RenderError(f"Unknown page size: {page_size}")
    layout = QPageLayout(
        QPageSize(size_id),
        QPageLayout.Orientation.Landscape if orientation == "landscape" else QPageLayout.Orientation.Portrait,
        QMarginsF(0, 0, 0, 0),
    )

    pdf_file = Path(pdf_file).resolve()
    page = QWebEnginePage()
    loop = QEventLoop()
    state: dict[str, object] = {"started": False, "error": None}

    def on_loaded(ok: bool) -> None:
        if state["started"]:
            return
        state["started"] = True
        if not ok:
            state["error"] = "Could not load the rendered cards"
            loop.quit()
            return
        page.printToPdf(str(pdf_file), layout)

    def on_printed(_path: str, ok: bool) -> None:
        if not ok:
            state["error"] = f"Could not write {pdf_file.name}"
        loop.quit()

    def on_timeout() -> None:
        state["error"] = "Timed out while creating the PDF"
        loop.quit()

    page.loadFinished.connect(on_loaded)
    page.pdfPrintingFinished.connect(on_printed)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(on_timeout)
    timer.start(timeout_s * 1000)

    page.load(QUrl.fromLocalFile(str(Path(html_file).resolve())))
    loop.exec()
    timer.stop()
    page.deleteLater()

    if state["error"]:
        raise RenderError(str(state["error"]))
