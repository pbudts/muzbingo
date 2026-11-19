"""Make uploaded pictures a sensible size before they are stored in a game.

A photo straight from a phone can be 5000+ pixels wide and 10 MB. The game file
embeds its pictures, so a big photo makes every autosave and every PDF slow, while
a printed A4 page needs no more than about 3500 pixels (300 dpi).

Uses Qt's QImage, which is safe to use outside the Qt main thread for raster images.
SVG pictures are kept as they are: they scale without loss.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import PurePath

from muzbingo.models import Image

# Longest side in pixels.
MAX_SIDE = {
    "background": 3508,  # A4 at 300 dpi
    "logo": 1200,
}
# Pictures without transparency that are bigger than this are stored as JPEG.
RECOMPRESS_BYTES = 3 * 1024 * 1024
JPEG_QUALITY = 90
RASTER_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


class ImageError(Exception):
    """The picture could not be read."""


def prepare_image(image: Image, kind: str) -> Image:
    """Return ``image`` scaled down (and re-encoded) if it is larger than needed."""
    if image.mime not in RASTER_MIME_TYPES:
        return image
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
        from PySide6.QtGui import QImage, QImageReader
    except ImportError:  # no Qt: store the picture unchanged
        return image

    source = QBuffer()
    source.setData(QByteArray(image.data))
    source.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(source)
    reader.setAutoTransform(True)  # keep the camera's EXIF rotation when re-encoding
    picture = reader.read()
    if picture.isNull():
        raise ImageError(reader.errorString())

    max_side = MAX_SIDE.get(kind, MAX_SIDE["background"])
    too_big = max(picture.width(), picture.height()) > max_side
    alpha = picture.hasAlphaChannel()
    heavy = len(image.data) > RECOMPRESS_BYTES and not alpha
    if not (too_big or heavy):  # browsers apply EXIF rotation themselves
        return image

    if too_big:
        picture = picture.scaled(
            max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    fmt, mime, suffix = ("PNG", "image/png", ".png") if alpha else ("JPEG", "image/jpeg", ".jpg")
    target = QBuffer()
    target.open(QIODevice.OpenModeFlag.WriteOnly)
    if not picture.save(target, fmt, -1 if alpha else JPEG_QUALITY):
        return image
    data = bytes(target.data())
    if not too_big and len(data) >= len(image.data):
        return image  # re-encoding didn't help
    filename = str(PurePath(image.filename).with_suffix(suffix)) if image.filename else f"{kind}{suffix}"
    return replace(image, filename=filename, mime=mime, data=data)
