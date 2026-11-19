import sys
import time

import pytest

pytest.importorskip("PySide6.QtNetwork")

from muzbingo.desktop.single_instance import SingleInstance, socket_name  # noqa: E402
from muzbingo.logs import setup_file_logging  # noqa: E402
from muzbingo.render.pdf import ensure_qt_app  # noqa: E402


def pump(condition, timeout: float = 3.0) -> bool:
    from PySide6.QtCore import QCoreApplication

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_second_start_shows_the_first(tmp_path):
    ensure_qt_app()
    first, second = SingleInstance(tmp_path), SingleInstance(tmp_path)
    assert not second.activate_running(timeout_ms=200)  # nothing runs yet
    shown = []
    assert first.listen(lambda: shown.append(True))
    try:
        assert second.activate_running()
        assert pump(lambda: shown)
    finally:
        first.close()
    assert not SingleInstance(tmp_path).activate_running(timeout_ms=200)


def test_name_depends_on_data_folder(tmp_path):
    assert socket_name(tmp_path / "a") != socket_name(tmp_path / "b")
    assert socket_name(tmp_path / "a") == socket_name(tmp_path / "a")


def test_log_file_captures_streams(tmp_path, monkeypatch):
    import logging

    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    try:
        path = setup_file_logging(tmp_path, capture_streams=True)
        print("hello from stdout")
        print("a warning on stderr", file=sys.stderr)
        for handler in root.handlers:
            handler.flush()
        text = path.read_text()
        assert "hello from stdout" in text and "WARNING stderr: a warning on stderr" in text
    finally:
        for handler in root.handlers[:]:
            if handler not in handlers:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(level)
