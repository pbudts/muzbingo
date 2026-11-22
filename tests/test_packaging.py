"""The license files that packaging/build.py adds to the app folder."""

import importlib.util
from pathlib import Path

from muzbingo.render import list_templates

ROOT = Path(__file__).resolve().parents[1]


def load_build():
    spec = importlib.util.spec_from_file_location("muzbingo_build", ROOT / "packaging" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_licenses(tmp_path):
    load_build().collect_licenses(tmp_path)
    assert "GNU GENERAL PUBLIC LICENSE" in (tmp_path / "LICENSE.txt").read_text()
    notices = (tmp_path / "THIRD-PARTY-NOTICES.txt").read_text()
    assert "nicegui" in notices and "PySide6" in notices and "CC0-1.0" in notices
    licenses = tmp_path / "licenses"
    assert "LESSER" in (licenses / "Qt" / "LGPL-3.0.txt").read_text()
    assert "download.qt.io" in (licenses / "Qt" / "NOTICE.txt").read_text()
    assert any((licenses / "nicegui").iterdir())
    assert "CC0" in (licenses / "MuzBingo-card-templates-CC0-1.0.txt").read_text()


def test_templates_license_is_not_a_template():
    assert (ROOT / "src" / "muzbingo" / "templates" / "LICENSE").is_file()
    assert [t.name for t in list_templates([ROOT / "src" / "muzbingo" / "templates"])] == ["classic"]
