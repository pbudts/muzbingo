import json

from muzbingo import paths, settings
from muzbingo.settings import Settings, system_language


def test_defaults_without_file():
    s = settings.get()
    assert (s.template, s.rows, s.cols, s.n_cards, s.ui_language) == ("classic", 4, 5, 30, None)


def test_update_is_saved():
    settings.update(ui_language="nl", rows=5)
    data = json.loads(paths.settings_file().read_text())
    assert data["ui_language"] == "nl" and data["rows"] == 5
    settings.reset()
    assert settings.get().rows == 5


def test_broken_file_gives_defaults():
    paths.settings_file().parent.mkdir(parents=True, exist_ok=True)
    paths.settings_file().write_text("{not json")
    assert settings.load() == Settings()
    paths.settings_file().write_text(json.dumps({"rows": "x", "ui_language": "fr", "unknown": 1}))
    s = settings.load()
    assert s.rows == 4 and s.ui_language is None


def test_system_language(monkeypatch):
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", "nl_BE.UTF-8")
    assert system_language() == "nl"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert system_language() == "en"
    assert Settings(ui_language="nl").language() == "nl"
