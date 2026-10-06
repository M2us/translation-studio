"""Render the editable SVG into Windows ICO sizes and a repository preview PNG."""
from pathlib import Path
import os
import struct
import sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]


def main():
    app = QGuiApplication.instance() or QGuiApplication([])
    svg = QSvgRenderer(str(ROOT / "Assets/translation-studio.svg"))
    assert svg.isValid()
    entries, blobs = [], []
    sizes = (16, 24, 32, 48, 64, 128, 256)
    offset = 6 + len(sizes) * 16
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        svg.render(painter, QRectF(0, 0, size, size))
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        assert image.save(buffer, "PNG")
        blob = bytes(data)
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset))
        blobs.append(blob)
        offset += len(blob)
        if size == 256:
            image.save(str(ROOT / "Assets/translation-studio.png"))
    (ROOT / "Assets/translation-studio.ico").write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + blobs))


if __name__ == "__main__":
    main()
