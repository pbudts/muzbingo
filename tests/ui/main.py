"""NiceGUI test entry point: the UI wired to a library in a temporary folder."""

import os
from pathlib import Path

from nicegui import ui

from muzbingo.services import Library
from muzbingo.ui.app import setup

setup(Library(Path(os.environ["MUZBINGO_TEST_GAMES"])), pdf=None)
ui.run(storage_secret="test")
