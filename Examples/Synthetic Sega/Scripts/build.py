"""Two synthetic adapters, deliberately outside the generic editor."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys


def main():
    # Frozen Python executables may ignore PYTHONIOENCODING. Set both streams
    # explicitly so the editor's UTF-8 contract also holds after packaging.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", help="Folder containing translation_studio")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--project")
    args = parser.parse_args()
    if args.sdk:
        sys.path.insert(0, args.sdk)
    from translation_studio.core import Project, StudioError, json_bytes, safe_path
    base = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent.parent
    root = Path(args.project).resolve() if args.project else base
    project = Project(root)
    if args.language not in project.config["targetLanguages"]:
        raise StudioError("languages", path=str(root))
    errors = [i for i in project.issues(language=args.language, complete=True) if i.severity == "error"]
    if errors:
        raise SystemExit("\n".join(i.message() for i in errors))
    project.check_external()
    variant = project.config.get("extensions", {}).get("demoFormat", "nes")
    values = [entry["texts"][args.language] for entry in project.documents["text"]["entries"]]
    if variant == "nes":
        chunks = [text.encode("utf-8") for text in values]
        output = b"TSN1" + struct.pack("<I", len(chunks)) + b"".join(struct.pack("<I", len(c)) + c for c in chunks)
    else:
        chunks = [text.encode("utf-16le") + b"\x00\x00" for text in values]
        offsets, offset = [], 8 + 4 * len(chunks)
        for chunk in chunks:
            offsets.append(offset)
            offset += len(chunk)
        output = b"TSS1" + struct.pack(">I", len(chunks)) + b"".join(struct.pack(">I", i) for i in offsets) + b"".join(chunks)
    project.check_external()
    directory = root / "Builds/Patch"
    directory.mkdir(parents=True, exist_ok=True)
    images = []
    for tab_id, tab in project.tabs.items():
        if tab["type"] != "images" or tab_id not in project.documents:
            continue
        for entry in project.documents[tab_id]["entries"]:
            side = project.asset_side(tab_id, entry["id"], args.language)
            if side is None:
                continue
            relative = side.get("assetPath", side["previewPath"])
            payload = safe_path(root, relative).read_bytes()
            output_name = f"image-{len(images):03d}.png"
            (directory / output_name).write_bytes(payload)
            images.append({"entryId": entry["id"], "variantId": side.get("id"), "assetPath": relative,
                           "output": output_name, "sha256": hashlib.sha256(payload).hexdigest()})
    (directory / "translation.bin").write_bytes(output)
    (directory / "manifest.json").write_bytes(json_bytes({"projectId": project.config["projectId"],
        "language": args.language, "format": variant, "sha256": hashlib.sha256(output).hexdigest(), "images": images,
        "sourceHashes": {str(path.relative_to(root)): value for path, value in project.hashes.items()}}))
    print("Synthetic table built:", directory, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
