"""One portable personal profile; no project text is stored here."""
import os
from pathlib import Path
import sys


def app_root():
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]


def profile_path():
    return Path(os.environ.get("TRANSLATION_STUDIO_PROFILE", str(app_root() / "Data/profile.json")))


def logs_path():
    return profile_path().parent / "Logs"
