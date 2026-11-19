"""The app window for end-users: the local web UI in a normal desktop window.

Starts the server on a free port of 127.0.0.1 and shows it in a QWebEngineView, so
users never see a browser, URL or port. Everything else lives in ``muzbingo.ui``.

- Downloads (PDF, game files) get a native "Save as" dialog.
- Links to other websites (e.g. Exportify) open in the user's own browser.
- Closing the window stops the server and the app.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from muzbingo.i18n import _

WINDOW_SIZE = (1280, 860)


def has_display() -> bool:
    if not sys.platform.startswith("linux") or os.environ.get("QT_QPA_PLATFORM"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def run(data_dir: Path | None = None) -> int:
    if not has_display():
        print(
            "No desktop found, so the MuzBingo window can't open here.\n"
            "Use the browser version instead:  muzbingo serve",
            file=sys.stderr,
        )
        return 1

    from PySide6.QtCore import QCoreApplication, QStandardPaths, Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QIcon
    from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

    from muzbingo.ui.server import ServerError, start_server

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)  # before the app
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("MuzBingo")
    app.setApplicationDisplayName("MuzBingo")
    icon_path = Path(__file__).with_name("icon.svg")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    try:
        running = start_server("127.0.0.1", 0, data_dir)
    except ServerError as exc:
        QMessageBox.critical(None, "MuzBingo", str(exc))
        return 1
    local = QUrl(running.url)

    class Page(QWebEnginePage):
        """Keeps the app on the local server; other links go to the system browser."""

        def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:  # noqa: N802
            if is_main_frame and not _same_server(url, local):
                QDesktopServices.openUrl(url)
                return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        def createWindow(self, _type):  # noqa: N802  (target="_blank" links)
            return _ExternalLinkPage(self.profile(), self)

    class _ExternalLinkPage(QWebEnginePage):
        def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:  # noqa: N802
            QDesktopServices.openUrl(url)
            self.deleteLater()
            return False

    window = QMainWindow()
    window.setWindowTitle("MuzBingo")
    window.resize(*WINDOW_SIZE)
    view = QWebEngineView(window)
    profile = QWebEngineProfile.defaultProfile()
    page = Page(profile, view)
    view.setPage(page)
    window.setCentralWidget(view)

    last_dir = {"path": QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)}

    def on_download(item: QWebEngineDownloadRequest) -> None:
        suggested = os.path.join(last_dir["path"] or str(Path.home()), item.downloadFileName())
        target, _filter = QFileDialog.getSaveFileName(window, _("Save as"), suggested)
        if not target:
            item.cancel()
            return
        last_dir["path"] = os.path.dirname(target)
        item.setDownloadDirectory(os.path.dirname(target))
        item.setDownloadFileName(os.path.basename(target))
        item.isFinishedChanged.connect(lambda: _finished(item))
        item.accept()

    def _finished(item: QWebEngineDownloadRequest) -> None:
        if item.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            window.statusBar().showMessage(
                _("Saved: {path}").format(path=os.path.join(item.downloadDirectory(), item.downloadFileName())),
                8000,
            )
        elif item.state() == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            QMessageBox.warning(window, "MuzBingo", _("Could not save the file: {error}").format(
                error=item.interruptReasonString()))

    profile.downloadRequested.connect(on_download)
    view.titleChanged.connect(lambda title: window.setWindowTitle(title or "MuzBingo"))
    view.load(local)
    window.show()

    try:
        return app.exec()
    finally:
        running.stop()


def _same_server(url, local) -> bool:
    return url.scheme() in ("http", "https") and url.host() == local.host() and url.port() == local.port() \
        or url.scheme() in ("about", "data", "blob")
