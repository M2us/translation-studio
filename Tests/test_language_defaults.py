"""English defaults must not remove explicit Russian diagnostic support."""
import json
from pathlib import Path
import subprocess
import sys

from translation_studio.core import Issue
from translation_studio.i18n import tr

ROOT = Path(__file__).resolve().parents[1]


def test_default_diagnostics_and_cli_are_english(tmp_path):
    assert tr("saved") == "Saved"
    assert tr("saved", "ru") == "Сохранено"
    assert Issue("saved").message() == "Saved"
    assert Issue("saved").as_dict()["message"] == "Saved"
    outputs = []
    for locale in (None, "en", "ru"):
        command = [sys.executable, str(ROOT / "Source/studio_cli.py")]
        if locale:
            command.extend(["--ui-language", locale])
        command.extend(["validate", str(tmp_path / "Missing project")])
        result = subprocess.run(command, capture_output=True)
        assert result.returncode == 1
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]
    assert outputs[0]["issues"][0]["code"] == outputs[2]["issues"][0]["code"]
    assert outputs[0]["issues"][0]["message"] != outputs[2]["issues"][0]["message"]
