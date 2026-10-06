# Synthetic NES

A standalone teaching project. It contains no ROM and is not a translation of a real game.

Copy this folder before experimenting. Open it in Translation Studio, edit a target field in the detail panel, save, and click **Rebuild patch**. Outputs are `Builds/Patch/translation.bin` and `manifest.json`. The button needs `Tools/DemoBuilder.exe` included with the portable distribution.

From source, install Python 3.12 and jsonschema, then run `python Scripts/build.py --sdk <path-to-Source-or-SDK> --language ru` from this folder. NES writes length-prefixed UTF-8; Sega writes UTF-16LE with an offset table. These synthetic formats do not describe real console formats.

English is the source language; Russian (and, where declared, German) values are sample translation data. Explanatory metadata is English. The first record includes a PNG context screenshot and an illustrative ban on caret/tilde (`^~`), not a built-in language restriction.

Audio consists of generated test tones; the fourth Russian clip and German media are intentionally absent. Full media completeness therefore fails for those sides.

The image tab offers standard and compact variants. Arrows only browse; choose a variant explicitly, Save and build. The builder copies the selected PNG and records its ID/hash in the manifest. Relations demonstrate shared fragments, identical text with distinct IDs, complete audio queues and a missing translation.
