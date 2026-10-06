# Translation Studio — agent instructions

Start with [README.md](README.md) and [Docs/AgentGuide.md](Docs/AgentGuide.md). This is a standalone Windows translation editor; do not assume a parent workspace or a particular game.

- English is primary for comments, public docs, explanatory example metadata and default diagnostics. Russian UI and [user docs](Docs/UserGuide.ru.md) are additional localization. Reply in the user's language. Preserve multilingual fixtures: they test Unicode behavior.
- Keep the application universal. Game-specific extraction, encodings, ROM offsets, flags and packing belong in game adapters. Games connect through `Translation/project.json`.
- Preserve stable IDs, source text, opaque `extensions` and numeric precision. GUI edits are limited to target text/notes and image `selectedVariantId`. Context, comments, screenshots and resource descriptions are read-only. Previewing an alternative is not selecting it.
- GUI and builders use the same author catalogs. Preserve user edits. Never modify `Original`/`Extracted` or install documentation examples into real games. Follow [storage rules](Docs/StorageDiagnostics.md).
- Read the relevant [architecture](Docs/Architecture.md), [format](Docs/ProjectFormat.md), [relations](Docs/Relations.md) and [build contract](Docs/BuildIntegration.md). Change schemas in `Source/translation_studio/schemas.py`, export them and update docs together.
- Update English docs, affected Russian user guidance and the existing `1.0` changelog section. Do not assign/increment releases without a maintainer request. `schemaVersion` is a separate data-format version.
- Run [Testing](Docs/Testing.md)'s required checks after code/format changes. Use disposable copies for saves/recovery/smoke tests. Audio tests require Windows audio output; report failures instead of silently skipping them.
- For distribution changes: build, verify candidate, publish locally and verify ZIP per [Distribution](Docs/Distribution.md). `--assemble-only` does not rebuild EXEs. Check the installed app is closed and bundled examples have no user edits before replacement; preserve `Data`.
- Keep private plans/reports in ignored `Internal`/`Work`. Public docs/packages must not depend on them. Preparing files does not authorize repository creation, pushing or public releases.
- No sub-agents unless explicitly requested by the user. [CLAUDE.md](CLAUDE.md) points to this shared instruction set.
