# PyInstaller spec for MuzBingo: a "onedir" build (a folder with MuzBingo[.exe] and
# _internal/). Build with:  python packaging/build.py
# See ARCHITECTURE.md, section 6, for why onedir and not onefile.

import os
import re
import sys
from pathlib import Path, PurePath

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
ICON = os.environ.get("MUZBINGO_ICON")  # made by build.py (.ico on Windows)

# Our own data files: card templates, the host sheet template, translations, the icon.
datas = collect_data_files("muzbingo", excludes=["**/__pycache__/*", "**/*.po", "**/*.pot"])
# NiceGUI's web assets come from the hook in pyinstaller-hooks-contrib.

a = Analysis(
    [str(ROOT / "packaging" / "muzbingo_main.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=collect_submodules("muzbingo"),  # many imports are inside functions
    excludes=["tkinter", "pytest", "IPython", "matplotlib", "babel"],
    noarchive=False,
)
# -- leave out what MuzBingo never uses ---------------------------------------------
# PyInstaller's QML hook collects every QML plugin, and with them Qt 3D, Charts,
# Multimedia, Quick3D, ... (about 120 MB). MuzBingo uses Qt WebEngine with widgets
# only, which needs Qt Quick/Qml themselves but none of these. The names match both
# libQt6Xxx.so* (Linux) and Qt6Xxx.dll (Windows).
UNUSED_QT = re.compile(
    r"^(lib)?Qt6(3D|Charts|DataVisualization|Graphs|Labs|Location|Multimedia|Quick3D|"
    r"QuickControls2|QuickDialogs2|QuickEffects|QuickLayouts|QuickParticles|QuickShapes|"
    r"QuickTemplates2|QuickTest|QuickTimeline|QuickVectorImage|RemoteObjects|Scxml|Sensors|"
    r"ShaderTools|SpatialAudio|StateMachine|TextToSpeech|VirtualKeyboard|WaylandCompositor|"
    r"WebChannelQuick|WebEngineQuick|WebView|PdfQuick|PositioningQuick|QmlDesignSupport|"
    r"QmlLocalStorage|QmlXmlListModel)",
    re.IGNORECASE,
)
KEEP_LANGUAGES = ("en", "en-US", "en-GB", "nl")  # Chromium and Qt texts: English and Dutch


def wanted(dest: str) -> bool:
    parts = PurePath(dest).parts
    name = parts[-1]
    if "PySide6" in parts and "qml" in parts:  # QML plugins and their files
        return False
    if UNUSED_QT.match(name):
        return False
    if "qtwebengine_locales" in parts:  # e.g. nl.pak; en-US.pak is the fallback
        return PurePath(name).stem in KEEP_LANGUAGES
    if "translations" in parts and name.endswith(".qm"):  # e.g. qtbase_nl.qm
        return PurePath(name).stem.rsplit("_", 1)[-1] in KEEP_LANGUAGES
    return True


a.binaries = [entry for entry in a.binaries if wanted(entry[0])]
a.datas = [entry for entry in a.datas if wanted(entry[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MuzBingo",
    console=False,  # a window app: no console window on Windows
    icon=ICON if ICON and sys.platform == "win32" else None,
    upx=False,  # UPX-packed Qt files are slow to start and trip up antivirus software
)
coll = COLLECT(exe, a.binaries, a.datas, name="MuzBingo", upx=False)
