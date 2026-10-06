"""Capture our own Qt window using synthetic data, without editing author examples."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Source"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
session = Path(tempfile.mkdtemp(prefix="design-", dir=ROOT / "Work/QA"))
os.environ["TRANSLATION_STUDIO_PROFILE"] = str(session / "profile.json")
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QFontDatabase
from translation_studio.gui import MainWindow
from translation_studio.core import Project

app = QApplication([])
app.setStyle("Fusion")
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeuib.ttf")
game = session / "Synthetic NES"
shutil.copytree(ROOT / "Examples/Synthetic NES", game, ignore=shutil.ignore_patterns("Work", "Builds", "__pycache__"))
w = MainWindow()
w.on_loaded(Project(game, editable=True), None, .1)
w.resize(1440, 960)
w.show()
# Public screenshots show a neutral display path; project data still lives in
# the isolated disposable copy above. This changes only the displayed label.
def neutral_path():
    for label in w.findChildren(QLabel):
        if label.text() == str(game):
            label.setText("C:/Games/Synthetic NES")

images = ROOT / "Docs/Images"
images.mkdir(exist_ok=True)
for mode in ("light", "dark"):
    w.theme_choice.setCurrentIndex(w.theme_choice.findData(mode))
    w.ui_choice.setCurrentIndex(w.ui_choice.findData("en"))
    neutral_path()
    app.processEvents()
    w.grab().save(str(images / (mode + ".png")))
w.pages["text"].select_id("728dcc4a-0bce-45b4-9e6a-3371d19b5d8c")
app.processEvents()
w.grab().save(str(ROOT / "Work/QA/design-relations.png"))
w.resize(1060, 750)
app.processEvents()
w.grab().save(str(ROOT / "Work/QA/design-small.png"))
assert w.width() == 1060 and w.height() == 750
for key in ("voice", "art"):
    w.tabs.setCurrentWidget(w.pages[key])
    app.processEvents()
    w.grab().save(str(ROOT / ("Work/QA/design-" + key + ".png")))
w.resize(1440, 960)
w.tabs.setCurrentWidget(w.pages["art"])
w.pages["art"].browse_variant(1)
app.processEvents()
w.grab().save(str(images / "variants.png"))
assert not w.project.dirty
w.tabs.setCurrentWidget(w.pages["text"])
page = w.pages["text"]
page.select_id(page.model.entries[0]["id"])
page.target_editor.setPlainText("^" * 21)
page.rules_toggle.setChecked(True)
app.processEvents()
w.grab().save(str(ROOT / "Work/QA/design-rules.png"))
page.target_editor.setPlainText("Начать игру")
page.rules_toggle.setChecked(False)
page.splitter.setSizes([140, 630])
page.splitter.widget(1).ensureWidgetVisible(page.screenshots)
app.processEvents()
w.grab().save(str(images / "context.png"))
w.dialog = lambda *args: "discard"
assert w.close_project()
w.ui_choice.setCurrentIndex(w.ui_choice.findData("en"))
for mode in ("light", "dark"):
    w.theme_choice.setCurrentIndex(w.theme_choice.findData(mode))
    app.processEvents()
    w.grab().save(str(ROOT / ("Work/QA/design-empty-" + mode + ".png")))
w.close()
print("Screenshots captured in Docs/Images and Work/QA")
