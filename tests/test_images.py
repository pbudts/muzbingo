import pytest

pytest.importorskip("PySide6.QtGui")

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402

from muzbingo.images import MAX_SIDE, ImageError, prepare_image  # noqa: E402
from muzbingo.models import Image  # noqa: E402


def encode(width: int, height: int, fmt: str, alpha: bool = False) -> bytes:
    picture = QImage(width, height, QImage.Format.Format_ARGB32 if alpha else QImage.Format.Format_RGB32)
    picture.fill(0x804080C0 if alpha else 0xFF4080C0)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert picture.save(buffer, fmt)
    return bytes(buffer.data())


def size_of(image: Image) -> tuple[int, int]:
    picture = QImage.fromData(image.data)
    return picture.width(), picture.height()


def test_small_picture_is_kept():
    image = Image("logo.png", "image/png", encode(300, 200, "PNG", alpha=True))
    assert prepare_image(image, "logo") is image


def test_large_photo_is_scaled_down():
    image = Image("photo.jpeg", "image/jpeg", encode(5000, 2500, "JPEG"))
    result = prepare_image(image, "background")
    assert size_of(result) == (MAX_SIDE["background"], MAX_SIDE["background"] // 2)
    assert result.mime == "image/jpeg" and result.filename == "photo.jpg"


def test_transparent_logo_stays_png():
    image = Image("logo.webp", "image/webp", encode(2400, 1200, "PNG", alpha=True))
    result = prepare_image(image, "logo")
    assert size_of(result) == (MAX_SIDE["logo"], MAX_SIDE["logo"] // 2)
    assert result.mime == "image/png" and result.filename == "logo.png"
    assert QImage.fromData(result.data).hasAlphaChannel()


def test_svg_is_untouched():
    image = Image("logo.svg", "image/svg+xml", b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    assert prepare_image(image, "logo") is image


def test_broken_picture():
    with pytest.raises(ImageError):
        prepare_image(Image("x.png", "image/png", b"not a picture"), "logo")
