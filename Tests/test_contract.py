import copy
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import pytest
from translation_studio.core import (Project, StudioError, parse_json, json_bytes, read_json,
    atomic_write, source_revision, text_issues, safe_path, work_path)


def test_roundtrip_keeps_source_languages_extensions_notes(game):
    project = Project(game, editable=True)
    try:
        before = copy.deepcopy(project.documents["text"])
        entry_id = before["entries"][0]["id"]
        project.set_text("text", entry_id, "ru", "Пуск")
        project.set_note("text", entry_id, "ru", "Проверено")
        project.save()
        after = read_json(project.paths["text"])
        assert after["entries"][0]["texts"]["ru"] == "Пуск"
        assert after["entries"][0]["notes"]["ru"] == "Проверено"
        after["entries"][0]["texts"]["ru"] = before["entries"][0]["texts"]["ru"]
        if "notes" in before["entries"][0]:
            after["entries"][0]["notes"] = before["entries"][0]["notes"]
        else:
            after["entries"][0].pop("notes")
        assert after == before
        assert not project.dirty
    finally:
        project.close()


def test_json_precision_and_duplicate_keys():
    raw = b'{"extensions":{"n":9007199254740993,"v":0.12345678901234567890123456789}}'
    doc = parse_json(raw)
    assert parse_json(json_bytes(doc)) == doc
    assert doc["extensions"]["v"] == Decimal("0.12345678901234567890123456789")
    for bad in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":"\\ud800"}', b'\xef\xbb\xbf{}']:
        with pytest.raises(StudioError):
            parse_json(bad)


def test_constraints_unicode_bytes_tokens_null():
    e = {"id": "e", "texts": {"ru": "😀я"}}
    assert not text_issues(e, "ru", {"maxCodePoints": 2})
    issues = text_issues(e, "ru", {"byteLimit": {"encoding": "utf-8", "maxBytes": 6, "terminatorBytes": 1}})
    assert issues[0].values["actual"] == 7
    assert "e [ru]" in issues[0].message()
    e["texts"]["ru"] = "a{p}b{p}c{0}{0}"
    assert len(text_issues(e, "ru", {"maxLines": 2, "lineBreakToken": "{p}",
        "requiredTokens": [{"token": "{0}", "count": 1}]})) == 2
    e["texts"]["ru"] = None
    assert not text_issues(e, "ru")
    e["texts"]["ru"] = ""
    assert text_issues(e, "ru")[0].code == "empty_text"
    assert not text_issues(e, "ru", {"allowEmpty": True})


@pytest.mark.parametrize("fault", ["source", "duplicate", "language", "unknown", "version"])
def test_bad_catalog_isolated(game, fault):
    path = game / "Translation/Text/main.json"
    doc = read_json(path)
    if fault == "source":
        doc["entries"][0]["texts"]["en"] += "!"
    elif fault == "duplicate":
        doc["entries"].append(copy.deepcopy(doc["entries"][0]))
    elif fault == "language":
        doc["entries"][0]["texts"]["fr"] = "Bonjour"
    elif fault == "unknown":
        doc["invented"] = 1
    else:
        doc["schemaVersion"] = 2
    atomic_write(path, doc)
    p = Project(game)
    assert "text" in p.tab_errors and "voice" in p.documents


def test_conflict_lock_recovery(game):
    p = Project(game, editable=True)
    second = Project(game, editable=True)
    try:
        assert p.writable and not second.writable
        entry = p.documents["text"]["entries"][0]
        p.set_text("text", entry["id"], "ru", "Пуск")
        recovery = p.recovery()
        old = p.paths["text"].read_bytes()
        p.paths["text"].write_bytes(old + b"\n")
        with pytest.raises(StudioError, match="outside"):
            p.save()
        assert p.paths["text"].read_bytes() == old + b"\n"
        p.close()
        restored = Project(game, editable=True)
        try:
            restored.restore(recovery)
            assert restored.entries["text"][entry["id"]]["texts"]["ru"] == "Пуск"
            restored.save()
        finally:
            restored.close()
    finally:
        p.close()
        second.close()


def test_write_failure_preserves_file_and_edits(game, monkeypatch):
    import translation_studio.core as core
    p = Project(game, editable=True)
    try:
        entry = p.documents["text"]["entries"][0]
        p.set_text("text", entry["id"], "ru", "Пуск")
        old = p.paths["text"].read_bytes()
        def denied(*_):
            raise PermissionError("disk unavailable")
        monkeypatch.setattr(core.os, "replace", denied)
        with pytest.raises(StudioError):
            p.save()
        assert p.paths["text"].read_bytes() == old
        assert p.dirty
        assert not list(p.paths["text"].parent.glob("*.tmp"))
    finally:
        p.close()


def test_immutable_fields_and_limit(game):
    p = Project(game, editable=True)
    try:
        e = p.documents["text"]["entries"][0]
        p.set_text("text", e["id"], "ru", "x" * 500)
        with pytest.raises(StudioError, match="Fix errors"):
            p.save()
        p.set_text("text", e["id"], "ru", "Пуск")
        e["extensions"]["tamper"] = 1
        with pytest.raises(StudioError, match="Protected"):
            p.save()
    finally:
        p.close()


@pytest.mark.parametrize("relative", ["../x", "D:/x", "/x", "\\\\host\\x", "Translation/../../x", "https://x", "x:y"])
def test_bad_paths(game, relative):
    with pytest.raises(StudioError):
        safe_path(game, relative)


def test_work_junction_and_protected_output(game):
    original = game / "Original"
    original.mkdir()
    work = game / "Work"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(work), str(original)], capture_output=True)
    assert result.returncode == 0, result.stderr
    with pytest.raises(StudioError):
        work_path(game, "Work/TranslationStudio/test")
    config = read_json(game / "Translation/project.json")
    config["actions"][0]["outputs"] = ["Original/output"]
    atomic_write(game / "Translation/project.json", config)
    with pytest.raises(StudioError):
        Project(game)


def test_relations_memberships_languages_and_bad_ref(game):
    p = Project(game)
    shared = "728dcc4a-0bce-45b4-9e6a-3371d19b5d8c"
    assert len(p.memberships[("text", shared)]) == 2
    gid = p.memberships[("text", shared)][0]
    assert "".join(part["text"] or "" for part in p.text_sequence(gid, "ru")) == "Возможно, что-то произошло"
    relation_path = game / "Translation/Catalogs/relations.json"
    doc = read_json(relation_path)
    doc["groups"][0]["parts"][0]["ref"]["entryId"] = "missing"
    atomic_write(relation_path, doc)
    bad = Project(game)
    assert bad.relation_issues and len(bad.groups) == len(p.groups) - 1
    assert not bad.tab_errors


def test_audio_queue_null_no_fallback(game):
    p = Project(game)
    group = next(g["id"] for g in p.groups.values() if g["type"] == "audioSequence")
    assert len(p.audio_queue("voice", "voice.intro.001", "ru", group)) == 3
    with pytest.raises(StudioError, match="missing"):
        p.audio_queue("voice", "voice.intro.004", "ru")


def test_source_hash_independent_of_sort_translation(game):
    p = Project(game)
    doc = copy.deepcopy(p.documents["text"])
    expected = doc["sourceRevision"]
    doc["entries"].reverse()
    doc["entries"][0]["texts"]["ru"] = "Other"
    assert source_revision(doc) == expected


def test_no_config_no_side_effects(tmp_path):
    with pytest.raises(StudioError, match="not found"):
        Project(tmp_path, editable=True)
    assert not list(tmp_path.iterdir())
