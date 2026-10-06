import copy
from pathlib import Path
import subprocess
import sys
import pytest
from translation_studio.core import Project, StudioError, read_json, atomic_write, source_revision
from translation_studio.processes import ActionRunner


def test_partial_save_identifies_success(game, monkeypatch):
    import translation_studio.core as core
    config_path = game / "Translation/project.json"
    config = read_json(config_path)
    second = copy.deepcopy(config["tabs"][0])
    second.update(id="extra", datasetId="extra", catalogPath="Translation/Text/extra.json")
    config["tabs"].append(second)
    doc = read_json(game / "Translation/Text/main.json")
    doc["datasetId"] = "extra"
    atomic_write(game / second["catalogPath"], doc)
    atomic_write(config_path, config)
    project = Project(game, editable=True)
    try:
        eid = doc["entries"][0]["id"]
        for tab in ("text", "extra"):
            project.set_text(tab, eid, "ru", "Пуск")
        original = core.atomic_write
        written = []
        def fail_second(path, data, expected=None):
            catalog = path.parent == game / "Translation/Text"
            if written and catalog:
                raise PermissionError("injected second-file failure")
            result = original(path, data, expected)
            if catalog:
                written.append(path)
            return result
        monkeypatch.setattr(core, "atomic_write", fail_second)
        with pytest.raises(StudioError) as caught:
            project.save()
        assert caught.value.issue.code == "partial_save"
        assert str(written[0]) in caught.value.issue.values["saved"]
        assert len(project.dirty) == 1
    finally:
        project.close()


def test_null_empty_and_warning_save(game):
    path = game / "Translation/Text/main.json"
    doc = read_json(path)
    doc["entries"][0]["constraintsByLanguage"]["ru"] = {"maxCodePoints": 1,
        "severity": {"maxCodePoints": "warning"}, "allowEmpty": True}
    atomic_write(path, doc)
    p = Project(game, editable=True)
    try:
        eid = doc["entries"][0]["id"]
        for value in ("Длиннее", "", None):
            p.set_text("text", eid, "ru", value)
            p.save()
            assert read_json(path)["entries"][0]["texts"]["ru"] == value
        assert p.issues(language="ru", complete=True)
    finally:
        p.close()


def test_action_validation_missing_exe_dirty(game):
    p = Project(game, editable=True)
    try:
        action = copy.deepcopy(p.config["actions"][0])
        action["executable"] = "missing-translation-studio-test-program.exe"
        with pytest.raises(StudioError) as error:
            ActionRunner(p, action).start()
        assert error.value.issue.code == "missing_program"
        p.set_text("text", p.documents["text"]["entries"][0]["id"], "ru", "Пуск")
        with pytest.raises(StudioError) as error:
            ActionRunner(p, action).start()
        assert error.value.issue.code == "unsaved"
    finally:
        p.close()


def test_stale_preview_and_recovery_source_mismatch(game):
    audio_path = game / "Translation/Catalogs/audio.json"
    audio = read_json(audio_path)
    audio["entries"][0]["assets"]["ru"]["derivedFromSha256"] = "0" * 64
    atomic_write(audio_path, audio)
    p = Project(game, editable=True)
    try:
        assert p.media_side("voice", "voice.intro.001", "ru")[1]
        eid = p.documents["text"]["entries"][0]["id"]
        p.set_text("text", eid, "ru", "Пуск")
        recovery = p.recovery()
        p.close()
        doc = read_json(game / "Translation/Text/main.json")
        doc["entries"][0]["texts"]["en"] += " changed"
        doc["sourceRevision"] = source_revision(doc)
        atomic_write(game / "Translation/Text/main.json", doc)
        new = Project(game, editable=True)
        try:
            with pytest.raises(StudioError) as error:
                new.restore(recovery)
            assert error.value.issue.code == "source_hash"
            assert not new.dirty
        finally:
            new.close()
    finally:
        p.close()


def test_cross_tab_relation_language_override(game):
    config_path = game / "Translation/project.json"
    config = read_json(config_path)
    tab = copy.deepcopy(config["tabs"][0])
    tab.update(id="other", datasetId="other", catalogPath="Translation/Text/other.json")
    config["tabs"].append(tab)
    doc = read_json(game / "Translation/Text/main.json")
    doc["datasetId"] = "other"
    atomic_write(game / tab["catalogPath"], doc)
    atomic_write(config_path, config)
    eid1, eid2 = doc["entries"][0]["id"], doc["entries"][1]["id"]
    group = {"id": "cross", "type": "textSequence", "label": "Cross tab",
        "parts": [{"ref":{"tabId":"text","entryId":eid1}}, {"literal": " / "},
                  {"ref":{"tabId":"other","entryId":eid2}}]}
    group["partsByLanguage"] = {"ru": list(reversed(group["parts"]))}
    atomic_write(game / "Translation/Catalogs/relations.json", {"schemaVersion": 1, "groups": [group]})
    p = Project(game)
    assert not p.relation_issues
    assert p.text_sequence("cross", "ru")[0]["ref"]["tabId"] == "other"
    assert p.memberships[("other", eid2)] == ["cross"]


def test_invalid_relations_envelope_does_not_break_text(game):
    atomic_write(game / "Translation/Catalogs/relations.json", [])
    p = Project(game)
    assert p.relation_issues and "text" in p.documents
