"""UI translations with gettext.

All user-facing UI text is written in English and wrapped in ``_()``. The Dutch
catalog (``locale/nl/LC_MESSAGES/muzbingo.po``) is added in phase 5; until then
``_()`` simply returns the English text.

MuzBingo is a single-user local app, so one process-wide language is enough.
"""

from __future__ import annotations

import gettext as _gettext
from pathlib import Path

DOMAIN = "muzbingo"
LANGUAGES = {"en": "English", "nl": "Nederlands"}
LOCALE_DIR = Path(__file__).resolve().parent / "locale"

_translations: _gettext.NullTranslations = _gettext.NullTranslations()
_language = "en"


def set_language(language: str) -> None:
    global _translations, _language
    _language = language if language in LANGUAGES else "en"
    _translations = _gettext.translation(
        DOMAIN, localedir=LOCALE_DIR, languages=[_language], fallback=True
    )


def current_language() -> str:
    return _language


def _(message: str) -> str:
    return _translations.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translations.ngettext(singular, plural, n)
