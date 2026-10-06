"""Verify a staged binary without modifying author-owned examples."""
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Source"))
from translation_studio import __version__
PACKAGE = ROOT / "Work/Package/TranslationStudio"
QA = ROOT / "Work/QA/Packaged"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--portable-profile", action="store_true")
    args = parser.parse_args()
    package = args.package.resolve()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    QA.mkdir(parents=True, exist_ok=True)
    # mkdtemp avoids overwriting prior diagnostic reports or user edits.
    import tempfile
    session = Path(tempfile.mkdtemp(prefix="run-", dir=QA))
    result = {"session": str(session), "examples": {}}
    version = subprocess.run([str(package / "TranslationStudio.Cli.exe"), "--version"],
                             capture_output=True, text=True, timeout=30, check=True)
    assert version.stdout.strip() == f"Translation Studio {__version__}"
    import pefile
    for filename in ("TranslationStudio.exe", "TranslationStudio.Cli.exe",
                     "Examples/Synthetic NES/Tools/DemoBuilder.exe"):
        with pefile.PE(str(package / filename)) as executable:
            strings = {}
            for group in executable.FileInfo:
                for block in group:
                    for table in getattr(block, "StringTable", []):
                        strings.update(table.entries)
            assert strings[b"ProductVersion"].decode() == __version__
            assert strings[b"FileVersion"].decode() == __version__
    for filename, language in (("UserGuide.html", "en"), ("UserGuide.ru.html", "ru")):
        assert f'<html lang="{language}">' in (package / "Docs" / filename).read_text(encoding="utf-8")
    diagnostics = []
    for locale in (None, "en", "ru"):
        command = [str(package / "TranslationStudio.Cli.exe")]
        if locale:
            command.extend(["--ui-language", locale])
        command.extend(["validate", str(session / "Missing project")])
        failed = subprocess.run(command, capture_output=True, timeout=30)
        assert failed.returncode == 1
        diagnostics.append(json.loads(failed.stdout))
    assert diagnostics[0] == diagnostics[1]
    assert diagnostics[0]["issues"][0]["message"] != diagnostics[2]["issues"][0]["message"]
    for variant in ("NES", "Sega"):
        game = session / ("Перенесённая игра " + variant)
        shutil.copytree(package / "Examples" / ("Synthetic " + variant), game)
        cli = subprocess.run([str(package / "TranslationStudio.Cli.exe"), "validate", str(game),
            "--language", "ru", "--complete"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert cli.returncode == 0, cli.stdout + cli.stderr
        media_cli = subprocess.run([str(package / "TranslationStudio.Cli.exe"), "validate", str(game),
            "--language", "ru", "--media", "--strict-relations"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert media_cli.returncode == 0, media_cli.stdout + media_cli.stderr
        report = session / (variant + ".json")
        env = {**os.environ, "TRANSLATION_STUDIO_PROFILE": str(session / (variant + "-profile.json"))}
        if args.portable_profile:
            env.pop("TRANSLATION_STUDIO_PROFILE", None)
        env.pop("QT_QPA_PLATFORM", None)
        # This is our own verification window. No external applications are controlled.
        run = subprocess.run([str(package / "TranslationStudio.exe"), "--smoke-test", str(game), str(report)],
            env=env, timeout=85, creationflags=subprocess.CREATE_NO_WINDOW)
        assert report.is_file(), "Missing report, exit=" + str(run.returncode)
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["ok"] and run.returncode == 0, data
        assert "Synthetic table built:" in data["logText"], data["logText"]
        assert "Перенесённая игра " + variant in data["logText"]
        assert "\ufffd" not in data["logText"], data["logText"]
        log_path = next((game / "Work/TranslationStudio/Logs").glob("*.log"))
        saved_log = log_path.read_text(encoding="utf-8", errors="strict")
        raw = log_path.with_suffix(".output.bin").read_bytes().decode("utf-8", errors="strict")
        assert "Synthetic table built:" in saved_log and "Synthetic table built:" in raw
        assert "Перенесённая игра " + variant in saved_log and "Перенесённая игра " + variant in raw
        assert "\ufffd" not in saved_log and "\ufffd" not in raw
        binary = (game / "Builds/Patch/translation.bin").read_bytes()
        manifest = json.loads((game / "Builds/Patch/manifest.json").read_text(encoding="utf-8"))
        if variant == "NES":
            assert manifest["images"][0]["variantId"] == "compact"
            assert (game / "Builds/Patch" / manifest["images"][0]["output"]).read_bytes() == (
                game / "Translation/Images/wall-sign-compact.png").read_bytes()
        assert "Пуск".encode("utf-8" if variant == "NES" else "utf-16le") in binary
        result["examples"][variant] = data
        profile = package / "Data/profile.json" if args.portable_profile else session / (variant + "-profile.json")
        settings = json.loads(profile.read_text(encoding="utf-8"))
        assert settings["theme"] == "dark" and settings["uiLanguage"] == "en"
        bookmarks = settings["bookmarks"][str(game.resolve()).casefold()]
        assert len(bookmarks) == 2
        assert {item["note"] for item in bookmarks} == {"Private bookmark smoke note", "Resume work"}
        recovery = game / "Work/TranslationStudio/Recovery"
        assert (recovery / "previous.json").is_file() and not (recovery / "draft.json").exists()
    logs = (package / "Data" if args.portable_profile else session) / "Logs"
    assert {path.name for path in logs.glob("*.log")} == {"current.log", "previous.log"}
    for path in logs.glob("*.log"):
        assert path.stat().st_size <= 2 * 1024 * 1024
        text = path.read_text(encoding="utf-8")
        assert '"save.complete"' in text and '"application.exit"' in text
        assert "Пуск" not in text
        assert "Private bookmark smoke note" not in text and "Resume work" not in text
    result["portableProfile"] = args.portable_profile
    result["package"] = str(package)
    (ROOT / "Work/QA/package-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
