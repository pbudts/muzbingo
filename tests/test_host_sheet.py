import pytest

from muzbingo.render import HostOrder, RenderError, render_host_sheet
from muzbingo.render.host_sheet import ordered_songs


def test_orders(game):
    by_artist = ordered_songs(game, HostOrder.ARTIST)
    assert [s.shown_artist.casefold() for s in by_artist] == sorted(s.shown_artist.casefold() for s in by_artist)
    shuffled = ordered_songs(game, "shuffled")
    assert shuffled == ordered_songs(game, "shuffled")  # the same order every time
    assert shuffled != list(game.playlist)
    assert ordered_songs(game, "playlist") == list(game.playlist)


def test_render(game):
    html = render_host_sheet(game, HostOrder.TITLE)
    assert game.title in html
    assert html.count('<td class="title">') == len(game.playlist)
    assert "Sorted by title" in html


def test_render_dutch_and_escaping(game):
    game.language = "nl"
    game.playlist[0].display_title = "<b>Rock & Roll</b>"
    html = render_host_sheet(game)
    assert "Gespeeld" in html
    assert "&lt;b&gt;Rock &amp; Roll&lt;/b&gt;" in html


def test_empty_playlist(game):
    game.playlist = []
    with pytest.raises(RenderError):
        render_host_sheet(game)
