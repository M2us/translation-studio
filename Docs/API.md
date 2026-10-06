# CLI and Python API

## CLI

Source entry: `python Source/studio_cli.py`. Portable entry: `TranslationStudio.Cli.exe`. These use the headless reader and do not import Qt.

```powershell
& './TranslationStudio.Cli.exe' validate 'C:/Games/My Game' --language ru --complete
& './TranslationStudio.Cli.exe' validate 'C:/Games/My Game' --language ru --media --strict-relations
& './TranslationStudio.Cli.exe' --ui-language ru validate 'C:/Games/My Game'
& './TranslationStudio.Cli.exe' source-hash 'C:/Games/My Game/Translation/Text/main.json'
& './TranslationStudio.Cli.exe' export-schemas 'C:/Games/My Game/Docs/StudioSchemas'
```

Global `--ui-language en|ru` must precede the subcommand. English is the default diagnostic language; it does not select a translation language. `--language` selects a configured target, or validation covers all targets if omitted.

`validate` writes UTF-8 JSON with `ok`, `project` (when available), and `issues`. Issues expose `code`, `severity`, `tabId`, `entryId`, `message` and `details`. Exit codes: 0 for no errors (warnings may exist), 1 for contract/validation failures, 2 for argument errors or I/O/type failures not expressed as ordinary issues. Automations should use codes/details, not parse translated prose.

`--complete` rejects null text. Combined with `--media`, it also requires the checked media sides. Without completeness, missing optional target media is allowed. `--media` checks preview paths, WAV readability, PNG signatures, screenshots and every image alternative. PNG decoding remains a GUI check. Optional relation errors are warnings unless `--strict-relations` is set.

`source-hash` prints the computed hash and never changes a file. Use it after reviewing extracted source, not to suppress unexplained source changes. `export-schemas` writes Draft 2020-12 schemas.

## SDK installation

The portable package includes `SDK/translation_studio` and `SDK/requirements.txt`. Copy the complete SDK into a project's tools folder or pin a documented shared path. For source development, add `Source` to the builder's import path. Python 3.12 and jsonschema suffice; Qt is not needed. Pin the SDK files/hashes and schema version while no release version exists.

```python
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "Tools/TranslationStudioSdk"))
from translation_studio.core import Project, safe_path

project = Project(root)  # Read-only reader; does not acquire an editor lock.
errors = [i for i in project.issues(language="ru", complete=True)
          if i.severity == "error"]
if errors:
    raise SystemExit("\n".join(i.message() for i in errors))
project.check_external()
for entry in project.documents["text"]["entries"]:
    text = entry["texts"]["ru"]
    binding = entry.get("extensions", {}).get("game", {}).get("binding", {})
    # Validate game encoding/budgets and pack this text using the binding.
project.check_external()  # Check again before publishing output.
```

## Reader surface

| Member | Purpose |
| --- | --- |
| `Project(root, editable=False)` | Load config/catalogs. Invalid config raises `StudioError`; broken tabs are isolated. Editable mode requests a lock. |
| `config`, `tabs`, `documents`, `entries`, `paths` | Loaded config and indexes; documents/entries are indexed by **tab ID**, not dataset ID. |
| `tab_errors`, `relation_issues` | Catalog failures and independent optional-relation diagnostics |
| `issues(tab_ids=None, language=None, complete=False)` | Standard catalog/text checks, including tab errors; not full game/media validation |
| `check_external()` | Detect changed input file bytes against load-time hashes |
| `asset_side(tab_id, entry_id, language)` | Saved selected image variant, ordinary side or None |
| `media_side(tab_id, entry_id, language, variant_id=None)` | Resolve preview path and stale-preview flag; optional variant is for comparison |
| `audio_queue(tab_id, entry_id, language, group_id=None)` | Resolve and validate the requested PCM playback queue |
| `parts(group_id, language)`, `text_sequence(group_id, language)` | Resolve optional relation parts/text from current model |
| `close()` | Release editor resources/lock when using editable mode |

For media builders, resolve the selected side with `asset_side`, then read `safe_path(project.root, side.get("assetPath", side["previewPath"]))`. Validate the actual game resource separately; `issues()` alone does not do that. Do not use the first variant or a duplicated selection file.

`Issue.message(language="en")` and `Issue.as_dict(language="en")` default to English. `StudioError.issue` supplies its structured issue; `str(error)` is English. `safe_path`, `read_json`, `json_bytes`, `atomic_write` and `source_revision` provide shared path, precise-JSON and hashing behavior. Standard-library `json` with float conversion is not a drop-in replacement for exact Decimal round trips.

## Editable integrations

The desktop uses `set_text`, `set_note`, `set_variant`, `save`, `recovery` and `restore`. Changes require a writable project and enforce immutable fields, source integrity and external-change checks. Read [StorageDiagnostics](StorageDiagnostics.md) and inspect current method signatures before building another writer; these internal mutation methods are not a separately versioned remote/plugin API.

A game builder normally uses read-only mode. Never consume recovery files as author input or bypass validation by reading an old derived TXT after a catalog failure.

## Application version

Run `TranslationStudio.Cli.exe --version` (or `python Source/studio_cli.py --version`) to print `Translation Studio 1.0`. This is the application version; `schemaVersion: 1` independently identifies the catalog contract.
