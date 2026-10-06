"""Build a portable Windows directory in Work/Package. Publish only after verification."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "Work/Packaging"
STAGE = ROOT / "Work/Package"
sys.path.insert(0, str(ROOT / "Source"))
from translation_studio.schemas import export
from translation_studio import __version__


def run(entry, name, gui=False):
    # Windows version resources use four numeric components; public versions do not.
    parts = tuple(int(part) for part in __version__.split("."))
    version = parts + (0,) * (4 - len(parts))
    resource = WORK / "version-info.txt"
    resource.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={version!r}, prodvers={version!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', {name!r}),
    StringStruct('FileVersion', {__version__!r}),
    StringStruct('ProductName', 'Translation Studio'),
    StringStruct('ProductVersion', {__version__!r}),
    StringStruct('OriginalFilename', {str(name + '.exe')!r})
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
''', encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", name, "--paths", str(ROOT / "Source"), "--distpath", str(STAGE),
        "--workpath", str(WORK / "Build"), "--specpath", str(WORK),
        "--onedir" if gui else "--onefile", "--windowed" if gui else "--console",
        "--exclude-module", "pytest", "--version-file", str(resource),
        "--icon", str(ROOT / "Assets/translation-studio.ico"), str(ROOT / entry)]
    subprocess.run(command, cwd=ROOT, check=True)


def assemble():
    package = STAGE / "TranslationStudio"
    # This Qt wheel imports Windows' unversioned ICU API. A bundled Python runtime
    # may put a different, version-suffixed icuuc.dll on PATH; PyInstaller then
    # collects it and shadows the system DLL, breaking QtCore at import time.
    import pefile
    icu = package / "_internal/icuuc.dll"
    if icu.exists():
        pe = pefile.PE(str(icu))
        exports = {s.name for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
        pe.close()
        if b"ucnv_open" not in exports:
            icu.unlink()
            for data_dll in (package / "_internal").glob("icudt*.dll"):
                data_dll.unlink()
    for name in ("TranslationStudio.Cli.exe",):
        shutil.copy2(STAGE / name, package / name)
    export(ROOT / "Docs/Schemas")
    subprocess.run([sys.executable, str(ROOT / "Scripts/render_guide.py")], check=True)
    # Refresh the public documentation tree; removed private documents must not
    # survive an assemble-only update from an older staging directory.
    docs = package / "Docs"
    if docs.exists():
        if not docs.resolve().is_relative_to(STAGE.resolve()):
            raise RuntimeError("Unsafe documentation staging directory")
        shutil.rmtree(docs)
    shutil.copytree(ROOT / "Docs", docs)
    shutil.copytree(ROOT / "Assets", package / "Assets", dirs_exist_ok=True)
    for name in ("README.md", "README.ru.md", "CHANGELOG.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "LICENSE"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copy2(ROOT / "Scripts/PortableREADME.md", package / "README.md")
    shutil.copytree(ROOT / "Examples", package / "Examples", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "Work", "Builds"))
    for demo in (package / "Examples").iterdir():
        if demo.is_dir():
            (demo / "Tools").mkdir(exist_ok=True)
            shutil.copy2(STAGE / "DemoBuilder.exe", demo / "Tools/DemoBuilder.exe")
    sdk = package / "SDK/translation_studio"
    sdk.mkdir(parents=True, exist_ok=True)
    for name in ("__init__.py", "core.py", "schemas.py", "i18n.py", "cli.py"):
        shutil.copy2(ROOT / "Source/translation_studio" / name, sdk / name)
    (sdk.parent / "requirements.txt").write_text("jsonschema==4.26.0\n", encoding="utf-8")
    licenses = package / "ThirdParty"
    if licenses.exists():
        if not licenses.resolve().is_relative_to(STAGE.resolve()):
            raise RuntimeError("Unsafe license staging directory")
        shutil.rmtree(licenses)
    licenses.mkdir(exist_ok=True)
    installed = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        installed[name] = dist.version
        for file in dist.files or []:
            if Path(file).suffix.lower() not in (".py", ".pyc", ".pyo") and any(
                    word in str(file).lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = licenses / name / str(file).replace("../", "")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    (licenses / "dependencies.json").write_text(json.dumps(installed, indent=2) + "\n", encoding="utf-8")
    return package


def publish(package):
    destination = ROOT / "Builds/Windows/Translation Studio"
    # Only this reproducible output is replaced; game files and Work research are untouched.
    resolved = destination.resolve()
    if not resolved.is_relative_to((ROOT / "Builds").resolve()):
        raise RuntimeError("Unsafe output directory")
    # Preserve portable preferences/logs during a local rebuild. They are excluded from ZIP.
    personal = {}
    if (destination / "Data").is_dir():
        personal = {p.relative_to(destination): p.read_bytes() for p in (destination / "Data").rglob("*") if p.is_file()}
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(package, destination)
    sums = []
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            sums.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(destination).as_posix())
    (destination / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    archive = destination.parent / "Translation-Studio-Windows-Portable.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(destination.rglob("*")):
            if path.is_file() and "Data" not in path.relative_to(destination).parts:
                bundle.write(path, Path("Translation Studio") / path.relative_to(destination))
    for relative, data in personal.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (destination.parent / "Portable-SHA256.txt").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n", encoding="utf-8")
    print(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assemble-only", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--gui-only", action="store_true")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "Scripts/create_icon.py")], check=True)
    if not args.assemble_only:
        run("Source/app.py", "TranslationStudio", True)
        if not args.gui_only:
            run("Source/studio_cli.py", "TranslationStudio.Cli")
            run("Scripts/demo_builder.py", "DemoBuilder")
    package = assemble()
    if args.publish:
        publish(package)
    print("Staged:", package)


if __name__ == "__main__":
    main()
