"""Shared reader/writer. No Qt imports; safe to use from a game's build adapter."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import struct
import tempfile
import time
import wave
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path, PureWindowsPath
from typing import Any

from jsonschema import Draft202012Validator

from .schemas import SCHEMAS
from .i18n import tr


@dataclass
class Issue:
    code: str
    values: dict = field(default_factory=dict)
    severity: str = "error"
    tab_id: str = ""
    entry_id: str = ""

    def message(self, language="en"):
        return tr(self.code, language, **self.values)

    def as_dict(self, language="en"):
        return {"code": self.code, "severity": self.severity, "tabId": self.tab_id,
                "entryId": self.entry_id, "message": self.message(language), "details": self.values}


class StudioError(Exception):
    def __init__(self, code, **values):
        self.issue = Issue(code, values)
        super().__init__(self.issue.message("en"))


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    try:
        with Path(path).open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError:
        return None


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise StudioError("duplicate", id=key)
        result[key] = value
    return result


def check_strings(value):
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
    elif isinstance(value, dict):
        for key, item in value.items():
            check_strings(key)
            check_strings(item)
    elif isinstance(value, list):
        for item in value:
            check_strings(item)


def parse_json(raw: bytes, path="<memory>"):
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_float=Decimal,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        check_strings(data)
        return data
    except StudioError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise StudioError("json", path=str(path), detail=str(error)) from error


def read_json(path):
    try:
        return parse_json(Path(path).read_bytes(), path)
    except OSError as error:
        raise StudioError("io", path=str(path), detail=str(error)) from error


def encode_json(value, depth=0):
    """Preserve arbitrary JSON integers and decimals without a float round trip."""
    indent = "  " * depth
    next_indent = "  " * (depth + 1)
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        value.encode("utf-8", errors="strict")
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite decimal")
        return str(value)
    if isinstance(value, float):
        return json.dumps(value, allow_nan=False)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[\n" + ",\n".join(next_indent + encode_json(item, depth + 1) for item in value) + "\n" + indent + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{\n" + ",\n".join(next_indent + encode_json(key) + ": " + encode_json(item, depth + 1)
                                 for key, item in value.items()) + "\n" + indent + "}"
    raise TypeError(type(value).__name__)


def json_bytes(value):
    return (encode_json(value) + "\n").encode("utf-8")


VALIDATORS = {key: Draft202012Validator(schema) for key, schema in SCHEMAS.items()}


def validate_schema(kind, data, path):
    error = next(VALIDATORS[kind].iter_errors(data), None)
    if error:
        while error.context:
            error = max(error.context, key=lambda item: len(item.absolute_path))
        detail = encode_json({"rule": error.validator, "expected": error.validator_value})
        raise StudioError("schema", path=str(path),
                          field="/".join(map(str, error.absolute_path)) or "/", detail=detail)


def unique(values):
    seen = set()
    for value in values:
        if value in seen:
            raise StudioError("duplicate", id=value)
        seen.add(value)


def safe_path(root, relative, *, translation=False):
    root = Path(root).resolve()
    if (not isinstance(relative, str) or not relative or "\x00" in relative
            or "\\" in relative or ":" in relative or PureWindowsPath(relative).is_absolute()
            or relative.startswith("/") or ".." in Path(relative).parts):
        raise StudioError("path", path=str(relative))
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise StudioError("path", path=relative)
    if translation and (not Path(relative).parts or Path(relative).parts[0] != "Translation"
                        or not result.is_relative_to((root / "Translation").resolve())
                        or (root / "Translation").is_symlink()):
        raise StudioError("path", path=relative)
    if translation:
        # Check the lexical directory too: a Translation junction may point at Original.
        protected = [(root / name).resolve() for name in ("Original", "Extracted")]
        if any(result.is_relative_to(parent) for parent in protected):
            raise StudioError("path", path=relative)
    return result


def source_revision(document):
    pieces = [document["sourceLanguage"]]
    for entry in sorted(document["entries"], key=lambda item: item["id"].encode("utf-8")):
        pieces.extend([entry["id"], entry["texts"][document["sourceLanguage"]]])
    hashed = hashlib.sha256()
    for piece in pieces:
        raw = piece.encode("utf-8")
        hashed.update(struct.pack(">I", len(raw)))
        hashed.update(raw)
    return hashed.hexdigest()


def work_path(root, relative):
    """App-owned writes must stay under the real, non-redirected Work directory."""
    root = Path(root).resolve()
    result = safe_path(root, relative)
    lexical = root / relative
    if not lexical.is_relative_to(root / "Work") or result != lexical:
        raise StudioError("path", path=relative)
    return result


def validate_rules(rules):
    for rule in rules.values():
        tokens = [item["token"] for item in rule.get("requiredTokens", [])]
        unique(tokens)


def asset_candidates(side):
    """All image alternatives, or the single legacy asset; no implicit fallback."""
    return side.get("variants", [side]) if side else []


def selected_asset(side, variant_id=None):
    if not side or "variants" not in side:
        return side
    selected = variant_id if variant_id is not None else side["selectedVariantId"]
    return next((variant for variant in side["variants"] if variant["id"] == selected), None)


def validate_catalog(document, tab, config, path):
    kind = "text" if tab["type"] == "text" else "media"
    validate_schema(kind, document, path)
    languages = {config["sourceLanguage"], *config["targetLanguages"]}
    if (document["sourceLanguage"] != config["sourceLanguage"]
            or set(document["languages"]) != languages):
        raise StudioError("languages", path=str(path))
    unique(entry["id"] for entry in document["entries"])
    targets = set(config["targetLanguages"])
    for entry in document["entries"]:
        values = entry["texts" if kind == "text" else "assets"]
        if set(values) != languages or values[config["sourceLanguage"]] is None:
            raise StudioError("languages", path=str(path) + "#" + entry["id"])
        if kind == "text":
            for key in ("notes", "constraintsByLanguage"):
                if not set(entry.get(key, {})) <= targets:
                    raise StudioError("languages", path=str(path) + "#" + entry["id"])
            validate_rules(entry.get("constraintsByLanguage", {}))
        else:
            for language, side in values.items():
                if side and "variants" in side:
                    if tab["type"] != "images" or language == config["sourceLanguage"]:
                        raise StudioError("variant", id=entry["id"], detail="target images only")
                    unique(variant["id"] for variant in side["variants"])
                    if selected_asset(side) is None:
                        raise StudioError("variant", id=entry["id"], detail=side["selectedVariantId"])
    if kind == "text":
        if document["datasetId"] != tab["datasetId"]:
            raise StudioError("dataset", path=str(path))
        if document["sourceRevision"] != source_revision(document):
            raise StudioError("source_hash", path=str(path))
    elif document["kind"] != tab["type"]:
        raise StudioError("dataset", path=str(path))


def text_issues(entry, language, defaults=None, tab_id=""):
    value = entry["texts"][language]
    if value is None:
        return []
    rules = {**(defaults or {}), **entry.get("constraintsByLanguage", {}).get(language, {})}
    issues = []

    def issue(rule, actual=None, limit=None, code="constraint"):
        values = {"id": entry["id"], "language": language}
        if code == "constraint":
            values.update(rule=rule, actual=actual, limit=limit)
        issues.append(Issue(code, values, rules.get("severity", {}).get(rule, "error"), tab_id, entry["id"]))

    if value == "" and not rules.get("allowEmpty", False):
        issue("allowEmpty", code="empty_text")
    for key, count in (("maxCodePoints", len(value)),
                       ("maxLines", 1 + value.count(rules.get("lineBreakToken", "\n")))):
        limit = rules.get(key)
        if limit is not None and count > limit:
            issue(key, count, limit)
    byte_limit = rules.get("byteLimit")
    if byte_limit:
        try:
            count = len(value.encode(byte_limit["encoding"], errors="strict")) + byte_limit["terminatorBytes"]
            if count > byte_limit["maxBytes"]:
                issue("byteLimit", count, byte_limit["maxBytes"])
        except UnicodeError:
            issue("byteLimit", "Unicode", byte_limit["encoding"])
    for token in rules.get("requiredTokens", []):
        count = value.count(token["token"])
        if count != token["count"]:
            issue("requiredTokens", token["token"] + " × " + str(count), token["count"])
    allowed = rules.get("allowedCharacters")
    forbidden = set(rules.get("forbiddenCharacters", ""))
    for rule, invalid in (("allowedCharacters", set(value) - set(allowed) if allowed is not None else set()),
                          ("forbiddenCharacters", set(value) & forbidden)):
        if invalid:
            characters = " ".join(encode_json(char) + f" (U+{ord(char):04X})" for char in sorted(invalid))
            issue(rule, characters, rules[rule])
    return issues


def atomic_write(path, data, expected=None):
    path = Path(path)
    payload = json_bytes(data)
    parse_json(payload, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if expected is not None and file_hash(path) != expected:
            raise StudioError("conflict", path=str(path))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return digest(payload)


class ProjectLock:
    def __init__(self, path):
        self.stream = None
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = self.path.open("a+b")
            if self.path.stat().st_size == 0:
                self.stream.write(b"0")
                self.stream.flush()
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if self.stream:
                self.stream.close()
            self.stream = None

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None


class Project:
    def __init__(self, root, *, editable=False):
        self.root = Path(root).resolve()
        self.config_path = safe_path(self.root, "Translation/project.json")
        if not self.config_path.is_file():
            raise StudioError("no_project", path=str(self.config_path))
        raw = self.config_path.read_bytes()
        self.config = parse_json(raw, self.config_path)
        validate_schema("project", self.config, self.config_path)
        self.hashes = {self.config_path: digest(raw)}
        self.tabs = {tab["id"]: tab for tab in self.config["tabs"]}
        unique(tab["id"] for tab in self.config["tabs"])
        unique(tab["datasetId"] for tab in self.config["tabs"] if tab["type"] == "text")
        unique(action["id"] for action in self.config.get("actions", []))
        if self.config["sourceLanguage"] in self.config["targetLanguages"]:
            raise StudioError("languages", path=str(self.config_path))
        self.paths = {}
        self.documents = {}
        self.baselines = {}
        self.baseline_entries = {}
        self.modified = set()
        self.entries = {}
        self.tab_errors = {}
        self.relation_issues = []
        self.groups = {}
        self.memberships = {}
        self.lock = None
        self.writable = False
        self.dirty = set()
        for tab_id, tab in self.tabs.items():
            path = safe_path(self.root, tab["catalogPath"], translation=tab["type"] == "text")
            if path in self.paths.values() or path == self.config_path:
                raise StudioError("path", path=str(path))
            self.paths[tab_id] = path
            if not set(tab.get("defaultsByLanguage", {})) <= set(self.config["targetLanguages"]):
                raise StudioError("languages", path=str(self.config_path))
            validate_rules(tab.get("defaultsByLanguage", {}))
            try:
                raw = path.read_bytes()
                doc = parse_json(raw, path)
                validate_catalog(doc, tab, self.config, path)
                if tab["type"] == "text":
                    for entry in doc["entries"]:
                        for screenshot in entry.get("screenshots", []):
                            safe_path(self.root, screenshot["path"])
                else:
                    for entry in doc["entries"]:
                        for side in entry["assets"].values():
                            if side and "variants" in side:
                                safe_path(self.root, tab["catalogPath"], translation=True)
                            for candidate in asset_candidates(side):
                                for key in ("previewPath", "assetPath"):
                                    if key in candidate:
                                        safe_path(self.root, candidate[key])
                self.documents[tab_id] = doc
                self.baselines[tab_id] = copy.deepcopy(doc)
                self.baseline_entries[tab_id] = {e["id"]: e for e in self.baselines[tab_id]["entries"]}
                self.entries[tab_id] = {entry["id"]: entry for entry in doc["entries"]}
                self.hashes[path] = digest(raw)
            except (StudioError, OSError) as error:
                self.tab_errors[tab_id] = (error.issue if isinstance(error, StudioError)
                                          else Issue("io", {"path": str(path), "detail": str(error)}))
        for action in self.config.get("actions", []):
            self.validate_action_config(action)
        self.load_relations()
        if editable:
            try:
                self.lock = ProjectLock(work_path(self.root, "Work/TranslationStudio/editor.lock"))
                self.writable = self.lock.stream is not None
            except StudioError:
                self.writable = False

        if self.writable:
            try:
                self._finish_interrupted_snapshot()
            except Exception:
                self.close()
                raise

    def close(self):
        if self.lock:
            self.lock.close()
        self.writable = False

    def validate_action_config(self, action):
        datasets = {tab.get("datasetId") for tab in self.tabs.values() if tab["type"] == "text"}
        if not set(action["datasetIds"]) <= datasets or action["targetLanguage"] not in self.config["targetLanguages"]:
            raise StudioError("invalid_action", id=action["id"])
        safe_path(self.root, action["workingDirectory"])
        executable = action["executable"]
        if "/" in executable or "\\" in executable or ":" in executable:
            safe_path(self.root, executable)
        elif not re.fullmatch(r"[A-Za-z0-9_.-]+", executable):
            raise StudioError("path", path=executable)
        for output in action.get("outputs", []):
            result = safe_path(self.root, output)
            if result == self.root or any(result.is_relative_to((self.root / item).resolve())
                                          for item in ("Translation", "Original", "Extracted", "Scripts")):
                raise StudioError("path", path=output)

    def load_relations(self):
        relative = self.config.get("relationsPath")
        if not relative:
            return
        try:
            path = safe_path(self.root, relative)
            if path in self.paths.values() or path == self.config_path:
                raise StudioError("path", path=relative)
            raw = path.read_bytes()
            document = parse_json(raw, path)
            if not isinstance(document, dict):
                raise StudioError("json", path=str(path), detail="object")
            # Validate envelope separately so one invalid group does not hide valid groups.
            envelope = copy.deepcopy(document)
            envelope["groups"] = []
            validate_schema("relations", envelope, path)
            if not isinstance(document.get("groups"), list):
                raise StudioError("relation", id=relative, detail="groups")
            self.hashes[path] = digest(raw)
            ids = [item.get("id") for item in document["groups"] if isinstance(item, dict)]
            for group in document["groups"]:
                group_id = group.get("id", "?") if isinstance(group, dict) else "?"
                try:
                    validate_schema("relation-group", group, path)
                    if ids.count(group_id) != 1:
                        raise StudioError("duplicate", id=group_id)
                    variants = group.get("partsByLanguage", {})
                    if not set(variants) <= {self.config["sourceLanguage"], *self.config["targetLanguages"]}:
                        raise StudioError("languages", path=str(path))
                    references = set()
                    for parts in [group["parts"], *variants.values()]:
                        if sum("ref" in part for part in parts) < 2:
                            raise StudioError("relation", id=group_id, detail="ref >= 2")
                        for part in parts:
                            if "ref" not in part:
                                continue
                            ref = part["ref"]
                            tab_id, entry_id = ref["tabId"], ref["entryId"]
                            expected = "text" if group["type"] == "textSequence" else "audio"
                            if (self.tabs.get(tab_id, {}).get("type") != expected
                                    or entry_id not in self.entries.get(tab_id, {})):
                                raise StudioError("relation", id=group_id, detail=tab_id + "/" + entry_id)
                            references.add((tab_id, entry_id))
                    self.groups[group_id] = group
                    for ref in references:
                        self.memberships.setdefault(ref, []).append(group_id)
                except StudioError as error:
                    self.relation_issues.append(error.issue)
        except (StudioError, OSError) as error:
            self.relation_issues.append(error.issue if isinstance(error, StudioError)
                                       else Issue("io", {"path": relative, "detail": str(error)}))

    def issues(self, tab_ids=None, language=None, complete=False):
        result = []
        for tab_id in (self.tabs if tab_ids is None else tab_ids):
            if tab_id in self.tab_errors:
                result.append(self.tab_errors[tab_id])
                continue
            tab = self.tabs[tab_id]
            if tab["type"] != "text":
                continue
            for entry in self.documents[tab_id]["entries"]:
                for lang in ([language] if language else self.config["targetLanguages"]):
                    defaults = tab.get("defaultsByLanguage", {}).get(lang, {})
                    result.extend(text_issues(entry, lang, defaults, tab_id))
                    if complete and entry["texts"][lang] is None:
                        result.append(Issue("untranslated", {"id": entry["id"], "language": lang},
                                            tab_id=tab_id, entry_id=entry["id"]))
        return result

    def set_text(self, tab_id, entry_id, language, value):
        if not self.writable:
            raise StudioError("locked", path=str(self.root))
        if language not in self.config["targetLanguages"] or not (value is None or isinstance(value, str)):
            raise StudioError("languages", path=tab_id)
        if value is not None:
            check_strings(value)
        self.entries[tab_id][entry_id]["texts"][language] = value
        self.update_dirty(tab_id, entry_id)

    def set_note(self, tab_id, entry_id, language, value):
        if not self.writable:
            raise StudioError("locked", path=str(self.root))
        if language not in self.config["targetLanguages"] or not isinstance(value, str):
            raise StudioError("languages", path=tab_id)
        check_strings(value)
        entry = self.entries[tab_id][entry_id]
        if value or language in self.baseline_entries[tab_id][entry_id].get("notes", {}):
            entry.setdefault("notes", {})[language] = value
        elif "notes" in entry:
            entry["notes"].pop(language, None)
            if not entry["notes"] and "notes" not in self.baseline_entries[tab_id][entry_id]:
                del entry["notes"]
        self.update_dirty(tab_id, entry_id)

    def update_dirty(self, tab_id, entry_id):
        ref = (tab_id, entry_id)
        if self.entries[tab_id][entry_id] != self.baseline_entries[tab_id][entry_id]:
            self.modified.add(ref)
        else:
            self.modified.discard(ref)
        self.dirty = {tab for tab, _ in self.modified}

    def changed_entry(self, tab_id, entry_id, language):
        baseline = self.baseline_entries[tab_id][entry_id]
        current = self.entries[tab_id][entry_id]
        if self.tabs[tab_id]["type"] != "text":
            return baseline["assets"][language] != current["assets"][language]
        return (baseline["texts"][language] != current["texts"][language]
                or baseline.get("notes", {}).get(language, "") != current.get("notes", {}).get(language, ""))

    def set_variant(self, tab_id, entry_id, language, variant_id):
        if not self.writable:
            raise StudioError("locked", path=str(self.root))
        if self.tabs[tab_id]["type"] != "images" or language not in self.config["targetLanguages"]:
            raise StudioError("languages", path=tab_id)
        side = self.entries[tab_id][entry_id]["assets"][language]
        if not side or "variants" not in side or selected_asset(side, variant_id) is None:
            raise StudioError("variant", id=entry_id, detail=str(variant_id))
        side["selectedVariantId"] = variant_id
        self.update_dirty(tab_id, entry_id)

    def editable_catalog(self, tab_id):
        return self.tabs[tab_id]["type"] == "text" or (
            self.tabs[tab_id]["type"] == "images" and any(
                side and "variants" in side for entry in self.documents[tab_id]["entries"]
                for side in entry["assets"].values()))

    def protected_document(self, tab_id, document):
        """Strip only author-editable values, retaining every other byte-level JSON value."""
        protected = copy.deepcopy(document)
        for entry in protected["entries"]:
            for language in self.config["targetLanguages"]:
                if self.tabs[tab_id]["type"] == "text":
                    entry["texts"][language] = None
                else:
                    side = entry["assets"][language]
                    if side and "variants" in side:
                        side["selectedVariantId"] = None
            if self.tabs[tab_id]["type"] == "text":
                entry.pop("notes", None)
        return protected

    def check_external(self):
        for path, old_hash in self.hashes.items():
            if file_hash(path) != old_hash:
                raise StudioError("conflict", path=str(path))

    def save(self):
        if not self.dirty:
            return []
        if not self.writable:
            raise StudioError("locked", path=str(self.root))
        self.check_external()
        errors = []
        for tab_id in self.dirty:
            doc = self.documents[tab_id]
            validate_catalog(doc, self.tabs[tab_id], self.config, self.paths[tab_id])
            if (not self.editable_catalog(tab_id) or self.protected_document(tab_id, doc)
                    != self.protected_document(tab_id, self.baselines[tab_id])):
                raise StudioError("immutable", path=str(self.paths[tab_id]))
            errors.extend(issue for issue in self.issues([tab_id]) if issue.severity == "error")
        if errors:
            error = StudioError("validation", detail="\n".join(item.message() for item in errors))
            error.issues = errors
            raise error
        # Keep the editor buffer on disk before attempting any catalog replacement.
        try:
            self.recovery()
            pending = self.snapshot_path("previous.pending.tmp")
            atomic_write(pending, self.snapshot(self.baselines))
        except OSError as error:
            raise StudioError("io", path=str(self.snapshot_path("draft.json")), detail=str(error)) from error
        saved = []
        saved_tabs = []
        for tab_id in list(self.dirty):
            path = safe_path(self.root, self.tabs[tab_id]["catalogPath"], translation=True)
            if path != self.paths[tab_id]:
                raise StudioError("conflict", path=str(path))
            try:
                self.hashes[path] = atomic_write(path, self.documents[tab_id], self.hashes[path])
            except (OSError, StudioError) as error:
                if saved:
                    os.replace(pending, self.snapshot_path("previous.json"))
                    self._acknowledge_saved(saved_tabs)
                    raise StudioError("partial_save", saved=", ".join(saved), path=str(path),
                                      detail=str(error)) from error
                pending.unlink(missing_ok=True)
                if isinstance(error, StudioError):
                    raise
                raise StudioError("io", path=str(path), detail=str(error)) from error
            saved.append(str(path))
            saved_tabs.append(tab_id)
        os.replace(pending, self.snapshot_path("previous.json"))
        self.snapshot_path("draft.json").unlink(missing_ok=True)
        self._acknowledge_saved(saved_tabs)
        return saved

    def _acknowledge_saved(self, tabs):
        for tab_id in tabs:
            self.baselines[tab_id] = copy.deepcopy(self.documents[tab_id])
            self.baseline_entries[tab_id] = {e["id"]: e for e in self.baselines[tab_id]["entries"]}
            self.modified = {ref for ref in self.modified if ref[0] != tab_id}
            self.dirty.remove(tab_id)

    def snapshot_path(self, name):
        return work_path(self.root, "Work/TranslationStudio/Recovery/" + name)

    def snapshot(self, documents):
        return {"projectRoot": str(self.root), "createdAt": time.time(),
                "catalogs": {self.tabs[key]["catalogPath"]: copy.deepcopy(doc) for key, doc in documents.items()
                             if self.editable_catalog(key)}}

    def _finish_interrupted_snapshot(self):
        pending = self.snapshot_path("previous.pending.tmp")
        if not pending.exists():
            return
        data = read_json(pending)
        if not isinstance(data, dict) or not isinstance(data.get("catalogs"), dict):
            raise StudioError("json", path=str(pending), detail="catalogs")
        current = self.snapshot(self.baselines)["catalogs"]
        if current != data["catalogs"]:
            os.replace(pending, self.snapshot_path("previous.json"))
        else:
            pending.unlink()

    def recovery(self):
        if not self.writable:
            raise StudioError("locked", path=str(self.root))
        path = self.snapshot_path("draft.json")
        data = self.snapshot(self.documents)
        # Repeated timers without edits don't touch the same recovery file.
        if path.exists() and read_json(path).get("catalogs") == data["catalogs"]:
            return path
        atomic_write(path, data)
        return path

    def restore(self, path, *, data=None):
        if not self.writable:
            raise StudioError("locked", path=str(self.root))
        data = read_json(path) if data is None else data
        if not isinstance(data, dict) or not isinstance(data.get("catalogs"), dict):
            raise StudioError("json", path=str(path), detail="catalogs")
        pending = []
        for relative, recovered in data["catalogs"].items():
            tab_id = next((key for key, tab in self.tabs.items()
                           if key in self.documents and self.editable_catalog(key)
                           and tab["catalogPath"] == relative), None)
            if tab_id is None:
                raise StudioError("path", path=relative)
            validate_catalog(recovered, self.tabs[tab_id], self.config, relative)
            if self.tabs[tab_id]["type"] == "text":
                if recovered["sourceRevision"] != self.documents[tab_id]["sourceRevision"]:
                    raise StudioError("source_hash", path=relative)
            elif (self.protected_document(tab_id, recovered)
                  != self.protected_document(tab_id, self.documents[tab_id])):
                raise StudioError("immutable", path=relative)
            pending.append((tab_id, recovered))
        for tab_id, recovered in pending:
            for entry in recovered["entries"]:
                for language in self.config["targetLanguages"]:
                    if self.tabs[tab_id]["type"] == "text":
                        self.set_text(tab_id, entry["id"], language, entry["texts"][language])
                        self.set_note(tab_id, entry["id"], language, entry.get("notes", {}).get(language, ""))
                    else:
                        side = entry["assets"][language]
                        if side and "variants" in side:
                            self.set_variant(tab_id, entry["id"], language, side["selectedVariantId"])

    def parts(self, group_id, language):
        group = self.groups[group_id]
        return group.get("partsByLanguage", {}).get(language, group["parts"])

    def text_sequence(self, group_id, language):
        result = []
        for part in self.parts(group_id, language):
            if "literal" in part:
                result.append({"text": part["literal"], "ref": None})
            else:
                ref = part["ref"]
                entry = self.entries[ref["tabId"]][ref["entryId"]]
                result.append({"text": entry["texts"][language], "ref": ref})
        return result

    def asset_side(self, tab_id, entry_id, language, variant_id=None):
        """Builder API: resolve the saved selection; assetPath is the build input."""
        return selected_asset(self.entries[tab_id][entry_id]["assets"][language], variant_id)

    def media_side(self, tab_id, entry_id, language, variant_id=None):
        side = self.asset_side(tab_id, entry_id, language, variant_id)
        if side is None:
            raise StudioError("untranslated", id=entry_id, language=language)
        path = safe_path(self.root, side["previewPath"])
        if not path.is_file():
            raise StudioError("missing_file", path=str(path))
        stale = False
        if "derivedFromSha256" in side:
            asset = safe_path(self.root, side["assetPath"])
            stale = file_hash(asset) != side["derivedFromSha256"]
        return path, stale

    def audio_queue(self, tab_id, entry_id, language, group_id=None):
        parts = (self.parts(group_id, language) if group_id else
                 [{"ref": {"tabId": tab_id, "entryId": entry_id}}])
        queue = []
        for part in parts:
            ref = part["ref"]
            path, stale = self.media_side(ref["tabId"], ref["entryId"], language)
            try:
                with wave.open(str(path), "rb") as wav:
                    if wav.getcomptype() != "NONE" or wav.getnframes() == 0:
                        raise ValueError("PCM")
                    duration = wav.getnframes() / wav.getframerate()
            except (wave.Error, OSError, ValueError, EOFError):
                raise StudioError("unsupported_audio", path=str(path))
            queue.append({"path": str(path), "id": ref["entryId"], "pause": part.get("pauseAfterMs", 0),
                          "duration": duration, "stale": stale})
        return queue
