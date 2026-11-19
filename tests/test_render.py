from datetime import date

import pytest

pytest.importorskip("jinja2")

from muzbingo.models import Image, Song  # noqa: E402
from muzbingo.render import RenderError, export_html, load_template  # noqa: E402
from muzbingo.render.context import build_context, fit_class, format_date  # noqa: E402
from muzbingo.render.templates import TemplateError, list_templates  # noqa: E402


@pytest.fixture
def classic():
    return load_template("classic")


def test_bundled_template(classic):
    assert classic.display_name == "Classic"
    assert classic.orientation == "landscape"
    assert classic.asset(classic.background) is not None
    assert classic.asset(classic.logo) is not None
    assert "classic" in [t.name for t in list_templates()]


def test_template_names_are_checked():
    with pytest.raises(TemplateError):
        load_template("../classic")
    with pytest.raises(TemplateError):
        load_template("does-not-exist")


def test_date_formats(classic):
    d = date(2026, 12, 9)
    assert format_date(d, "nl", classic.date_formats) == "09/12/2026"
    assert format_date(d, "en", classic.date_formats) == "9 Dec 2026"
    assert format_date(d, "nl", {"nl": "{day} {month_long} {year}"}) == "9 december 2026"
    assert format_date(None, "en") == ""


def test_labels(classic):
    assert classic.label_set("nl")["card"] == "Kaart"
    assert classic.label_set("en")["card"] == "Card"
    assert classic.label_set("fr")["card"] == "Card"  # falls back to English


def test_fit_class():
    assert fit_class(Song(title="Hello", artist="Adele"), 44) == "normal"
    assert fit_class(Song(title="x" * 30, artist="y" * 10), 44) == "small"
    assert fit_class(Song(title="x" * 40, artist="y" * 10), 44) == "tiny"
    long = Song(title="x" * 40, artist="y" * 10, display_title="Short")
    assert fit_class(long, 44) == "normal"  # the edited text counts


def test_context_uses_display_texts(game, classic):
    game.playlist[0].display_title = "SHORT"
    game.language = "nl"
    game.event_date = date(2026, 12, 19)
    ctx = build_context(game, classic)

    assert len(ctx["cards"]) == 5
    assert len(ctx["cards"][0]["rows"]) == 4
    assert len(ctx["cards"][0]["rows"][0]) == 5
    titles = {cell["title"] for card in ctx["cards"] for row in card["rows"] for cell in row}
    assert "Title 1" not in titles
    assert ctx["date_text"] == "19/12/2026"
    assert ctx["labels"]["card"] == "Kaart"


def test_context_errors(game, classic):
    game.playlist.clear()  # the cards now refer to songs that no longer exist
    with pytest.raises(RenderError, match="no longer in the playlist"):
        build_context(game, classic)
    game.cards = []
    with pytest.raises(RenderError, match="generate the cards"):
        build_context(game, classic)


def test_export_html(tmp_path, game, classic):
    game.title = "Rock & Roll <Night>"
    game.event_date = date(2026, 12, 19)
    game.logo = Image(filename="mine.png", mime="image/png", data=b"png")
    out = export_html(game, tmp_path / "cards.html", classic)
    html = out.read_text(encoding="utf-8")

    assert "Rock &amp; Roll &lt;Night&gt;" in html  # escaped
    assert html.count('<section class="card">') == 5
    assert "Card 5" in html
    assert "19 Dec 2026" in html
    assert (tmp_path / "cards_files" / "logo.png").read_bytes() == b"png"
    assert "background.svg" in html  # template default background
    assert classic.path.as_uri() in html  # stylesheet from the template folder


def test_export_pdf(tmp_path, game):
    pytest.importorskip("PySide6.QtWebEngineCore")
    from muzbingo.render import export_pdf

    out = export_pdf(game, tmp_path / "cards.pdf")

    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
