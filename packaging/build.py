"""Build the MuzBingo app with PyInstaller: a folder plus a zip (Windows) or tarball (Linux).

    pip install -r requirements-build.txt
    pip install -e . --no-deps
    python packaging/build.py

Result in ``dist/``:
- ``dist/MuzBingo/``: the app folder (``MuzBingo.exe`` or ``MuzBingo`` plus ``_internal/``)
- Windows: ``MuzBingo-<version>-win64-portable.zip``, with ``portable.txt``: all data
  is kept in a ``data`` folder next to the program.
- Linux: ``MuzBingo-<version>-linux-x86_64.tar.gz``; data goes to ~/.local/share/MuzBingo.

Options: ``--portable`` / ``--no-portable`` overrides the default; ``--no-archive``
skips the zip/tarball. PyInstaller can't cross-compile: build on the target system.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DIST = ROOT / "dist"
WORK = ROOT / "build" / "pyinstaller"
APP_DIR = DIST / "MuzBingo"
LOCALE = SRC / "muzbingo" / "i18n" / "locale"
PORTABLE_NOTE = """This file makes MuzBingo portable: games, settings and your own card templates
are kept in the "data" folder next to the program instead of in your user profile.
Delete this file to use the user profile (%APPDATA%\\MuzBingo) instead.
"""


def version() -> str:
    sys.path.insert(0, str(SRC))
    from muzbingo import __version__

    return __version__


def compile_translations() -> None:
    try:
        from babel.messages.frontend import CommandLineInterface
    except ImportError:
        print("Babel not installed: using the committed .mo files")
        return
    CommandLineInterface().run(["pybabel", "-q", "compile", "-d", str(LOCALE), "-D", "muzbingo"])


def make_icon() -> Path | None:
    """Render the SVG app icon to a Windows .ico file."""
    if sys.platform != "win32":
        return None
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841  (needed to render)
    renderer = QSvgRenderer(str(SRC / "muzbingo" / "desktop" / "icon.svg"))
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    target = ROOT / "build" / "MuzBingo.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target), "ICO"):
        print("warning: could not write the .ico file; building without an icon")
        return None
    return target


def run_pyinstaller(icon: Path | None) -> None:
    env = dict(os.environ)
    if icon:
        env["MUZBINGO_ICON"] = str(icon)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(DIST), "--workpath", str(WORK), str(ROOT / "packaging" / "muzbingo.spec")],
        check=True, env=env, cwd=ROOT,
    )


def archive(portable: bool) -> Path:
    ver = version()
    if sys.platform == "win32":
        target = DIST / f"MuzBingo-{ver}-win64{'-portable' if portable else ''}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path in sorted(APP_DIR.rglob("*")):
                zf.write(path, Path("MuzBingo") / path.relative_to(APP_DIR))
    else:
        machine = platform.machine() or "x86_64"
        target = DIST / f"MuzBingo-{ver}-linux-{machine}{'-portable' if portable else ''}.tar.gz"
        with tarfile.open(target, "w:gz") as tf:
            tf.add(APP_DIR, arcname="MuzBingo")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--portable", action=argparse.BooleanOptionalAction, default=sys.platform == "win32",
                        help="keep the data next to the program (default: on for Windows)")
    parser.add_argument("--no-archive", action="store_true", help="only build the folder")
    args = parser.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is missing: pip install -r requirements-build.txt", file=sys.stderr)
        return 1

    if sys.platform.startswith("linux") and not shutil.which("objdump"):
        print("PyInstaller needs objdump on Linux: sudo apt install binutils", file=sys.stderr)
        return 1

    shutil.rmtree(APP_DIR, ignore_errors=True)
    compile_translations()
    run_pyinstaller(make_icon())
    portable_file = APP_DIR / "portable.txt"
    if args.portable:
        portable_file.write_text(PORTABLE_NOTE, encoding="utf-8")
    print(f"\nApp folder: {APP_DIR}  (portable: {'yes' if args.portable else 'no'})")
    if not args.no_archive:
        print(f"Archive:    {archive(args.portable)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
