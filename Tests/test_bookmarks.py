"""Personal navigation survives restarts without changing builder inputs."""
import shutil
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from translation_studio.core import Project, read_json
from translation_studio.gui import MainWindow


def open_window(app, game):
    window = MainWindow()
    window.on_loaded(Project(game, editable=True), None, .1)
    window.show()
    app.processEvents()
    return window


def test_numbering_bookmark_notes_restart_and_navigation(app, game, tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(profile))
    catalogs = {path: path.read_bytes() for path in (game / "Translation").glob("*.json")}
    window = open_window(app, game)
    page = window.pages["text"]
    first, second = (entry["id"] for entry in page.model.entries[:2])
    try:
        assert window.bookmark_bar.isHidden()
        assert not page.table.verticalHeader().isHidden()
        page.select_id(second)
        page.bookmark_toggle.click()
        page.bookmark_note.setFocus()
        QTest.keyClicks(page.bookmark_note, "Continue here tomorrow")
        assert window.bookmark("text", second)["note"] == "Continue here tomorrow"
        window.set_bookmark("art", window.pages["art"].model.entries[0]["id"], True, "Review artwork")
        assert not window.bookmark_bar.isHidden()
        assert window.bookmark_choice.count() == 2
        page.search.setText("Targets:")
        assert page.proxy.rowCount() == 1
        assert page.proxy.headerData(0, Qt.Orientation.Vertical) == 2
        assert page.proxy.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.DecorationRole) is not None
        page.select_id(first)
        page.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        for row in range(page.proxy.rowCount()):
            entry = page.proxy.data(page.proxy.index(row, 0))
            assert page.proxy.headerData(row, Qt.Orientation.Vertical) == page.model.row_by_id[entry] + 1
        window.navigate_bookmark(1)
        assert page.current_id == second
        window.navigate_bookmark(1)
        assert window.tabs.currentWidget() is window.pages["art"]
        window.navigate_bookmark(1)
        assert window.tabs.currentWidget() is page
        assert page.current_id == second
        window.navigate_bookmark(-1)
        assert window.tabs.currentWidget() is window.pages["art"]
        assert not window.project.dirty
    finally:
        window.close()
    reopened = open_window(app, game)
    try:
        assert reopened.bookmark_choice.count() == 2
        page = reopened.pages["text"]
        page.search.setText("no matching record")
        reopened.open_bookmark(0)
        assert page.current_id == second and not page.search.text()
        assert page.bookmark_toggle.isChecked()
        assert page.bookmark_note.text() == "Continue here tomorrow"
        assert read_json(profile)["bookmarks"]
        assert all(path.read_bytes() == original for path, original in catalogs.items())
        reopened.set_bookmark("text", second, False)
        reopened.set_bookmark("art", reopened.pages["art"].model.entries[0]["id"], False)
        assert reopened.bookmark_bar.isHidden()
    finally:
        reopened.close()


def test_unavailable_bookmark_and_failed_save(app, game, tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(tmp_path / "profile.json"))
    window = open_window(app, game)
    try:
        page = window.pages["text"]
        entry = page.current_id
        window.set_bookmark("text", "removed-id", True, "Keep this note")
        window.set_bookmark("text", entry, True, "Available")
        window.navigate_bookmark(-1)
        assert page.current_id == entry
        window.open_bookmark(1)
        assert page.current_id == entry
        window.bookmark_choice.setCurrentIndex(1)
        window.remove_selected_bookmark()
        assert window.bookmark_choice.count() == 1
        import translation_studio.gui as gui
        def fail(*args):
            raise OSError("Profile is read-only")
        monkeypatch.setattr(gui, "atomic_write", fail)
        page.bookmark_toggle.click()
        assert page.bookmark_toggle.isChecked()
        assert window.bookmark("text", entry)["note"] == "Available"
        assert "Cannot save personal settings" in window.statusBar().currentMessage()
    finally:
        window.close()


def test_bookmarks_are_personal_per_project_and_work_readonly(app, game, tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(tmp_path / "profile.json"))
    other = tmp_path / "Other game"
    shutil.copytree(game, other)
    window = open_window(app, game)
    try:
        page = window.pages["text"]
        entry = page.current_id
        window.project.writable = False
        page.update_details()
        page.bookmark_toggle.click()
        assert window.bookmark("text", entry)
        assert not window.project.dirty
        window.project.close()
        window.project = None
        window.on_loaded(Project(other, editable=True), None, .1)
        assert window.bookmark_bar.isHidden()
        assert window.bookmark("text", entry) is None
        window.set_bookmark("text", entry, True, "Different project")
        window.project.close()
        window.project = None
        window.on_loaded(Project(game, editable=True), None, .1)
        assert window.bookmark_choice.count() == 1
        assert window.bookmark("text", entry)["note"] == ""
    finally:
        window.close()
