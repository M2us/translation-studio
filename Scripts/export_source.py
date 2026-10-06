"""Export only public source files; never initialize Git or publish remotely."""
import hashlib
from pathlib import Path
import zipfile

from verify_source import ROOT, audit


def main():
    files = audit()
    directory = ROOT / "Builds/Source"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "Translation-Studio-Source.zip"
    temporary = target.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                archive.write(path, Path("Translation Studio") / path.relative_to(ROOT))
        with zipfile.ZipFile(temporary) as archive:
            assert archive.testzip() is None
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (directory / "Source-SHA256.txt").write_text(digest + "  " + target.name + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
