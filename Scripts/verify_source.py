"""Audit the explicit public source boundary without initializing a Git repository."""
import ast
import io
import json
import os
from pathlib import Path
import re
import tokenize

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (".gitignore", ".gitattributes", ".editorconfig", "AGENTS.md", "CLAUDE.md",
              "README.md", "README.ru.md", "CONTRIBUTING.md", "CHANGELOG.md")
PUBLIC_DIRS = {
    "Source": {".py", ".txt"}, "Scripts": {".py", ".md"}, "Tests": {".py"},
    "Assets": {".svg", ".png", ".ico"}, "Docs": {".md", ".json", ".png"},
    "Examples": {".md", ".py", ".json", ".png", ".wav"},
}
PRIVATE_DIRS = {"Work", "Builds", "Data", "Internal", "__pycache__", ".pytest_cache",
                ".git", ".venv", "venv"}
CYRILLIC = re.compile(r"[\u0400-\u04ff]")


def public_files():
    files = [ROOT / name for name in ROOT_FILES]
    for name in ("LICENSE", "LICENSE.md", "NOTICE"):
        if (ROOT / name).is_file():
            files.append(ROOT / name)
    for directory, suffixes in PUBLIC_DIRS.items():
        for parent, directories, names in os.walk(ROOT / directory):
            directories[:] = [d for d in directories if d not in PRIVATE_DIRS]
            for name in names:
                path = Path(parent) / name
                if path.suffix.lower() in suffixes:
                    if not path.resolve().is_relative_to(ROOT.resolve()):
                        raise AssertionError(f"Public file escapes repository: {path}")
                    files.append(path)
    for path in files:
        assert path.is_file(), f"Missing public source file: {path}"
    return sorted(set(files))


def check_metadata(value, location):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"label", "context", "comment", "group", "caption"} and isinstance(child, str):
                assert not CYRILLIC.search(child), f"Non-English example explanation: {location}/{key}"
            check_metadata(child, f"{location}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_metadata(child, f"{location}/{index}")


def audit():
    files = public_files()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for rule in ("/Internal/", "/Work/", "/Builds/", "/Data/", "/Docs/UserGuide*.html",
                 "Examples/**/Work/", "Examples/**/Builds/", "__pycache__/"):
        assert rule in ignore, f"Missing ignore rule: {rule}"
    for path in files:
        relative = path.relative_to(ROOT)
        assert not set(relative.parts) & PRIVATE_DIRS, relative
        if path.suffix == ".py":
            source = path.read_text(encoding="utf-8")
            for token in tokenize.generate_tokens(io.StringIO(source).readline):
                if token.type == tokenize.COMMENT:
                    assert not CYRILLIC.search(token.string), f"Translate comment: {relative}:{token.start[0]}"
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    assert not CYRILLIC.search(ast.get_docstring(node) or ""), f"Translate docstring: {relative}"
        if path.suffix == ".json" and (relative.parts[0] == "Examples" or relative.parts[:2] == ("Docs", "Examples")):
            check_metadata(json.loads(path.read_text(encoding="utf-8")), relative.as_posix())
        if path.suffix == ".md":
            content = path.read_text(encoding="utf-8")
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
                assert not any(part in link.split("/") for part in ("Internal", "Work", "Data")), (relative, link)
    report = ROOT / "Work/QA/public-source.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"files": [p.relative_to(ROOT).as_posix() for p in files]}, indent=2) + "\n", encoding="utf-8")
    print(f"Public source audit: {len(files)} files; comments/docstrings and example metadata OK")
    return files


if __name__ == "__main__":
    audit()
