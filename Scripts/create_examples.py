"""Create copyright-free fixtures; never overwrite existing projects."""
import argparse
import math
from pathlib import Path
import shutil
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Source"))
from translation_studio.core import read_json, atomic_write, source_revision
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
from PySide6.QtCore import Qt


def example_readme(variant):
    text = (
        f"# Synthetic {variant}\n\n"
        "A standalone teaching project. It contains no ROM and is not a translation of a real game.\n\n"
        "Copy this folder before experimenting. Open it in Translation Studio, edit a target field "
        "in the detail panel, save, and click **Rebuild patch**. Outputs are "
        "`Builds/Patch/translation.bin` and `manifest.json`. The button needs "
        "`Tools/DemoBuilder.exe` included with the portable distribution.\n\n"
        "From source, install Python 3.12 and jsonschema, then run "
        "`python Scripts/build.py --sdk <path-to-Source-or-SDK> --language ru` from this folder. "
        "NES writes length-prefixed UTF-8; Sega writes UTF-16LE with an offset table. "
        "These synthetic formats do not describe real console formats.\n\n"
        "English is the source language; Russian (and, where declared, German) values are sample "
        "translation data. Explanatory metadata is English. The first record includes a PNG context "
        "screenshot and an illustrative ban on caret/tilde (`^~`), not a built-in language restriction.\n")
    if variant == "NES":
        text += (
            "\nAudio consists of generated test tones; the fourth Russian clip and German media are "
            "intentionally absent. Full media completeness therefore fails for those sides.\n\n"
            "The image tab offers standard and compact variants. Arrows only browse; choose a variant "
            "explicitly, Save and build. The builder copies the selected PNG and records its ID/hash "
            "in the manifest. Relations demonstrate shared fragments, identical text with distinct "
            "IDs, complete audio queues and a missing translation.\n")
    return text


def tone(path, frequency):
    path.parent.mkdir(parents=True, exist_ok=True)
    rate, count = 22050, 6615
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, rate, count, "NONE", "not compressed"))
        wav.writeframes(b"".join(struct.pack("<h", int(4200 * math.sin(2 * math.pi * frequency * i / rate)
            * min(1, i / 300, (count - i) / 300))) for i in range(count)))


def sign(path, title):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(720, 400, QImage.Format.Format_RGB32)
    image.fill(QColor("#17233a"))
    painter = QPainter(image)
    painter.setPen(QColor("#88c5cf"))
    painter.setBrush(QColor("#223d53"))
    painter.drawRoundedRect(30, 30, 660, 340, 15, 15)
    painter.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
    painter.setPen(QColor("#e5faff"))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, title)
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(55, 340, "TRANSLATION STUDIO / SYNTHETIC ASSET")
    painter.end()
    assert image.save(str(path), "PNG")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=str(ROOT / "Examples"))
    directory = Path(parser.parse_args().directory).resolve()
    app = QGuiApplication.instance() or QGuiApplication([])
    template = ROOT / "Docs/Examples"
    for variant in ("NES", "Sega"):
        root = directory / ("Synthetic " + variant)
        if root.exists():
            raise SystemExit("Refusing to overwrite " + str(root))
        config = read_json(template / "project.example.json")
        text = read_json(template / "text.example.json")
        config["projectId"] = "synthetic-" + variant.lower()
        config["name"] = "Synthetic " + variant
        config["extensions"] = {"demoFormat": variant.lower()}
        config["actions"][0]["arguments"] = ["--language", "ru"]
        config["actions"][0]["executable"] = "Tools/DemoBuilder.exe"
        if variant == "Sega":
            config.pop("relationsPath")
            config["tabs"] = config["tabs"][:1]
            config["targetLanguages"] = ["ru"]
            config["tabs"][0]["defaultsByLanguage"].pop("de")
            text["languages"] = ["en", "ru"]
            text["entries"] = text["entries"][:2]
            for index, entry in enumerate(text["entries"]):
                entry["texts"].pop("de")
                for key in ("notes", "constraintsByLanguage"):
                    entry.get(key, {}).pop("de", None)
                entry["extensions"] = {"recordIndex": index, "encoding": "utf-16le"}
        for entry in text["entries"]:
            if entry["texts"]["ru"] is None:
                entry["texts"]["ru"] = "Пример"
        text["sourceRevision"] = source_revision(text)
        atomic_write(root / "Translation/project.json", config)
        atomic_write(root / "Translation/Text/main.json", text)
        sign(root / "Translation/Context/main-menu.png", "START GAME\nOPTIONS\nEXIT")
        if variant == "NES":
            for kind in ("audio", "images", "relations"):
                atomic_write(root / ("Translation/Catalogs/" + kind + ".json"),
                             read_json(template / (kind + ".example.json")))
            for index, entry in enumerate(read_json(root / "Translation/Catalogs/audio.json")["entries"]):
                for lang, side in entry["assets"].items():
                    if side:
                        tone(root / side["previewPath"], 330 + 100 * index + (70 if lang == "ru" else 0))
            for lang, side in read_json(root / "Translation/Catalogs/images.json")["entries"][0]["assets"].items():
                from translation_studio.core import asset_candidates
                for candidate in asset_candidates(side):
                    title = "SECTOR 04\nACCESS OPEN" if lang == "en" else "СЕКТОР 04\nВХОД ОТКРЫТ"
                    if candidate.get("id") == "compact":
                        title = "СЕКТОР 04\nПРОХОД"
                    sign(root / candidate["previewPath"], title)
        (root / "Scripts").mkdir()
        shutil.copy2(ROOT / "Scripts/demo_builder.py", root / "Scripts/build.py")
        (root / "README.md").write_text(example_readme(variant), encoding="utf-8")
    print(directory)


if __name__ == "__main__":
    main()
