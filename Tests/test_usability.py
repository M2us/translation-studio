import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import Qt, QPoint, QEventLoop, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QToolButton

from translation_studio.core import Project, StudioError, atomic_write, read_json, text_issues, selected_asset
from translation_studio.gui import MainWindow
from test_gui import window, close

ROOT = Path(__file__).resolve().parents[1]


def wait_loaded(w):
    if w.loader is None:
        return
    # An event loop releases the GIL for the Python loader; repeated QTest.qWait
    # calls can starve its Python work even while processing Qt events.
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    w.loader.finished.connect(loop.quit)
    timeout.start(15000)
    loop.exec()
    timeout.stop()
    assert w.loader is None


@pytest.fixture
def illustrated(game):
    path = game / "Translation/Catalogs/images.json"
    doc = read_json(path)
    entry = doc["entries"][0]
    first = dict(selected_asset(entry["assets"]["ru"]), id="regular", label="Обычный", comment="Основной вариант")
    second = dict(entry["assets"]["en"], id="alternative", label="Альтернативный")
    entry["assets"]["ru"] = {"selectedVariantId": "regular", "variants": [first, second]}
    atomic_write(path, doc)
    path = game / "Translation/Text/main.json"
    text = read_json(path)
    text["entries"][0]["screenshots"] = [{"path": first["previewPath"], "caption": "Главный экран"}]
    text["entries"][0].setdefault("constraintsByLanguage", {}).setdefault("ru", {})["forbiddenCharacters"] = "ёЁ"
    atomic_write(path, text)
    return game, entry["id"]


def test_character_rules_inheritance_unicode_and_severity():
    # Cyrillic yo (U+0401/U+0451), emoji and a zero-width joiner exercise
    # arbitrary Unicode rules; these letters are not forbidden by the app.
    entry = {"id": "sample", "texts": {"ru": "Ёж 👩‍🚀"}}
    defaults = {"allowedCharacters": "Ёж 👩‍🚀", "forbiddenCharacters": "ёЁ", "maxCodePoints": 6}
    issues = text_issues(entry, "ru", defaults)
    assert [i.values["rule"] for i in issues] == ["forbiddenCharacters"]
    assert "U+0401" in issues[0].values["actual"]
    entry["constraintsByLanguage"] = {"ru": {"allowedCharacters": "Ёж ", "forbiddenCharacters": "",
                                               "severity": {"allowedCharacters": "warning"}}}
    issues = text_issues(entry, "ru", defaults)
    assert len(issues) == 1 and issues[0].severity == "warning"
    assert "U+200D" in issues[0].values["actual"]
    entry["constraintsByLanguage"]["ru"]["allowedCharacters"] = None
    assert not text_issues(entry, "ru", defaults)
    entry["texts"]["ru"] = None
    assert not text_issues(entry, "ru", defaults)


def test_variants_save_draft_rollback_builder(illustrated):
    game, image_id = illustrated
    p = Project(game, editable=True)
    try:
        text_id = p.documents["text"]["entries"][0]["id"]
        assert p.asset_side("art", image_id, "ru")["id"] == "regular"
        p.set_variant("art", image_id, "ru", "alternative")
        p.set_text("text", text_id, "ru", "Пуск")
        draft = p.recovery()
        snapshot = read_json(draft)
        assert "Translation/Catalogs/images.json" in snapshot["catalogs"]
        p.save()
        assert not draft.exists()
        saved = Project(game)
        assert saved.asset_side("art", image_id, "ru")["id"] == "alternative"
        result = subprocess.run([sys.executable, str(ROOT / "Scripts/demo_builder.py"), "--sdk", str(ROOT / "Source"),
                                 "--project", str(game)], capture_output=True)
        assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
        manifest = read_json(game / "Builds/Patch/manifest.json")
        assert manifest["images"][0]["variantId"] == "alternative"
        p.restore(p.snapshot_path("previous.json"))
        assert p.asset_side("art", image_id, "ru")["id"] == "regular"
        assert p.entries["text"][text_id]["texts"]["ru"] != "Пуск"
        p.restore(draft, data=snapshot)
        assert p.asset_side("art", image_id, "ru")["id"] == "alternative"
        assert p.entries["text"][text_id]["texts"]["ru"] == "Пуск"
        assert len(list(p.snapshot_path("previous.json").parent.glob("*.json"))) <= 2
    finally:
        p.close()


def test_variants_readonly_and_protection(illustrated):
    game, image_id = illustrated
    p = Project(game)
    with pytest.raises(StudioError):
        p.set_variant("art", image_id, "ru", "alternative")
    p = Project(game, editable=True)
    try:
        with pytest.raises(StudioError):
            p.set_variant("art", image_id, "en", "alternative")
        with pytest.raises(StudioError):
            p.set_variant("art", image_id, "ru", "unknown")
        p.set_variant("art", image_id, "ru", "alternative")
        recovered = p.snapshot(p.documents)
        recovered["catalogs"]["Translation/Catalogs/images.json"]["entries"][0]["assets"]["en"]["previewPath"] = "Other.png"
        with pytest.raises(StudioError):
            p.restore("unused", data=recovered)
        p.entries["art"][image_id]["assets"]["ru"]["variants"][0]["label"] = "tampered"
        with pytest.raises(StudioError):
            p.save()
        assert read_json(game / "Translation/Catalogs/images.json")["entries"][0]["assets"]["ru"]["selectedVariantId"] == "regular"
    finally:
        p.close()


def test_mixed_partial_save_retains_full_recovery(illustrated, monkeypatch):
    import translation_studio.core as core
    game, image_id = illustrated
    p = Project(game, editable=True)
    try:
        before = p.snapshot(p.baselines)["catalogs"]
        p.set_text("text", p.documents["text"]["entries"][0]["id"], "ru", "Пуск")
        p.set_variant("art", image_id, "ru", "alternative")
        write = core.atomic_write
        writes = []
        def fail_second(path, value, expected=None):
            if path in (p.paths["text"], p.paths["art"]):
                writes.append(path)
                if len(writes) == 2:
                    raise PermissionError("injected second catalog failure")
            return write(path, value, expected)
        monkeypatch.setattr(core, "atomic_write", fail_second)
        with pytest.raises(StudioError) as error:
            p.save()
        assert error.value.issue.code == "partial_save" and len(p.dirty) == 1
        assert read_json(p.snapshot_path("previous.json"))["catalogs"] == before
        draft = read_json(p.snapshot_path("draft.json"))
        assert draft["catalogs"]["Translation/Catalogs/images.json"]["entries"][0]["assets"]["ru"]["selectedVariantId"] == "alternative"
        assert draft["catalogs"]["Translation/Text/main.json"]["entries"][0]["texts"]["ru"] == "Пуск"
        monkeypatch.setattr(core, "atomic_write", write)
        p.restore(p.snapshot_path("previous.json"))
        p.save()
        assert p.snapshot(p.documents)["catalogs"] == before
    finally:
        p.close()


@pytest.mark.parametrize("kind", ["selection", "duplicate", "source", "audio", "path", "screenshot"])
def test_invalid_optional_metadata_rejected(illustrated, kind):
    game, _ = illustrated
    path = game / "Translation/Catalogs/images.json"
    doc = read_json(path)
    side = doc["entries"][0]["assets"]["ru"]
    tab = "art"
    if kind == "selection":
        side["selectedVariantId"] = "unknown"
    elif kind == "duplicate":
        side["variants"][1]["id"] = side["variants"][0]["id"]
    elif kind == "source":
        doc["entries"][0]["assets"]["en"] = copy.deepcopy(side)
    elif kind == "audio":
        path = game / "Translation/Catalogs/audio.json"
        doc = read_json(path)
        doc["entries"][0]["assets"]["ru"] = side
        tab = "voice"
    elif kind == "path":
        side["variants"][1]["previewPath"] = "../escape.png"
    else:
        path = game / "Translation/Text/main.json"
        doc = read_json(path)
        doc["entries"][0]["screenshots"][0]["path"] = "C:/escape.png"
        tab = "text"
    atomic_write(path, doc)
    assert tab in Project(game).tab_errors


def test_cli_checks_alternatives_and_screenshots(illustrated):
    game, _ = illustrated
    path = game / "Translation/Catalogs/images.json"
    doc = read_json(path)
    doc["entries"][0]["assets"]["ru"]["variants"][1]["previewPath"] = "Translation/Images/absent.png"
    atomic_write(path, doc)
    result = subprocess.run([sys.executable, str(ROOT / "Source/studio_cli.py"), "validate", str(game),
                             "--language", "ru", "--media"], capture_output=True)
    assert result.returncode == 1
    assert any(i["code"] == "missing_file" for i in json.loads(result.stdout)["issues"])


def test_readonly_table_rules_and_variant_preview(app, illustrated):
    game, image_id = illustrated
    w = window(app, game)
    try:
        page = w.pages["text"]
        assert page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        assert not page.model.flags(page.model.index(0, 2)) & Qt.ItemFlag.ItemIsEditable
        assert page.context_label.text().startswith("Контекст:")
        assert page.comment_label.text().startswith("Примечание:")
        assert page.screenshots.items.count() == 1
        assert not page.screenshots.items.item(0).icon().isNull()
        page.target_editor.setPlainText("Ё" * 21)
        assert "Лимит символов превышен" in page.limit_label.text()
        assert "U+0401" in page.limit_label.text() and "maxCodePoints" not in page.limit_label.text()
        page.target_editor.setPlainText("Пуск")
        assert w.save()
        art = w.pages["art"]
        w.tabs.setCurrentWidget(art)
        art.browse_variant(1)
        assert not w.project.dirty
        assert w.project.asset_side("art", image_id, "ru")["id"] == "regular"
        assert art.variant_use.isEnabled()
        art.use_variant()
        assert w.project.dirty == {"art"}
        assert w.save()
        art.browse_variant(-1)
        assert not w.project.dirty
        assert w.project.asset_side("art", image_id, "ru")["id"] == "alternative"
    finally:
        close(w)


def test_first_language_help_close_remove(app, game, tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(tmp_path / "fresh.json"))
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    w = MainWindow()
    w.show()
    try:
        assert w.language == "en"
        assert w.target_choice.isHidden() and w.controls_widget.isHidden()
        w.help()
        assert opened[-1].endswith("UserGuide.html")
        w.ui_choice.setCurrentIndex(w.ui_choice.findData("ru"))
        w.help()
        assert opened[-1].endswith("UserGuide.ru.html")
        assert read_json(tmp_path / "fresh.json")["uiLanguage"] == "ru"
        w.on_loaded(Project(game, editable=True), None, .1)
        page = w.pages["text"]
        page.target_editor.setPlainText("Пуск")
        w.dialog = lambda *args: "cancel"
        assert not w.remove_recent(str(game.resolve()))
        assert w.project.dirty
        other = str(tmp_path / "Other game")
        w.profile["recentProjects"].append(other)
        assert w.remove_recent(other) and w.project.dirty
        w.dialog = lambda *args: "save"
        assert w.remove_recent(str(game.resolve()))
        assert w.project is None and not w.profile["recentProjects"]
        assert w.controls_widget.isHidden() and w.target_choice.isHidden()
        assert read_json(game / "Translation/Text/main.json")["entries"][0]["texts"]["ru"] == "Пуск"
        editable = Project(game, editable=True)
        assert editable.writable
        editable.close()
    finally:
        w.close()
        w.deleteLater()


def test_recent_cross_keeps_other_project_and_honors_cancel(app, game, tmp_path):
    w = window(app, game)
    try:
        w.pages["text"].target_editor.setPlainText("Пуск")
        project = w.project
        other = tmp_path / "Другой проект"
        other.mkdir()
        w.profile["recentProjects"].append(str(other))
        w.rebuild()
        app.processEvents()
        def cross(index):
            return w.recents.itemWidget(w.recents.item(index)).findChild(QToolButton, "RecentClose")
        assert cross(1).isVisible() and cross(1).toolTip() == "Закрыть и убрать из списка"
        # Clicking the child's button must not bubble into opening that list entry.
        QTest.mouseClick(cross(1), Qt.MouseButton.LeftButton)
        assert w.project is project and w.project.dirty and w.loader is None
        assert w.recents.count() == 1 and other.is_dir()
        w.dialog = lambda *args: "cancel"
        QTest.mouseClick(cross(0), Qt.MouseButton.LeftButton)
        assert w.project is project and w.project.dirty and w.recents.count() == 1
        w.dialog = lambda *args: "save"
        QTest.mouseClick(cross(0), Qt.MouseButton.LeftButton)
        assert w.project is None and w.recents.count() == 0
        assert read_json(game / "Translation/Text/main.json")["entries"][0]["texts"]["ru"] == "Пуск"
    finally:
        if w.project:
            w.project.dirty.clear()
        w.close()
        w.deleteLater()


def test_recent_active_click_is_noop_but_reload_reads_disk(app, game):
    w = window(app, game)
    try:
        page = w.pages["text"]
        page.target_editor.setPlainText("Пуск")
        project = w.project
        row = w.recents.itemWidget(w.recents.item(0))
        QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        QTest.mouseDClick(row, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        assert w.project is project and w.loader is None
        assert w.pages["text"] is page and page.target_editor.toPlainText() == "Пуск"
        assert project.dirty
        path = game / "Translation/Text/main.json"
        doc = read_json(path)
        doc["entries"][0]["comment"] = "Обновлено вне приложения"
        atomic_write(path, doc)
        w.dialog = lambda *args: "discard"
        w.reload()
        wait_loaded(w)
        assert w.loader is None and w.project is not project
        assert w.pages["text"].comment_label.text() == "Примечание: Обновлено вне приложения"
        assert not w.project.dirty
        cross = w.recents.itemWidget(w.recents.item(0)).findChild(QToolButton, "RecentClose")
        assert cross.isEnabled()
        assert w.close_project()
        row = w.recents.itemWidget(w.recents.item(0))
        QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        wait_loaded(w)
        assert w.loader is None and w.project is not None
        assert w.project.root == game.resolve()
    finally:
        if w.project:
            w.project.dirty.clear()
        w.close()
        w.deleteLater()
