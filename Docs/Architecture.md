# Architecture

## Stack and module map

The tested environment is Windows x64, Python 3.12, PySide6 6.11.2, jsonschema 4.26.0 and PyInstaller 6.22.3. Dependency files under `Source` are authoritative. Application release numbers and the data contract's `schemaVersion` are separate.

| Module | Responsibility |
| --- | --- |
| `Source/app.py` | Desktop entry point, diagnostics startup, explicit smoke-test mode |
| `Source/studio_cli.py` | Headless CLI and packaged worker entry point |
| `translation_studio/core.py` | JSON reader/writer, project loading, constraints, source hashes, locks, media paths, relations, save/recovery; no Qt |
| `schemas.py` | Authoritative schemas; exports `Docs/Schemas` |
| `cli.py` | Validation, source hashing, schema export |
| `gui.py` | Main window, background Loader, projects, profile, actions, recovery and help |
| `views.py` | Table models, filtering, record details/editors, relations and image selection |
| `rule_display.py` | Human-readable rule descriptions; validation itself stays in core |
| `media.py` | PNG views, screenshot thumbnails/dialogs, PCM audio and queues |
| `processes.py` | Action validation, worker IPC, Windows Job Objects, output decoding and cancellation |
| `settings.py` | Portable profile and application paths |
| `bookmarks.py` | Personal project keys and defensive normalization of profile bookmarks; no Qt or game-catalog writes |
| `diagnostics.py` | Bounded application logs, safe events and exception/native-fault handling |
| `theme.py` | Shared semantic colors, styles and SVG UI icons |
| `i18n.py` | English/Russian message translations and project labels |
| `smoke.py` | Explicit packaged-install verification on disposable examples |

## Data flow

```text
Game extraction -> Translation/project.json + author catalogs + media
                                      |
                           Project (shared reader)
                           /                     \
                 Desktop editor              Game adapter/CLI
                 in-memory edits             saved catalogs only
                       |                           |
                 validate + save             game validation/encoding
                       |                           |
                 same catalogs               Work -> Builds
```

The application has no built-in ROM formats. The two example adapters intentionally live outside the generic editor. Project `extensions` remain opaque, including large integers and Decimal values. Source text and stable IDs are protected independently of the byte hash used to detect external edits.

`MainWindow` loads a project on a `QThread`. `RecordModel` uses stable IDs despite filtering and sorting. The table is read-only; edits are made in the detail panel. One project is loaded at a time. The recent list retains up to 15 paths, scrolls when necessary and has a close/remove icon per row. Re-selecting the active project is a no-op; Reload explicitly reads disk again.

Image browsing is separate from `selectedVariantId`. The GUI and adapters share `Project.asset_side()` to resolve the selected resource. Context screenshots and resource descriptions remain read-only. Related text is derived from the current model, including unsaved edits; it is not stored as a second editable translation.

## Persistence and concurrency

Vertical table headers map proxy rows back to catalog rows, preserving displayed numbers under sorting/filtering. Bookmark identity uses the project folder, tab and stable entry ID, never a row number. `MainWindow` saves bookmark changes through the personal profile, maintains cross-tab navigation and preserves unavailable notes; `RecordPage` provides a flag and note editor independently of author translation notes. Bookmarks require no project schema changes or game integration work. See [StorageDiagnostics](StorageDiagnostics.md) for profile format and [UserGuide](UserGuide.md) for navigation behavior.

Saving validates all dirty catalogs before writes. Each file is written through a temporary file, flushed and atomically replaced after an external-change check. This is not a cross-file transaction. A failure after some replacements reports those successes and keeps a recovery draft for the intended complete state. The previous snapshot represents the state before the whole attempt. See [StorageDiagnostics](StorageDiagnostics.md).

An editor lock makes a second editor read-only. External tools that ignore locking cannot be made safe by the GUI; coordinate edits rather than promising automatic merging. A builder reads saved `Translation` catalogs, never the editor's draft.

## Processes and media

An action runs as an argument vector without shell concatenation. The parent creates a Windows Job Object; the worker waits for its launch command until attached to that job. Cancellation terminates the process tree. The packaged worker uses the console CLI executable, because a windowed EXE does not provide usable standard streams. Action execution disables editing and project switching.

Stdout/stderr are decoded incrementally using the action's declared encoding. The readable log is UTF-8; a companion file retains a bounded raw byte tail. Invalid bytes produce a warning and escaped bytes, not silent replacement characters. Game-text encoding is unrelated to log encoding.

Audio uses `QAudioSink` for integer PCM WAV. The current implementation polls sink state every 20 ms because the tested PySide6 binding did not reliably convert the state signal. A WAV is loaded into memory for playback. PNG views support zoom/pan; linked image views synchronize their transforms. These are comparison tools, not media editors or seamless audio renderers.

## Localization and documentation

English is the default UI/CLI/SDK diagnostic language. A saved or imported UI preference takes precedence. The `TEXT` message tables currently retain `(Russian, English)` tuple order for compatibility; callers use keys and `tr()`, not tuple indexes. Russian literals in localization tables and Unicode fixtures are intentional. New explanatory comments and public docs use English.

`Docs/UserGuide.md` is the English source and `Docs/UserGuide.ru.md` the Russian translation. `Scripts/render_guide.py` builds local HTML; the Help button chooses the current UI language. Generated HTML is excluded from Git and included in the portable build. Public technical docs remain ordinary Markdown.

See [Testing](Testing.md), [Distribution](Distribution.md), [API](API.md) and [AgentGuide](AgentGuide.md) for commands and workflows.
