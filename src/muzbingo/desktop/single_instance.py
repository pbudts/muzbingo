"""Run one MuzBingo window per data folder.

The first instance listens on a local socket (a named pipe on Windows). A second
start connects to it, asks it to show its window, and exits. The name depends on the
data folder, so a test copy with ``--data-dir`` can run next to the normal one.
Create after the QApplication.
"""

from __future__ import annotations

import getpass
import hashlib
from collections.abc import Callable
from pathlib import Path

SHOW = b"show\n"


def socket_name(data_dir: Path) -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001  (no user name available: still unique per folder)
        user = ""
    key = f"{user}:{data_dir.resolve()}".encode()
    return "MuzBingo-" + hashlib.sha1(key).hexdigest()[:16]


class SingleInstance:
    def __init__(self, data_dir: Path):
        self.name = socket_name(data_dir)
        self._server = None

    def activate_running(self, timeout_ms: int = 1000) -> bool:
        """If another instance runs, ask it to show its window and return True."""
        from PySide6.QtNetwork import QLocalSocket

        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write(SHOW)
        socket.flush()
        socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return True

    def listen(self, on_show: Callable[[], None]) -> bool:
        """Become the running instance; ``on_show`` is called when a second start asks."""
        from PySide6.QtNetwork import QLocalServer

        server = QLocalServer()
        if not server.listen(self.name):
            # A socket left behind by a crashed instance (Linux/macOS): remove and retry.
            QLocalServer.removeServer(self.name)
            if not server.listen(self.name):
                return False

        def on_connection() -> None:
            while server.hasPendingConnections():
                connection = server.nextPendingConnection()
                connection.readyRead.connect(lambda c=connection: _read(c))
                connection.disconnected.connect(connection.deleteLater)

        def _read(connection) -> None:
            if bytes(connection.readAll()).startswith(SHOW.strip()):
                on_show()

        server.newConnection.connect(on_connection)
        self._server = server
        return True

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
