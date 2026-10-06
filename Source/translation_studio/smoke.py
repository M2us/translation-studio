"""Explicit packaged-install verification; run only on a disposable example copy."""
from pathlib import Path
import time
import traceback
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QToolButton
from .core import atomic_write
from .processes import trust_key
from .gui import MainWindow, STYLE


def main(root, report_path):
    print("Creating QApplication", flush=True)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    print("Creating MainWindow", flush=True)
    w = MainWindow()
    w.ui_choice.setCurrentIndex(w.ui_choice.findData("ru"))
    w.theme_choice.setCurrentIndex(w.theme_choice.findData("light"))
    errors = []
    w.error = lambda error: errors.append(str(error))
    w.dialog = lambda *args: errors.append(str(args))
    w.show()
    print("Opening project", flush=True)
    w.open_project(root)
    started = time.monotonic()
    state = {"step": 0}

    def finish(ok):
        atomic_write(report_path, {"ok": ok, "errors": errors, "elapsedSeconds": time.monotonic() - started,
                                   "actionStatus": w.action_status.text(), "logText": w.log.toPlainText()})
        if w.running:
            w.cancel_action()
        if w.project:
            w.project.close()
        timer.stop()
        app.exit(0 if ok else 1)

    def tick():
        try:
            if errors or time.monotonic() - started > 60:
                errors.append("timeout" if not errors else "verification failed")
                return finish(False)
            if state["step"] == 0 and w.project and not w.loader:
                close = w.recents.itemWidget(w.recents.item(0)).findChild(QToolButton, "RecentClose")
                # QListWidget lays out child widgets after the loader completes.
                # Wait for a visible row; the overall timeout still catches a missing button.
                if not close.isVisible():
                    return
                print("Project loaded; checking and editing", flush=True)
                assert not w.project.tab_errors
                page = next(page for page in w.pages.values() if page.tab["type"] == "text")
                assert page.source_editor.isReadOnly()
                assert not page.model.flags(page.model.index(0, 2)) & Qt.ItemFlag.ItemIsEditable
                assert page.screenshots.items.count() > 0
                if "art" in w.pages:
                    art = w.pages["art"]
                    original = w.project.asset_side("art", art.current_id, "ru")["id"]
                    art.browse_variant(1)
                    assert not w.project.dirty
                    assert w.project.asset_side("art", art.current_id, "ru")["id"] == original
                    art.use_variant()
                    assert w.project.asset_side("art", art.current_id, "ru")["id"] == "compact"
                page.target_editor.setPlainText("Пуск")
                current = w.project
                w.open_project(root)
                assert w.project is current and w.loader is None and page.target_editor.toPlainText() == "Пуск"
                assert close.isVisible() and close.isEnabled() and close.toolTip() == w.msg("close_remove")
                assert w.save()
                assert w.project.snapshot_path("previous.json").is_file()
                assert not w.project.snapshot_path("draft.json").exists()
                print("Saved; screenshot", flush=True)
                w.grab().save(str(report_path.with_suffix(".ru.png")))
                print("Switching locale", flush=True)
                w.ui_choice.setCurrentIndex(w.ui_choice.findData("en"))
                w.theme_choice.setCurrentIndex(w.theme_choice.findData("dark"))
                state["step"] = 1
            elif state["step"] == 1:
                print("English UI; starting action", flush=True)
                assert "Save" in w.save_button.text()
                w.grab().save(str(report_path.with_suffix(".en.png")))
                w.profile["trustedActions"] = [trust_key(w.project)]
                w.run_action(w.project.config["actions"][0])
                assert w.running
                state["step"] = 2
            elif state["step"] == 2 and not w.running:
                assert "successfully" in w.action_status.text(), w.action_status.text()
                w.grab().save(str(report_path.with_suffix(".log.png")))
                return finish(True)
        except Exception as error:
            traceback.print_exc()
            errors.append(repr(error))
            finish(False)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(50)
    return app.exec()
