"""The Dutch translation must be complete and the compiled catalog up to date."""

import gettext
import re
from pathlib import Path

import pytest

from muzbingo.i18n import DOMAIN, LOCALE_DIR, _, set_language

babel = pytest.importorskip("babel")
from babel.messages.extract import extract_from_dir  # noqa: E402
from babel.messages.pofile import read_po  # noqa: E402

SOURCE = Path(__file__).resolve().parents[1] / "src" / "muzbingo"
PO_FILE = LOCALE_DIR / "nl" / "LC_MESSAGES" / f"{DOMAIN}.po"


def placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{(\w*)", text))


@pytest.fixture(scope="module")
def catalog():
    with open(PO_FILE, "rb") as f:
        return {m.id: m.string for m in read_po(f) if m.id}


def test_every_ui_string_is_translated(catalog):
    found = {
        message
        for _file, _line, message, _comments, _context in extract_from_dir(
            SOURCE, method_map=[("**.py", "python")], keywords={"_": None, "ngettext": (1, 2)}
        )
    }
    missing = sorted(m for m in found if isinstance(m, str) and m not in catalog)
    assert not missing, "Add these to the Dutch .po file (see README, Translations):\n" + "\n".join(missing)


def test_placeholders_match(catalog):
    wrong = [(k, v) for k, v in catalog.items() if not v or placeholders(k) != placeholders(v)]
    assert not wrong


def test_compiled_catalog_is_up_to_date(catalog):
    compiled = gettext.translation(DOMAIN, localedir=LOCALE_DIR, languages=["nl"])
    stale = [k for k, v in catalog.items() if compiled.gettext(k) != v]
    assert not stale, "Run: pybabel compile -d src/muzbingo/i18n/locale -D muzbingo"


def test_switching_language():
    set_language("nl")
    assert _("My games") == "Mijn spellen"
    set_language("en")
    assert _("My games") == "My games"
    set_language("xx")  # unknown: English
    assert _("My games") == "My games"
