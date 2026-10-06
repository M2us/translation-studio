"""Single source for the published JSON Schemas (Draft 2020-12)."""
import copy
import json
from pathlib import Path

STR = {"type": "string"}
ID = {"type": "string", "minLength": 1}
NAT = {"type": "integer", "minimum": 0}
LIMIT = {"type": ["integer", "null"], "minimum": 0}
EXT = {"type": "object"}
LABELS = {"type": "object", "properties": {"ru": ID, "en": ID}, "additionalProperties": False}


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


def array(items, minimum=0, unique=False):
    result = {"type": "array", "items": items, "minItems": minimum}
    if unique:
        result["uniqueItems"] = True
    return result


def mapping(value):
    return {"type": "object", "additionalProperties": value, "propertyNames": ID}


RULE_KEYS = ["allowEmpty", "maxCodePoints", "maxLines", "lineBreakToken",
             "byteLimit", "requiredTokens", "allowedCharacters", "forbiddenCharacters"]
RULES = obj({
    "allowEmpty": {"type": "boolean"},
    "maxCodePoints": LIMIT, "maxLines": LIMIT, "lineBreakToken": ID,
    "byteLimit": obj({"maxBytes": NAT, "encoding": {"enum": ["utf-8", "utf-16le"]},
                     "terminatorBytes": NAT}, ["maxBytes", "encoding", "terminatorBytes"]),
    "requiredTokens": array(obj({"token": ID, "count": NAT}, ["token", "count"])),
    "allowedCharacters": {"type": ["string", "null"]},
    "forbiddenCharacters": STR,
    "severity": {"type": "object",
                 "properties": {k: {"enum": ["error", "warning"]} for k in RULE_KEYS},
                 "additionalProperties": False}
})
TAB_BASE = {"id": ID, "type": STR, "label": ID, "labels": LABELS, "catalogPath": ID}
TEXT_TAB = obj({**TAB_BASE, "type": {"const": "text"}, "datasetId": ID,
                "defaultsByLanguage": mapping(RULES)},
               ["id", "type", "label", "catalogPath", "datasetId"])
MEDIA_TAB = obj({**TAB_BASE, "type": {"enum": ["audio", "images"]}},
                ["id", "type", "label", "catalogPath"])
ACTION = obj({
    "id": ID, "label": ID, "labels": LABELS, "kind": {"enum": ["build", "validate"]},
    "executable": ID, "arguments": array(STR), "workingDirectory": ID,
    "outputEncoding": {"enum": ["utf-8", "utf-8-sig", "cp1251", "cp866"]},
    "requiresSaved": {"const": True}, "requiresComplete": {"type": "boolean"},
    "datasetIds": array(ID, unique=True), "targetLanguage": ID, "outputs": array(ID)
}, ["id", "label", "kind", "executable", "arguments", "workingDirectory",
    "requiresSaved", "requiresComplete", "datasetIds", "targetLanguage"])
PROJECT = obj({
    "schemaVersion": {"const": 1}, "projectId": ID, "name": ID,
    "sourceLanguage": ID, "targetLanguages": array(ID, 1, True),
    "tabs": array({"oneOf": [TEXT_TAB, MEDIA_TAB]}, 1),
    "actions": array(ACTION), "relationsPath": ID, "extensions": EXT
}, ["schemaVersion", "projectId", "name", "sourceLanguage", "targetLanguages", "tabs"])
ENTRY = obj({
    "id": ID, "texts": mapping({"type": ["string", "null"]}), "context": STR,
    "group": STR, "comment": STR, "notes": mapping(STR),
    "constraintsByLanguage": mapping(RULES),
    "screenshots": array(obj({"path": ID, "caption": STR}, ["path"])), "extensions": EXT
}, ["id", "texts"])
TEXT = obj({
    "schemaVersion": {"const": 1}, "datasetId": ID, "sourceLanguage": ID,
    "languages": array(ID, 2, True), "sourceRevision": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "entries": array(ENTRY), "extensions": EXT
}, ["schemaVersion", "datasetId", "sourceLanguage", "languages", "sourceRevision", "entries"])
SIDE = obj({
    "previewPath": ID, "assetPath": ID,
    "derivedFromSha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
}, ["previewPath"])
SIDE["dependentRequired"] = {"derivedFromSha256": ["assetPath"]}
VARIANT = copy.deepcopy(SIDE)
VARIANT["properties"].update({"id": ID, "label": ID, "comment": STR})
VARIANT["required"] += ["id", "label"]
VARIANTS = obj({"variants": array(VARIANT, 1), "selectedVariantId": ID},
               ["variants", "selectedVariantId"])
MEDIA_ENTRY = obj({
    "id": ID, "label": ID, "context": STR, "comment": STR,
    "assets": mapping({"oneOf": [SIDE, VARIANTS, {"type": "null"}]}), "extensions": EXT
}, ["id", "label", "assets"])
MEDIA = obj({
    "schemaVersion": {"const": 1}, "kind": {"enum": ["audio", "images"]},
    "sourceLanguage": ID, "languages": array(ID, 2, True),
    "entries": array(MEDIA_ENTRY), "extensions": EXT
}, ["schemaVersion", "kind", "sourceLanguage", "languages", "entries"])
REF = obj({"tabId": ID, "entryId": ID}, ["tabId", "entryId"])
TEXT_PART = {"oneOf": [obj({"ref": REF}, ["ref"]), obj({"literal": STR}, ["literal"])]}
AUDIO_PART = obj({"ref": REF, "pauseAfterMs": NAT}, ["ref"])


def group(kind, part):
    return obj({
        "id": ID, "type": {"const": kind}, "label": ID, "labels": LABELS,
        "comment": STR, "parts": array(part, 2),
        "partsByLanguage": mapping(array(part, 2)), "extensions": EXT
    }, ["id", "type", "label", "parts"])


GROUP = {"oneOf": [group("textSequence", TEXT_PART), group("audioSequence", AUDIO_PART)]}
RELATIONS = obj({"schemaVersion": {"const": 1}, "groups": array(GROUP),
                 "extensions": EXT}, ["schemaVersion", "groups"])

SCHEMAS = {"project": PROJECT, "text": TEXT, "media": MEDIA, "relations": RELATIONS,
           "relation-group": GROUP}


def published(name):
    result = copy.deepcopy(SCHEMAS[name])
    result["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    result["title"] = "Translation Studio " + name + " (schema 1)"
    return result


def export(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in SCHEMAS:
        (directory / (name + ".schema.json")).write_text(
            json.dumps(published(name), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
