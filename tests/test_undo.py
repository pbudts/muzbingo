import pytest

from muzbingo.services import GameService, Library, ServiceError
from muzbingo.services import game_service as gs


@pytest.fixture
def service(tmp_path, game):
    library = Library(tmp_path / "games")
    library.save(game)
    return GameService(library, game)


def test_undo_redo_setting(service, tmp_path):
    service.update(rows=5)
    assert service.can_undo and not service.can_redo
    assert service.undo()
    assert service.game.rows == 4
    assert service.library.load(service.game.id).rows == 4  # undo is saved too
    assert service.redo()
    assert service.game.rows == 5
    assert not service.redo()


def test_undo_keeps_the_same_game_object(service):
    game = service.game
    service.update(title="New")
    service.undo()
    assert service.game is game and game.title != "New"


def test_typing_is_one_step(service):
    original = service.game.title
    for text in ("K", "Ke", "Ker"):
        service.update(title=text)
    service.undo()
    assert service.game.title == original
    assert not service.can_undo


def test_separate_steps_after_a_pause(service, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(gs.time, "monotonic", lambda: clock[0])
    service.update(title="A")
    clock[0] += gs.COALESCE_SECONDS + 1
    service.update(title="B")
    service.undo()
    assert service.game.title == "A"


def test_no_step_without_change_or_on_error(service):
    service.update(rows=service.game.rows)
    assert not service.can_undo
    with pytest.raises(ServiceError):
        service.update(title="Changed", rows=99)
    assert service.game.title != "Changed"  # rolled back
    assert not service.can_undo


def test_bulk_delete_is_one_step(service):
    ids = [s.id for s in service.game.playlist[:3]]
    n = len(service.game.playlist)
    service.delete_songs(ids)
    assert len(service.game.playlist) == n - 3
    service.undo()
    assert len(service.game.playlist) == n


def test_new_change_clears_redo(service):
    service.update(rows=5)
    service.undo()
    service.update(cols=4)
    assert not service.can_redo


def test_history_is_limited(service, monkeypatch):
    monkeypatch.setattr(gs, "HISTORY_SIZE", 3)
    clock = [100.0]
    monkeypatch.setattr(gs.time, "monotonic", lambda: clock[0])
    for seed in range(5):
        clock[0] += gs.COALESCE_SECONDS + 1
        service.update(seed=1000 + seed)
    assert len(service._undo) == 3


def test_cleanup(service):
    song = service.game.playlist[0]
    service.edit_song(song.id, title="Hey Jude - Remastered 2015")
    other = service.game.playlist[1]
    service.edit_song(other.id, title="Let It Be (Live)")
    suggestions = {s.id: new for s, new in service.cleanup_suggestions()}
    assert suggestions == {song.id: "Hey Jude", other.id: "Let It Be"}
    assert service.apply_cleanup([song.id]) == 1
    assert song.shown_title == "Hey Jude"
    assert other.shown_title == "Let It Be (Live)"
    service.undo()
    assert service.song(song.id).shown_title == "Hey Jude - Remastered 2015"
