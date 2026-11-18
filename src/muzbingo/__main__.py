"""Allow ``python -m muzbingo``. Runs the command-line interface (the GUI comes in phase 2)."""

from muzbingo.cli import main

raise SystemExit(main())
