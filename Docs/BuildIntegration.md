# Saving and build integration

## One author-owned source

Both the editor and command-line builder consume the same saved catalogs under `Translation`. Extracted source stays in `Original`/`Extracted`. TXT, encoded strings and binary tables are generated into `Work`; do not maintain a second independently editable translation.

Saving validates all modified catalogs, confirms source/immutable fields and compares disk hashes before writing. Each file uses a temporary file, flush/fsync and atomic replacement. Only successful replacement counts as saved. Multi-file failure reports successes and retains the remaining intended changes. Cross-file transactions and automatic merging are not supported. See [StorageDiagnostics](StorageDiagnostics.md) for draft/previous ordering.

The editor lock protects cooperating editor instances. Arbitrary external editors can ignore it; coordinate work and respond to conflicts instead of overwriting disk. A GUI build cannot run with unfinished/failed saving. The external builder must validate its own inputs too.

## Action fields

`project.json` may contain `actions`. Opening a project never runs them.

| Field | Meaning |
| --- | --- |
| `id`, `label` | Stable key and button text |
| `labels` | Optional `en`/`ru` button labels; fallback to `label` |
| `kind` | `build` or `validate` |
| `executable` | Program name in PATH or a project-relative executable path |
| `arguments` | Array of individual strings, not a shell command |
| `workingDirectory` | Game-relative directory, usually `.` |
| `outputEncoding` | Optional `utf-8` (default), `utf-8-sig`, `cp1251` or `cp866` |
| `requiresSaved` | Required true for both action kinds in contract 1 |
| `requiresComplete` | Required policy for untranslated text in the selected datasets |
| `datasetIds` | Required text-dataset IDs; `[]` for media-only commands |
| `targetLanguage` | Required configured target language for action validation |
| `outputs` | Optional relative result files/directories to open after success |

Unknown datasets or target languages are configuration errors. Before launch, the GUI saves edits through the normal save path and validates action datasets for the action language. Null targets are blocked when completeness is required; ordinary constraints still apply. This does not require completing other languages. Media completeness and game-specific validity must be checked by the builder.

Each action has a fixed target language. Switching the comparison column does not change its command. The script must explicitly accept the supplied arguments or select that language itself; the GUI does not inject hidden language arguments. There is no string-template expansion or execution of translated text.

```json
{
  "id": "build-ru", "label": "Rebuild",
  "labels": {"en": "Rebuild", "ru": "Пересобрать"},
  "kind": "build", "executable": "python",
  "arguments": ["Scripts/build.py", "--language", "ru"],
  "workingDirectory": ".", "requiresSaved": true,
  "requiresComplete": true, "datasetIds": ["main"],
  "targetLanguage": "ru", "outputs": ["Builds/Patch"]
}
```

Use a game script for complex sequences. Do not embed quoting in each argument or assume a `.cmd`/`.bat` file will run without an explicit interpreter. The GUI's personal Python setting may point to an installed interpreter; portable project JSON must not contain a developer's absolute machine path.

On the first button launch the app displays executable, arguments and working directory and asks for trust. Trust is keyed by project ID, path and action-list hash in the personal profile. Changed commands require new trust. Actions are ordinary local programs, not sandboxed plugins.

## Execution, output and cancellation

Processes launch without shell concatenation. The worker belongs to a Windows Job Object so cancellation terminates descendants. One action runs at a time; editing, saving and project switching are blocked during it. The UI displays actual tool output rather than an invented percentage.

Exit 0 means command success, not proof of playability. Builders should generate/check in `Work` and publish to `Builds` only after validation, so cancellation cannot replace a known good build with incomplete output. Input hashes are compared before/after; external changes during execution produce a warning that the result may not match current translations.

`outputEncoding` describes stdout/stderr, **not the game's text encoding**. Normalize mixed tool output in your adapter. The app does not guess between legacy encodings. Invalid bytes cause a warning and escaped byte display, with a bounded raw `.output.bin` tail retained alongside the UTF-8 log. Decoding warnings do not alter the process exit code.

Frozen Python tools may ignore environment encoding settings. Configure both streams explicitly:

```python
import sys
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
```

Logs retain only two bounded command runs; do not rely on a permanent full build transcript. Details and privacy boundaries are in [StorageDiagnostics](StorageDiagnostics.md).

## Two validation layers

The shared reader/CLI validates IDs, language keys, sourceRevision, paths, JSON and generic constraints. It preserves game extensions without interpretation. A builder in another language must implement equivalent behavior and validate against fixtures; the Python SDK is the reference implementation.

The game's validator handles encoding tables, tags, glyph coverage, font width, binary budgets, offsets/pointers and packaging after conversion. It is mandatory in the external build even if no GUI button is configured. Structured attachment of arbitrary game diagnostics to editor cells is not currently a general protocol.

Document confirmed constraints and verification scope in the game project. Optional buttons do not replace the external build path. See [IntegrationGuide](IntegrationGuide.md) for setup and [API](API.md) for reader calls.
