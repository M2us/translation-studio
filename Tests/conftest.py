import os
from pathlib import Path
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Source"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["TRANSLATION_STUDIO_PROFILE"] = str(ROOT / "Work/QA/test-profile.json")


@pytest.fixture
def game(tmp_path):
    target = tmp_path / "Игра с пробелами"
    shutil.copytree(ROOT / "Examples/Synthetic NES", target,
                    ignore=shutil.ignore_patterns("Work", "Builds", "__pycache__"))
    return target


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from translation_studio.gui import STYLE
    app = QApplication.instance() or QApplication([])
    # Qt's offscreen platform does not enumerate the Windows font collection.
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeuib.ttf")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    return app
