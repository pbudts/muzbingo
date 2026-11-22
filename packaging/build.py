"""Build the MuzBingo app with PyInstaller: a folder plus a zip (Windows) or tarball (Linux).

    pip install -r requirements-build.txt
    pip install -e . --no-deps
    python packaging/build.py

Result in ``dist/``:
- ``dist/MuzBingo/``: the app folder (``MuzBingo.exe`` or ``MuzBingo`` plus ``_internal/``)
- Windows: ``MuzBingo-<version>-win64-portable.zip``, with ``portable.txt``: all data
  is kept in a ``data`` folder next to the program.
- Linux: ``MuzBingo-<version>-linux-x86_64.tar.gz``; data goes to ~/.local/share/MuzBingo.

The app folder also gets ``LICENSE.txt`` (GPL-3.0), ``THIRD-PARTY-NOTICES.txt`` and a
``licenses/`` folder with the license texts of everything bundled (Python, Qt, the
Python packages from requirements.txt).

Options: ``--portable`` / ``--no-portable`` overrides the default; ``--no-archive``
skips the zip/tarball. PyInstaller can't cross-compile: build on the target system.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
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
SOURCE_URL = "https://github.com/pbudts/muzbingo"
LICENSE_FILE = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)
QT_NOTICE = """\
Qt and Qt for Python (PySide6 {pyside}, Qt {qt})
================================================

MuzBingo uses Qt, Qt WebEngine and Qt for Python (PySide6, shiboken6) under the GNU
Lesser General Public License version 3 (LGPL-3.0, in this folder, together with the
GNU GPL-3.0 it builds on). They are unmodified and installed as separate library files
in the "_internal" folder, so you can replace them with other compatible versions.

Source code:
- Qt:             https://download.qt.io/official_releases/qt/  (or https://code.qt.io)
- Qt for Python:  https://download.qt.io/official_releases/QtForPython/

Qt WebEngine contains Chromium, which includes third-party code under various
licenses (mostly BSD, MIT, Apache-2.0, LGPL and MPL). The full list, with all license
texts, is in the Qt documentation:
  https://doc.qt.io/qt-6/qtwebengine-licensing.html
"""
NICEGUI_NOTE = """\
NiceGUI (_internal/nicegui) includes third-party web libraries, such as Vue, Quasar,
AG Grid Community, socket.io, Tailwind CSS, UnoCSS and DOMPurify, plus the libraries
behind its other elements. Most keep their copyright and license notice at the top of
their file. They are under MIT-style licenses; DOMPurify is under Apache-2.0 or MPL-2.0.
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


def runtime_distributions():
    """The installed packages from requirements.txt that apply to this system."""
    from importlib import metadata

    from packaging.requirements import Requirement

    found = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        found.append(metadata.distribution(requirement.name))
    return sorted(found, key=lambda d: d.metadata["Name"].casefold())


def license_name(dist) -> str:
    meta = dist.metadata
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    text = (meta.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 80:
        return text
    classifiers = [c.split(" :: ")[-1] for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classifiers) or "see the license files"


def license_files(dist) -> list:
    """The license files in a package's .dist-info folder."""
    files = []
    for file in dist.files or []:
        parts = file.parts
        if not parts[0].endswith(".dist-info"):
            continue
        if (len(parts) > 2 and parts[1] == "licenses") or (len(parts) == 2 and LICENSE_FILE.match(parts[1])):
            files.append(file)
    return files


def home_page(dist) -> str:
    meta = dist.metadata
    if meta.get("Home-page"):
        return meta["Home-page"]
    for url in meta.get_all("Project-URL") or []:
        label, _, link = url.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "source code"):
            return link.strip()
    return ""


def collect_licenses(target: Path) -> None:
    """Write LICENSE.txt, THIRD-PARTY-NOTICES.txt and licenses/ into the app folder ``target``."""
    import PySide6
    from PySide6.QtCore import qVersion

    folder = target / "licenses"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    shutil.copyfile(ROOT / "LICENSE", target / "LICENSE.txt")
    shutil.copyfile(SRC / "muzbingo" / "templates" / "LICENSE", folder / "MuzBingo-card-templates-CC0-1.0.txt")

    lines = [
        f"MuzBingo {version()}",
        "=" * 40,
        "",
        "MuzBingo is free software under the GNU General Public License, version 3 or",
        "later (LICENSE.txt). The card templates (_internal/muzbingo/templates) and the",
        "host sheet template are under CC0-1.0: the cards and sheets you print are yours,",
        "without conditions.",
        f"Source code: {SOURCE_URL}",
        "",
        "MuzBingo includes the following software. The license texts are in the",
        '"licenses" folder.',
        "",
    ]

    python = folder / "Python"
    python.mkdir()
    for candidate in (Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"):
        if candidate.is_file():
            shutil.copyfile(candidate, python / "LICENSE.txt")
            break
    lines.append(f"- Python {platform.python_version()}: PSF-2.0  https://www.python.org")

    qt = folder / "Qt"
    qt.mkdir()
    shutil.copyfile(ROOT / "packaging" / "licenses" / "LGPL-3.0.txt", qt / "LGPL-3.0.txt")
    shutil.copyfile(ROOT / "LICENSE", qt / "GPL-3.0.txt")
    (qt / "NOTICE.txt").write_text(
        QT_NOTICE.format(pyside=PySide6.__version__, qt=qVersion()), encoding="utf-8"
    )

    for dist in runtime_distributions():
        name, ver = dist.metadata["Name"], dist.version
        url = home_page(dist)
        lines.append(f"- {name} {ver}: {license_name(dist)}" + (f"  {url}" if url else ""))
        files = license_files(dist)
        if files:
            out = folder / name
            out.mkdir(exist_ok=True)
            for file in files:
                parts = file.parts[2:] if file.parts[1] == "licenses" else file.parts[1:]
                dest = out.joinpath(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(dist.locate_file(file), dest)
    lines += ["", "Qt / PySide6: see licenses/Qt/NOTICE.txt.", "", NICEGUI_NOTE]
    (target / "THIRD-PARTY-NOTICES.txt").write_text("\n".join(lines), encoding="utf-8")


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
    collect_licenses(APP_DIR)
    portable_file = APP_DIR / "portable.txt"
    if args.portable:
        portable_file.write_text(PORTABLE_NOTE, encoding="utf-8")
    print(f"\nApp folder: {APP_DIR}  (portable: {'yes' if args.portable else 'no'})")
    if not args.no_archive:
        print(f"Archive:    {archive(args.portable)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
