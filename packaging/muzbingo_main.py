"""Entry point of the built app (PyInstaller). Without arguments it opens the window."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()  # harmless; needed if a library ever starts a process
    from muzbingo.cli import main

    sys.exit(main())
