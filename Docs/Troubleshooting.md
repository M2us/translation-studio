# Troubleshooting

## Project does not open

Select the game root containing `Translation/project.json`, not a single TXT file. Validate with the CLI. Check schemaVersion, language keys, unique IDs, catalog paths and sourceRevision. Paths are relative to the game root. Do not blindly recompute a mismatched source hash: first compare the extracted source and preserve author translations.

A second editor may open read-only because another instance holds the game lock. Another app using the same personal profile is refused. Do not delete a live lock to force concurrent writes; close the owning instance or use the existing one.

## Changes or build result look old

Edits live in memory until Save. A builder reads only saved `Translation` catalogs. Re-selecting the active project intentionally does not reload it; use Reload to read external changes, handling unsaved edits first. A build action has a fixed targetLanguage regardless of the comparison column.

For image alternatives, arrows only browse. Click Use this variant and Save, then make the builder resolve `Project.asset_side()`. Do not build from the first variant or an old duplicate path/TXT.

## Save is blocked

Inspect the field's constraints and validation details. Null means untranslated; empty string is distinct and may be prohibited. Limits may count code points or encoded bytes, not visual glyphs. An external-change conflict requires reconciliation/reload. Copy your work before manual merging; recovery is not automatic three-way merge. File permissions or partial saves must not be reported as complete success.

## Media or relations fail

Supply PNG or integer PCM WAV previews, safe relative paths and available files. A stale preview may have been derived from a different asset hash. Full audio playback requires every part on that side; no source fallback is inserted. Unsupported devices/formats need correction, not silent skips. Relations are optional and require explicit valid references; identical text alone creates no relation.

## Garbled builder output

Set the action's `outputEncoding` to its actual stdout/stderr encoding. Supported values: UTF-8, UTF-8 with BOM, CP1251 and CP866. Normalize mixed child-tool output in the adapter. This is independent of game text encoding. Frozen Python builders should explicitly configure both streams as documented in [BuildIntegration](BuildIntegration.md).

The UTF-8 `.log` and raw `.output.bin` tails help diagnose byte errors. A decoding warning does not necessarily mean the command failed. Previously lost/replaced characters cannot be reconstructed from a damaged text log alone.

## Crash or a button stops responding

Use Open logs folder. Save `current.log`, or `previous.log` after one restart; another restart rotates it away. For build failures, also inspect the game's command logs. Application logs omit entered fields, but external command logs may include private output: review before sharing.

Report app/source revision or archive checksum, Windows version, the shortest reproduction, expected/actual behavior, UI language/theme and relevant logs. Prefer a sanitized synthetic project; no ROM is needed for a UI issue. A hard kill or power loss may leave no final crash reason. See [StorageDiagnostics](StorageDiagnostics.md).
