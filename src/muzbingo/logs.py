"""Log to ``<data folder>/logs/muzbingo.log`` in the app window.

The Windows build has no console: ``sys.stdout`` and ``sys.stderr`` are ``None`` there,
and anything that prints (uvicorn, Qt messages, a crash) would fail or vanish. In app
mode, both streams and uncaught exceptions go to the log file instead.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "muzbingo.log"
MAX_BYTES = 1_000_000
BACKUPS = 3


def ensure_std_streams() -> None:
    """Give a windowed app (no console) harmless stdout/stderr, so printing never fails."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


class _LogStream:
    """A text stream that writes complete lines to a logger."""

    def __init__(self, logger: logging.Logger, level: int, original):
        self.logger, self.level, self.original = logger, level, original
        self._buffer = ""

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.logger.log(self.level, line.rstrip())
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return self.original.fileno()  # e.g. faulthandler; the original stream's descriptor

    @property
    def encoding(self) -> str:
        return "utf-8"


def setup_file_logging(data_dir: Path, *, capture_streams: bool) -> Path:
    """Log to a rotating file in ``data_dir/logs``; returns the log file path.

    ``capture_streams``: also send stdout/stderr there (for the windowed app).
    """
    folder = data_dir / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOG_NAME
    handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    if capture_streams:
        sys.stdout = _LogStream(logging.getLogger("stdout"), logging.INFO, sys.stdout)
        sys.stderr = _LogStream(logging.getLogger("stderr"), logging.WARNING, sys.stderr)

    def log_uncaught(exc_type, exc, tb) -> None:
        if not issubclass(exc_type, KeyboardInterrupt):
            logging.getLogger("muzbingo").critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = log_uncaught
    return path
