import asyncio
import threading
import time
from datetime import date

import pytest

from muzbingo.importers import ColumnMapping, MappingRequired
from muzbingo.models import Image
from muzbingo.services import GameService, Library, ServiceError


@pytest.fixture
def library(tmp_path):
    return Library(tmp_path / "games")


@pytest.fixture
def service(library, game):
    library.save(game)
    return GameService.open(library, game.id)


def reload(service):
    return service.library.load(service.game.id)


def write_csv(tmp_path, rows, header="Title,Artist"):
    path = tmp_path / "playlist.csv"
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_update_settings_is_saved(service):
    service.update(title="Kerstfeest", event_date=date(2026, 12, 19), language="nl", rows=5, cols=5)
    g = reload(service)
    assert (g.title, g.event_date, g.language, g.rows, g.cols) == ("Kerstfeest", date(2026, 12, 19), "nl", 5, 5)

    service.update(title="Other")  # leaves the date alone
    assert reload(service).event_date == date(2026, 12, 19)
    service.update(event_date=None)
    assert reload(service).event_date is None


def test_update_validates(service):
    with pytest.raises(ServiceError):
        service.update(rows=1)
    with pytest.raises(ServiceError):
        service.update(n_cards=0)
    with pytest.raises(ServiceError):
        service.update(language="xx")


def test_settings_that_change_cards(service):
    assert not service.game.cards_outdated
    service.update(title="New title", language="nl")
    assert not service.game.cards_outdated
    service.update(cols=4)
    assert service.game.cards_outdated
    service.generate()
    assert not service.game.cards_outdated
    assert all(len(row) == 4 for row in service.game.cards[0].cells)


def test_edit_and_reset_song(service):
    song = service.game.playlist[0]
    service.edit_song(song.id, title="  Short   title ")
    assert reload(service).playlist[0].display_title == "Short title"
    assert reload(service).playlist[0].shown_artist == song.artist

    service.edit_song(song.id, title=song.title)  # back to the original: no override
    assert reload(service).playlist[0].display_title is None

    service.edit_song(song.id, artist="X")
    service.reset_song(song.id)
    assert reload(service).playlist[0].display_artist is None
    assert not service.game.cards_outdated  # display texts don't change the cards


def test_add_and_delete_song(service):
    song = service.add_song("New Song", "New Artist")
    assert service.game.cards_outdated
    with pytest.raises(ServiceError):
        service.add_song("new song", "NEW ARTIST")
    with pytest.raises(ServiceError):
        service.add_song("", "x")
    service.delete_song(song.id)
    assert not service.game.cards_outdated
    with pytest.raises(ServiceError):
        service.delete_song(song.id)


def test_import_replace_and_append(service, tmp_path):
    path = write_csv(tmp_path, ["Hello,Adele", "Title 1,Artist 1"])
    result = service.import_playlist(path)
    assert [s.title for s in reload(service).playlist] == ["Hello", "Title 1"]
    assert len(result.songs) == 2

    path = write_csv(tmp_path, ["Skyfall,Adele", "hello,adele"])
    result = service.import_playlist(path, append=True)
    assert [s.title for s in reload(service).playlist] == ["Hello", "Title 1", "Skyfall"]
    assert [s.title for s in result.songs] == ["Skyfall"]
    assert any("Already in the playlist" in w for w in result.warnings)


def test_import_with_mapping(service, tmp_path):
    path = write_csv(tmp_path, ["Hello,Adele"], header="Nummer,Zanger")
    with pytest.raises(MappingRequired):
        service.import_playlist(path)
    service.import_playlist(path, ColumnMapping(title="Nummer", artist="Zanger"))
    assert reload(service).playlist[0].artist == "Adele"


def test_playlist_status(service):
    service.update(rows=4, cols=5)
    status = service.playlist_status()
    assert status.can_generate and status.message == ""  # 60 songs for 20 per card

    for song in service.game.playlist[30:]:
        service.delete_song(song.id)
    status = service.playlist_status()
    assert status.can_generate and "Tip" in status.message

    service.update(rows=8, cols=8)
    status = service.playlist_status()
    assert not status.can_generate
    with pytest.raises(ServiceError):
        service.generate()


def test_images(service):
    service.set_image("logo", Image(filename="l.png", mime="image/png", data=b"x"))
    assert reload(service).logo.data == b"x"
    service.set_image("logo", None)
    assert reload(service).logo is None


def test_too_long(service):
    song = service.add_song("A very long title that will never fit in one cell", "Somebody")
    assert service.too_long(song)
    service.edit_song(song.id, title="Short")
    assert not service.too_long(song)


def test_pdf_service_across_threads(game):
    """Same setup as the real server: asyncio in a thread, Qt on the main thread."""
    pytest.importorskip("PySide6.QtWebEngineCore")
    from PySide6.QtCore import QCoreApplication, QEventLoop

    from muzbingo.render.pdf import ensure_qt_app
    from muzbingo.services.pdf_service import PdfService

    ensure_qt_app()
    service = PdfService()
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        future = asyncio.run_coroutine_threadsafe(service.render(game), loop)
        deadline = time.monotonic() + 60
        while not future.done() and time.monotonic() < deadline:
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        pdf = future.result(timeout=0)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)

    assert pdf.startswith(b"%PDF")
