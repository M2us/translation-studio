"""Check local documentation links, published schemas and the copyable minimal project."""
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Source"))
from translation_studio.core import Project, atomic_write
from translation_studio.schemas import SCHEMAS, published
from verify_source import public_files


def main():
    broken = []
    paths = [path for path in public_files() if path.suffix == ".md"]
    for path in paths:
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = unquote(link.split("#")[0])
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            base = ROOT if path.name == "PortableREADME.md" else path.parent
            resolved = (base / target).resolve()
            if not resolved.is_relative_to(ROOT.resolve()) or not resolved.exists():
                broken.append(str(path.relative_to(ROOT)) + ": " + target)
    assert not broken, broken
    for name in SCHEMAS:
        assert json.loads((ROOT / "Docs/Schemas" / (name + ".schema.json")).read_text(encoding="utf-8")) == published(name)
    guide = (ROOT / "Docs/IntegrationGuide.md").read_text(encoding="utf-8")
    examples = re.findall(r"```json\n(.*?)\n```", guide, flags=re.S)
    (ROOT / "Work/QA").mkdir(parents=True, exist_ok=True)
    game = Path(tempfile.mkdtemp(prefix="minimal-guide-", dir=ROOT / "Work/QA"))
    atomic_write(game / "Translation/project.json", json.loads(examples[0]))
    atomic_write(game / "Translation/Text/main.json", json.loads(examples[1]))
    project = Project(game)
    assert not project.issues(complete=True)
    print("Documentation links, 5 schemas and minimal integration example: OK")


if __name__ == "__main__":
    main()
