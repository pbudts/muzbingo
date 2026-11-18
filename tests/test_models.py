from datetime import date

from muzbingo.models import Game, Image, Song, make_song_id


def test_song_id_is_stable_and_case_insensitive():
    assert make_song_id("Wham!", "Last Christmas") == make_song_id(" wham! ", "LAST CHRISTMAS")
    assert make_song_id("Wham!", "Last Christmas") != make_song_id("Wham!", "Club Tropicana")


def test_song_gets_id_when_missing():
    assert Song(title="T", artist="A").id == make_song_id("A", "T")
    assert Song(title="T", artist="A", id="spotify:track:1").id == "spotify:track:1"


def test_display_texts_fall_back_to_original():
    song = Song(title="Last Christmas - Remastered", artist="Wham!")
    assert song.shown_title == "Last Christmas - Remastered"
    song.display_title = "Last Christmas"
    assert song.shown_title == "Last Christmas"
    assert song.shown_artist == "Wham!"


def test_editing_display_text_keeps_id():
    song = Song(title="Long title", artist="A")
    before = song.id
    song.display_title = "Short"
    assert song.id == before


def test_game_round_trip(game):
    game.event_date = date(2026, 12, 19)
    game.language = "nl"
    game.logo = Image(filename="logo.png", mime="image/png", data=b"\x89PNG data")
    game.playlist[0].display_title = "Short"
    game.played = [game.playlist[0].id]

    copy = Game.from_dict(game.to_dict())

    assert copy == game


def test_image_from_file(tmp_path):
    path = tmp_path / "bg.JPG"
    path.write_bytes(b"jpegdata")
    image = Image.from_file(path)
    assert image.mime == "image/jpeg"
    assert image.suffix == ".jpg"
    assert image.data == b"jpegdata"
