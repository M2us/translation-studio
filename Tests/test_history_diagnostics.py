import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from translation_studio.core import Project, StudioError, atomic_write, read_json
from translation_studio.diagnostics import TailFile

ROOT = Path(__file__).resolve().parents[1]


def test_fixed_history_and_reopen(game):
    p = Project(game, editable=True)
    eid = p.documents["text"]["entries"][0]["id"]
    original = p.entries["text"][eid]["texts"]["ru"]
    p.set_text("text", eid, "ru", "Пуск")
    draft = p.recovery()
    stamp = draft.stat().st_mtime_ns
    assert p.recovery().stat().st_mtime_ns == stamp
    p.close()
    p = Project(game, editable=True)
    try:
        p.restore(draft)
        assert p.entries["text"][eid]["texts"]["ru"] == "Пуск"
        p.save()
        previous = p.snapshot_path("previous.json")
        assert not draft.exists()
        assert read_json(previous)["catalogs"]["Translation/Text/main.json"]["entries"][0]["texts"]["ru"] == original
        unchanged = previous.read_bytes()
        p.save()
        assert previous.read_bytes() == unchanged
        for value in ("Старт", "Начать", "Вперед"):
            p.set_text("text", eid, "ru", value)
            p.recovery()
            assert {x.name for x in draft.parent.glob("*.json")} == {"draft.json", "previous.json"}
            p.save()
        p.restore(previous)
        assert p.entries["text"][eid]["texts"]["ru"] == "Начать"
        assert p.paths["text"].read_bytes() != previous.read_bytes()
        assert not list(draft.parent.glob("*.tmp"))
    finally:
        p.close()


def test_snapshot_includes_unchanged_text_tabs(game):
    config = read_json(game / "Translation/project.json")
    extra = copy.deepcopy(config["tabs"][0])
    extra.update(id="extra", datasetId="extra", catalogPath="Translation/Text/extra.json")
    doc = read_json(game / "Translation/Text/main.json")
    doc["datasetId"] = "extra"
    config["tabs"].append(extra)
    atomic_write(game / "Translation/project.json", config)
    atomic_write(game / extra["catalogPath"], doc)
    p = Project(game, editable=True)
    try:
        eid = doc["entries"][0]["id"]
        p.set_text("text", eid, "ru", "Пуск")
        p.save()
        p.set_text("extra", eid, "ru", "Начать")
        p.save()
        p.restore(p.snapshot_path("previous.json"))
        assert p.entries["text"][eid]["texts"]["ru"] == "Пуск"
        assert p.entries["extra"][eid]["texts"]["ru"] == doc["entries"][0]["texts"]["ru"]
    finally:
        p.close()


def test_failed_save_keeps_previous_and_draft(game, monkeypatch):
    import translation_studio.core as core
    p = Project(game, editable=True)
    try:
        eid = p.documents["text"]["entries"][0]["id"]
        p.set_text("text", eid, "ru", "Пуск")
        p.save()
        before = p.snapshot_path("previous.json").read_bytes()
        saved = p.paths["text"].read_bytes()
        p.set_text("text", eid, "ru", "Начать")
        write = core.atomic_write
        def fail(path, value, expected=None):
            if path == p.paths["text"]:
                raise PermissionError("injected catalog failure")
            return write(path, value, expected)
        monkeypatch.setattr(core, "atomic_write", fail)
        with pytest.raises(StudioError):
            p.save()
        assert p.snapshot_path("previous.json").read_bytes() == before
        assert p.paths["text"].read_bytes() == saved
        assert p.snapshot_path("draft.json").exists()
        assert not p.snapshot_path("previous.pending.tmp").exists()
    finally:
        p.close()


def test_interrupted_save_promotes_pending_snapshot(game):
    p = Project(game, editable=True)
    eid = p.documents["text"]["entries"][0]["id"]
    before = p.snapshot(p.baselines)
    atomic_write(p.snapshot_path("previous.pending.tmp"), before)
    p.set_text("text", eid, "ru", "Пуск")
    p.recovery()
    atomic_write(p.paths["text"], p.documents["text"])
    p.close()
    p = Project(game, editable=True)
    try:
        assert read_json(p.snapshot_path("previous.json"))["catalogs"] == before["catalogs"]
        assert p.snapshot_path("draft.json").exists()
        assert not p.snapshot_path("previous.pending.tmp").exists()
    finally:
        p.close()


def test_failed_history_commit_can_retry_without_losing_previous(game, monkeypatch):
    import translation_studio.core as core
    p = Project(game, editable=True)
    try:
        eid = p.documents["text"]["entries"][0]["id"]
        old = copy.deepcopy(p.documents["text"])
        p.set_text("text", eid, "ru", "Пуск")
        replace = core.os.replace
        def fail(source, target):
            if Path(target).name == "previous.json":
                raise PermissionError("history commit unavailable")
            return replace(source, target)
        monkeypatch.setattr(core.os, "replace", fail)
        with pytest.raises(OSError):
            p.save()
        assert p.dirty
        assert p.snapshot_path("draft.json").exists()
        monkeypatch.setattr(core.os, "replace", replace)
        p.save()
        assert not p.dirty and not p.snapshot_path("draft.json").exists()
        assert read_json(p.snapshot_path("previous.json"))["catalogs"]["Translation/Text/main.json"] == old
    finally:
        p.close()


def test_recovery_prompt_cancel_does_not_overwrite_draft(app, game, tmp_path, monkeypatch):
    from translation_studio.gui import MainWindow
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(tmp_path / "profile.json"))
    p = Project(game, editable=True)
    eid = p.documents["text"]["entries"][0]["id"]
    p.set_text("text", eid, "ru", "Пуск")
    draft = p.recovery()
    before = draft.read_bytes()
    p.close()
    w = MainWindow()
    w.dialog = lambda *_: "cancel"
    w.on_loaded(Project(game, editable=True), None, .1)
    assert w.project is None
    assert draft.read_bytes() == before
    w.close()


def test_explicit_discard_removes_only_draft(app, game, tmp_path, monkeypatch):
    from translation_studio.gui import MainWindow
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(tmp_path / "profile.json"))
    w = MainWindow()
    w.on_loaded(Project(game, editable=True), None, .1)
    page = w.pages["text"]
    page.target_editor.setPlainText("Пуск")
    assert w.save()
    previous = w.project.snapshot_path("previous.json")
    before = previous.read_bytes()
    page.target_editor.setPlainText("Начать")
    draft = w.auto_recovery()
    w.dialog = lambda *_: "discard"
    assert w.can_leave()
    assert not draft.exists() and previous.read_bytes() == before
    w.close()


def test_tail_file_bounded_and_utf8(tmp_path):
    path = tmp_path / "current.log"
    with TailFile(path, 4096) as log:
        for i in range(300):
            log.write(f"{i} Проверка строки с кириллицей\n")
            assert path.stat().st_size <= 4096
        assert "299 Проверка" in path.read_text(encoding="utf-8")


def test_exceptions_and_two_session_logs_without_secrets(tmp_path):
    code = """
from translation_studio.diagnostics import start
import sys
s = start(sys.argv[1])
s.event('save.begin')
raise ValueError('PRIVATE_TRANSLATION_SECRET')
"""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "Source")}
    for _ in range(3):
        run = subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=env, capture_output=True, timeout=20)
        assert run.returncode != 0
    assert {p.name for p in tmp_path.glob("*.log")} == {"current.log", "previous.log"}
    for path in tmp_path.glob("*.log"):
        text = path.read_text(encoding="utf-8")
        assert "save.begin" in text and "ValueError" in text and '"frames"' in text
        assert "PRIVATE_TRANSLATION_SECRET" not in text


def test_native_fault_diagnostics(tmp_path):
    code = """
import ctypes, faulthandler, sys
ctypes.windll.kernel32.SetErrorMode(0x0002 | 0x8000)
from translation_studio.diagnostics import start
s = start(sys.argv[1])
s.event('native.before')
faulthandler._sigsegv()
"""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "Source")}
    run = subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=env, capture_output=True, timeout=20)
    assert run.returncode != 0
    text = (tmp_path / "current.log").read_text(encoding="utf-8")
    assert "native.before" in text
    assert "Windows fatal exception" in text or "Fatal Python error" in text


def test_two_bounded_action_runs(game, monkeypatch):
    from test_processes import action, wait
    import translation_studio.processes as processes
    monkeypatch.setattr(processes, "ACTION_LOG_LIMIT", 4096)
    for i in range(4):
        runner = action(Project(game), f"import sys; sys.stdout.write('X'*50000+'\\nRUN{i}\\n')")
        runner.start()
        result, events = wait(runner)
        assert result["code"] == 0
        assert runner.log_path.stat().st_size <= 4096
        assert runner.raw_log_path.stat().st_size <= 4096
    directory = runner.log_path.parent
    assert {p.name for p in directory.glob("*.log")} == {"current.log", "previous.log"}
    assert {p.name for p in directory.glob("*.bin")} == {"current.output.bin", "previous.output.bin"}
    assert "RUN3" in (directory / "current.log").read_text()
    assert "RUN2" in (directory / "previous.log").read_text()


def test_theme_language_persist_and_fields_private(app, game, tmp_path, monkeypatch):
    from translation_studio.gui import MainWindow
    from translation_studio import diagnostics
    monkeypatch.setenv("TRANSLATION_STUDIO_PROFILE", str(tmp_path / "profile.json"))
    session = diagnostics.start(tmp_path / "Logs")
    w = MainWindow()
    try:
        w.on_loaded(Project(game, editable=True), None, .01)
        w.show()
        page = w.pages["text"]
        page.target_editor.setPlainText("PRIVATE_FIELD_TEXT")
        page.note_editor.setText("PRIVATE_NOTE_TEXT")
        page.edit_note("PRIVATE_NOTE_TEXT")
        w.finish_edit()
        w.theme_choice.setCurrentIndex(w.theme_choice.findData("dark"))
        w.ui_choice.setCurrentIndex(w.ui_choice.findData("en"))
        assert w.project.dirty
        profile = read_json(tmp_path / "profile.json")
        assert profile["theme"] == "dark" and profile["uiLanguage"] == "en"
        for mode, lang in (("light", "ru"), ("dark", "en")):
            w.theme_choice.setCurrentIndex(w.theme_choice.findData(mode))
            w.ui_choice.setCurrentIndex(w.ui_choice.findData(lang))
            app.processEvents()
            w.grab().save(str(ROOT / f"Work/QA/design-{mode}.png"))
        w.project.dirty.clear()
        w.close()
        second = MainWindow()
        assert second.theme == "dark" and second.language == "en"
        second.close()
        text = (tmp_path / "Logs/current.log").read_text(encoding="utf-8")
        assert "PRIVATE_FIELD_TEXT" not in text and "PRIVATE_NOTE_TEXT" not in text
        assert text.count('"editing.finished"') == 1
    finally:
        if w.project:
            w.project.dirty.clear()
        w.close()
        session.close()
