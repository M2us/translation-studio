import copy
from pathlib import Path
import time
from PySide6.QtCore import Qt, QUrl
from PySide6.QtTest import QTest
from translation_studio.core import Project, atomic_write, source_revision
from translation_studio.gui import MainWindow

ROOT = Path(__file__).resolve().parents[1]


def window(app, game):
    w = MainWindow()
    def unexpected(error):
        raise AssertionError(str(error))
    w.error = unexpected
    w.dialog = lambda *args: unexpected(args)
    w.profile = {}
    w.language = "ru"
    w.on_loaded(Project(game, editable=True), None, .1)
    w.show()
    app.processEvents()
    return w


def close(w):
    w.project.dirty.clear()
    w.close()
    w.deleteLater()


def test_edit_sort_filter_relations_locales_images(app, game):
    w = window(app, game)
    try:
        page = w.pages["text"]
        shared = "728dcc4a-0bce-45b4-9e6a-3371d19b5d8c"
        page.select_id(shared)
        assert page.relation_choice.count() == 2
        assert page.source_editor.isReadOnly()
        page.target_editor.setPlainText("Наверное")
        assert "Наверное, что-то произошло" in page.relation_views[1].toPlainText()
        page.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        page.search.setText("Наверное")
        assert page.proxy.rowCount() == 1
        assert page.proxy.data(page.proxy.index(0, 0)) == shared
        w.target_choice.setCurrentText("de")
        assert w.project.entries["text"][shared]["texts"]["ru"] == "Наверное"
        w.target_choice.setCurrentText("ru")
        w.ui_choice.setCurrentIndex(w.ui_choice.findData("en"))
        assert w.tabs.tabText(0) == "Text"
        assert w.pages["text"].model.headerData(2, Qt.Orientation.Horizontal) == "Translation"
        w.ui_choice.setCurrentIndex(w.ui_choice.findData("ru"))
        w.pages["text"].select_id(shared)
        app.processEvents()
        assert w.grab().save(str(ROOT / "Work/QA/text-ru.png"))
        w.tabs.setCurrentWidget(w.pages["art"])
        app.processEvents()
        images = w.pages["art"].image_compare
        assert all(len(view.scene().items()) == 1 for view in images.views)
        assert w.grab().save(str(ROOT / "Work/QA/images-ru.png"))
        w.tabs.setCurrentWidget(w.pages["voice"])
        w.pages["voice"].select_id("voice.intro.004")
        assert not w.pages["voice"].play_buttons[1].isEnabled()
        assert w.save()
    finally:
        close(w)


def test_queue_plays_all_and_cancels(app, game):
    w = window(app, game)
    try:
        group = next(g["id"] for g in w.project.groups.values() if g["type"] == "audioSequence")
        played, errors = [], []
        w.audio.changed.connect(lambda entry, index, count: played.append(entry) if count else None)
        w.audio.failed.disconnect()
        w.audio.failed.connect(errors.append)
        sequence = w.project.audio_queue("voice", "voice.intro.001", "ru", group)
        w.audio.play(sequence)
        deadline = time.monotonic() + 8
        while w.audio.active and time.monotonic() < deadline:
            QTest.qWait(30)
        assert not errors, errors
        assert played == [part["id"] for part in sequence]
        assert not w.audio.active
        played.clear()
        w.audio.play(sequence)
        QTest.qWait(60)
        w.audio.stop()
        QTest.qWait(700)
        assert played == [sequence[0]["id"]]
    finally:
        close(w)


def test_large_catalog(app, game):
    path = game / "Translation/Text/main.json"
    from translation_studio.core import read_json
    doc = read_json(path)
    template = doc["entries"][0]
    doc["entries"] = []
    for i in range(2119):
        entry = copy.deepcopy(template)
        entry["id"] = "synthetic-" + str(i)
        entry["texts"]["en"] = "Original " + str(i)
        doc["entries"].append(entry)
    doc["sourceRevision"] = source_revision(doc)
    atomic_write(path, doc)
    # Omit now-invalid optional relations for this performance fixture.
    config = read_json(game / "Translation/project.json")
    config.pop("relationsPath")
    atomic_write(game / "Translation/project.json", config)
    start = time.perf_counter()
    w = window(app, game)
    loaded = time.perf_counter() - start
    try:
        start = time.perf_counter()
        w.pages["text"].search.setText("Original 2118")
        app.processEvents()
        filtered = time.perf_counter() - start
        assert w.pages["text"].proxy.rowCount() == 1
        w.pages["text"].select_id("synthetic-2118")
        w.pages["text"].target_editor.setPlainText("Пуск")
        assert w.save()
        atomic_write(ROOT / "Work/QA/performance.json", {"entries": 2119, "loadSeconds": loaded, "filterSeconds": filtered})
        assert loaded < 15 and filtered < 3
    finally:
        close(w)


def test_log_warning_keeps_polling_and_is_localized(app, game):
    import queue
    from types import SimpleNamespace
    from translation_studio.core import Issue
    w = window(app, game)
    try:
        events = queue.Queue()
        events.put(("warning", Issue("log_encoding", {"encoding": "utf-8", "path": "raw.output.bin"})))
        events.put(("line", "Сборка завершена\r\n"))
        events.put(("done", {"code": 0, "cancelled": False, "changed": False}))
        w.runner = SimpleNamespace(events=events, log_path="test.log", action={})
        w.running = True
        w.poll_action()
        text = w.log.toPlainText()
        assert "Вывод команды не соответствует utf-8" in text
        assert "Сборка завершена" in text and "\ufffd" not in text
        assert not w.running
    finally:
        close(w)
