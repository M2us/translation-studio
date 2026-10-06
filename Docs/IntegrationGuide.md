# Integrating a game project

This is an implementation guide for **schemaVersion 1**. Read your game's own instructions first. The editor is universal; an integration supplies standard data and a game-specific builder, without modifying the editor.

## Deliverables

1. Immutable original/extracted resources for comparison.
2. `Translation/project.json` and author catalogs containing original and translated values under stable custom IDs.
3. A builder reading those same catalogs, validating game constraints and producing checked output.
4. A game README describing commands, dependencies, confirmed limits, SDK location/version and actual verification scope.

Prepare initial translations before handing the project to a reviewer. During migration, old TXT becomes a generated intermediate or a preserved migration input, not another editable translation. Keep manual edits when re-extracting.

## Minimal working text project

Create `Translation/project.json`:

```json
{
  "schemaVersion": 1,
  "projectId": "my-game",
  "name": "My Game",
  "sourceLanguage": "en",
  "targetLanguages": ["ru"],
  "tabs": [{
    "id": "text", "type": "text", "label": "Text",
    "labels": {"en": "Text", "ru": "Текст"},
    "datasetId": "main", "catalogPath": "Translation/Text/main.json"
  }]
}
```

Create `Translation/Text/main.json`. The hash below matches this exact ID and source text:

```json
{
  "schemaVersion": 1,
  "datasetId": "main",
  "sourceLanguage": "en",
  "languages": ["en", "ru"],
  "sourceRevision": "aa48e72206141812333ee32ce358a6aaf560b96b5bffaa6e17ba5a24c694c849",
  "entries": [{
    "id": "menu.start",
    "texts": {"en": "Start", "ru": "Начать"},
    "comment": "Main menu: button that starts the game.",
    "constraintsByLanguage": {"ru": {"maxCodePoints": 20}}
  }]
}
```

The Russian string is example translation content, not an application requirement. Other source/target languages use the same contract. `menu.start` is a stable demonstration key; extracted projects should usually generate `str(uuid.uuid4())` once and keep the mapping across extractions. Do not derive identity from text, row number or game offset.

JSON is UTF-8 without BOM. All paths are game-root-relative with `/`; reject absolute paths and escapes through traversal/junctions. Writable catalogs belong in `Translation`. The whole game folder should be movable without rewriting its config.

## Validate and connect the builder

```powershell
$studioCli = 'C:/Tools/Translation Studio/TranslationStudio.Cli.exe'
& $studioCli validate 'C:/Games/My Game' --language ru --complete
& $studioCli validate 'C:/Games/My Game' --language ru --media --strict-relations
& $studioCli source-hash 'C:/Games/My Game/Translation/Text/main.json'
```

Messages default to English; optional `--ui-language ru` goes before the subcommand. Exit codes, flags and API calls are documented in [API](API.md). `source-hash` only prints a hash; it does not repair source automatically. Use it only after source review.

Copy the complete portable `SDK` to `Tools/TranslationStudioSdk` in the game, or pin and document a shared location. Install its requirements into the builder environment (Python 3.12 and jsonschema; no Qt). Record SDK hashes/schema version while there is no assigned application release.

A minimal builder entry point:

```python
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tools/TranslationStudioSdk"))
from translation_studio.core import Project

project = Project(ROOT)
language = "ru"
errors = [i for i in project.issues(language=language, complete=True)
          if i.severity == "error"]
if errors:
    raise SystemExit("\n".join(i.message() for i in errors))
project.check_external()
for entry in project.documents["text"]["entries"]:
    translated = entry["texts"][language]
    binding = entry.get("extensions", {}).get("game", {}).get("binding", {})
    # Validate game encoding, tags and budgets; pack translated using binding.
project.check_external()
# Publish checked output from Work to Builds.
```

`issues()` does not validate all media or interpret game extensions. Check `relation_issues` if your builder depends on relations. Resolve media using `asset_side`/`media_side`, then validate actual build resources. Catalog failures appear in `tab_errors` and `issues()`; an invalid project config raises `StudioError`.

Never fall back to a stale derived TXT when JSON validation fails. Regenerate intermediate data from saved catalogs, validate bytes/pointers/font coverage and publish the checked result. The builder must also work with the GUI closed. `Examples/*/Scripts/build.py` demonstrates two synthetic formats.

## Optional metadata and rules

| Feature | Configuration | If omitted |
| --- | --- | --- |
| Shared explanation | `comment` on text, media or relation group | Empty comment |
| Location/group | `context`, text `group` | Empty context |
| Translator note | `notes` keyed by target language | No note; GUI may create one |
| Project UI label | `labels` with English/Russian keys | Required `label` is used |
| Constraints | Tab `defaultsByLanguage`, record `constraintsByLanguage` | No numeric limits; empty string disallowed; error severity |
| Context screenshots | Record `screenshots` array | Screenshot block hidden |
| Image alternatives | Target side `variants`/`selectedVariantId` | Ordinary single side |
| Fragment connections | `relationsPath` | Relations hidden |
| Custom buttons | `actions` | External CLI builder only |
| Game bindings/flags | Namespaced `extensions` | Not required by GUI |

`texts` must contain exactly every declared language. Source is a string; target null means untranslated, an empty string means intentionally empty. Notes/rules use target languages only. Source, context and rules are authored by the integration, not changed through ordinary text editing.

Example rule object for one target language:

```json
{
  "allowEmpty": false,
  "maxCodePoints": 20,
  "maxLines": 2,
  "lineBreakToken": "{p}",
  "byteLimit": {"maxBytes": 64, "encoding": "utf-8", "terminatorBytes": 1},
  "requiredTokens": [{"token": "{0}", "count": 1}],
  "forbiddenCharacters": "^~",
  "severity": {"maxCodePoints": "warning"}
}
```

Place it under `constraintsByLanguage.<target>` or tab defaults. Each provided field replaces its inherited counterpart. Null numeric limits disable them; `requiredTokens: []` removes inherited token checks. `byteLimit` replaces the complete object. These values are illustrative, not confirmed restrictions for any real game.

Allowed/forbidden characters are literal sets, not regexes: `"0123456789 "` allows digits and space; `"A-Z"` means three characters. Include whitespace and tag characters explicitly in whitelists. The editor has no hardcoded forbidden letters. A game's encoding or font determines the actual set. See [ProjectFormat](ProjectFormat.md) for exact inheritance, null and Unicode semantics.

## Media and screenshots

Add a tab with `id`, `type: "audio"` or `"images"`, `label`, `catalogPath`. Its catalog contains `schemaVersion`, `kind`, `sourceLanguage`, `languages`, `entries`. Example entry:

```json
{
  "id": "voice.intro.001", "label": "Opening narration",
  "comment": "Spoken by the commander.",
  "assets": {
    "en": {"previewPath": "Extracted/Preview/intro-001.wav"},
    "ru": {"previewPath": "Translation/Audio/intro-001.wav", "assetPath": "Translation/Audio/intro-001.wav"}
  }
}
```

Supply PNG or integer PCM WAV (8/16/24/32-bit). Convert proprietary game formats in the adapter. Missing target media is null, never a silent fallback to source. `assetPath` is optional; otherwise preview is the resource. For derived previews, include `assetPath` and `derivedFromSha256` (hash of the asset bytes) and refresh both after changes.

A text entry may add `screenshots: [{"path":"Translation/Context/main-menu.png","caption":"Main menu"}]`. Supply a real PNG. Captions are optional, paths remain relative, and several records may share the file. The GUI provides viewing, not screenshot import/editing. CLI `--media` checks these files too.

For translated image alternatives, replace only the target side:

```json
{
  "selectedVariantId": "wide",
  "variants": [
    {"id":"wide", "label":"Full wording", "comment":"Two lines",
     "previewPath":"Translation/Images/sign-wide.png", "assetPath":"Translation/Images/sign-wide.png"},
    {"id":"short", "label":"Short wording",
     "previewPath":"Translation/Images/sign-short.png", "assetPath":"Translation/Images/sign-short.png"}
  ]
}
```

Only target images support alternatives; source and audio sides do not. Provide stable IDs and an explicit initial selection, and store the catalog in `Translation`. Browsing does not change the saved selection. The builder must use the current SDK:

```python
from translation_studio.core import Project, safe_path
project = Project(game_root)
side = project.asset_side("art", "texture.wall-sign", "ru")
if side is None:
    raise ValueError("Image translation is missing")
asset_path = safe_path(project.root, side.get("assetPath", side["previewPath"]))
# Validate and encode the selected asset for the game.
```

Do not read `variants[0]` or duplicate selection elsewhere. The NES example copies the chosen PNG and records variant ID/hash in its manifest. Test preview-without-selection, selection/save/external build, and rollback.

## Relations and custom buttons

Optional `relationsPath` points to a `{schemaVersion:1, groups:[...]}` catalog. Text groups use ordered refs plus explicit literals; audio groups use refs and optional pauses. Each needs at least two refs. A fragment may belong to multiple groups, and `partsByLanguage` may replace the order for a language. Missing translations remain visibly incomplete. Full examples and constraints are in [Relations](Relations.md).

Optional `actions` adds buttons. Use separate argument strings, a game-relative working directory, explicit `targetLanguage`, dataset IDs and completeness policy. Both action kinds require saved inputs. The script must accept the declared arguments and return 0 only after its own checks. Output decoding, trust, cancellation and the complete copyable action are documented in [BuildIntegration](BuildIntegration.md).

## Re-extraction and handoff

Keep the mapping between custom IDs and game bindings. Re-extraction must reconcile added/removed/changed records and preserve manual translations. Review source changes before updating `sourceRevision`. Do not edit author JSON concurrently with the user; external hash conflicts need reload/reconciliation, not blind replacement. Recovery is not a three-way merge.

Before handoff: validate with CLI, open GUI, change one record, save, build externally and confirm the new content in output. Move a copy of the whole game folder and repeat. Test configured media, variants and relations separately. Document whether checks covered files, an emulator, hardware or gameplay; those are different levels of evidence.

Upgrade app, CLI and SDK together before using new fields. Unknown schema versions are rejected. Recovery/profile/log storage is implementation-owned and described in [StorageDiagnostics](StorageDiagnostics.md); it is never builder input.
