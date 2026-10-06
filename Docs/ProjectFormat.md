# Project format

This describes implemented **schemaVersion 1**. The authoritative machine schemas are in [Schemas](Schemas/), generated from `Source/translation_studio/schemas.py`. Start with the copyable [IntegrationGuide](IntegrationGuide.md).

## Ownership and layout

```text
Game/
  Original/                 immutable game inputs
  Extracted/                reference extraction
  Translation/
    project.json            entry point
    Text/main.json          original and translated text
    Catalogs/               optional media/relations catalogs
    Audio/ Images/ Context/ author resources and screenshots
  Scripts/                  game-specific adapter and builder
  Work/                     derived/intermediate files
  Builds/                   checked output
```

Only `Translation/project.json` has a fixed location. A project may split text into several catalogs/tabs. Configuration and author data live with the game, not in an application database. Builders read the same author catalogs as the editor.

JSON uses UTF-8 without BOM. Saves use two-space indentation, unescaped Unicode and one final LF. Text, whitespace, punctuation, tags and Unicode normalization are not silently changed. Numeric values in `extensions` must retain precision; whole-file formatting need not be byte-identical.

## Shared rules

- Document roots are objects with `schemaVersion: 1`. Unsupported versions, duplicate JSON keys and unknown standard fields are rejected.
- IDs are non-empty strings compared exactly. Record IDs are unique within their dataset/catalog; text identity is `(datasetId, id)`. Tab, action and relation-group IDs are unique in their respective collections.
- Generate a custom ID once, preferably a UUID. Preserve it across edits, reordering and extraction. Identical strings may have distinct IDs. Game indexes/offsets belong in `extensions`, not in the identity algorithm.
- Array order determines initial display/file order. UI sorting does not reorder source identity.
- Paths are relative to the **game root**, even from nested JSON, and use `/`. Reject absolute/UNC paths, URLs, traversal outside the root and escapes through symlinks/junctions. `workingDirectory: "."` is allowed.
- Writable text catalogs and image catalogs containing variants belong inside `Translation`. `Original`/`Extracted` are protected. Build outputs cannot replace configuration or catalogs.
- `labels` is an optional map with `en`/`ru` UI-language keys and non-empty strings. It falls back to the required `label`. It does not translate game data.

## Project configuration

Required fields: `schemaVersion`, `projectId`, `name`, `sourceLanguage`, `targetLanguages`, `tabs`. The source is a non-empty language code. Targets are a non-empty, unique array excluding the source. The first target is initially selected. UI language is independent and stored in the personal profile.

Optional fields: `actions` (default `[]`), `relationsPath` and opaque `extensions`. Without `relationsPath`, ordinary tabs still work and relation UI is absent. Copies with the same project ID in different folders remain separate projects.

Every tab requires `id`, `type`, `label`; `labels` is optional. Types are `text`, `audio`, `images`. Text tabs additionally require `datasetId` and `catalogPath`; `defaultsByLanguage` is optional. Media tabs require `catalogPath`. Text dataset IDs are distinct; two tabs must not write the same catalog. Catalog kind, source and declared languages must agree with configuration.

`defaultsByLanguage` contains rule objects by target language. Omitting a language uses ordinary defaults. Specify shared rules explicitly for each language.

## Text catalog and records

Catalog requirements: `schemaVersion`, `datasetId`, `sourceLanguage`, `languages`, `sourceRevision`, `entries`; optional `extensions`. `languages` contains the source and all configured targets without duplicates.

| Record field | Meaning |
| --- | --- |
| `id` | Required stable custom ID |
| `texts` | Required map containing exactly every declared language |
| `context`, `group` | Optional context and grouping strings |
| `comment` | Optional shared explanation, empty by default |
| `notes` | Optional translator notes keyed only by target languages |
| `constraintsByLanguage` | Optional per-record target-language rules |
| `screenshots` | Optional PNG context references |
| `extensions` | Optional opaque game metadata |

Source text is always a string. A target is a string or `null`: null means untranslated, while `""` means intentionally empty and requires `allowEmpty`. The string `"null"` is ordinary text.

The GUI changes target text and target notes. It preserves source, IDs, other untouched languages, context, comments, rules, screenshots and extensions. `comment` is a shared read-only explanation (location, speaker, provenance); `notes` is a translator's editable language-specific note. Neither is automatically translated when UI language changes. Null is not a valid comment.

## Extensions and source integrity

`extensions` is an object for namespaced game metadata, for example:

```json
{"extensions":{"game":{"binding":{"table":"dialog","index":42,"offset":8192},"flags":{"speaker":3}}}}
```

Values may contain arbitrary valid nested JSON, large integers and decimals. The app preserves but does not execute or interpret them. Adding game metadata needs no editor release; adding a new standard field/type requires supported schemas and implementation.

`sourceRevision` is SHA-256 of the source projection. It excludes translations, comments, notes, relations and extensions. Algorithm:

1. Encode `sourceLanguage` as UTF-8.
2. Sort entries by the UTF-8 bytes of their `id`.
3. Append each entry's UTF-8 ID and UTF-8 source text.
4. Prefix **each** string (including language) with its byte length as unsigned 32-bit big-endian; reject longer values.
5. Hash the combined bytes and store 64 lowercase hex digits. No BOM, newline or normalization is added.

A mismatch prevents normal use of the affected dataset until its source is reviewed. The GUI does not silently recalculate it. Re-extraction must preserve custom IDs, identify changed/added/removed source entries and update the hash only after reconciliation. This is separate from disk-byte hashes used to detect concurrent external edits.

## Text constraints

A record rule replaces the same field in the tab defaults; absent fields inherit. Default `allowEmpty` is false, numeric limits are absent and severity is `error`.

| Field | Rule |
| --- | --- |
| `allowEmpty` | Allow an intentionally empty target string |
| `maxCodePoints` | Unicode code points, including spaces, tags and line breaks; null disables |
| `maxLines` | `1 +` non-overlapping occurrences of `lineBreakToken`; null disables |
| `lineBreakToken` | Non-empty token, default newline `\n` |
| `byteLimit` | Object with `maxBytes`, `encoding`, `terminatorBytes`; strict encoded bytes plus declared terminator |
| `requiredTokens` | Array of `{token,count}`; exact non-overlapping occurrence counts |
| `allowedCharacters` | Literal set of allowed code points; null disables inheritance |
| `forbiddenCharacters` | Literal set of forbidden code points; empty string disables inheritance |
| `severity` | Rule-name map to `error`/`warning`; unspecified rules are errors |

Limits/counts are non-negative integers. Required tokens are non-empty and unique; the array replaces inheritance as a whole. `byteLimit` is replaced as a whole and supports `utf-8` and `utf-16le`. Unknown encodings are unsupported; do not add a BOM or terminator beyond the declared count. See schemas for exact nullable fields.

Character sets are **not regexes or ranges**: `"A-Z"` contains three literal characters. Whitelists must explicitly include spaces, newlines, combining marks and tag characters. An empty whitelist permits only an empty string, subject to `allowEmpty`. When both sets are supplied, a character must be allowed and not forbidden. No case folding or normalization occurs.

For example, `forbiddenCharacters: "^~"` rejects caret and tilde. This is an illustrative per-record rule, not a universal game restriction. A Cyrillic-specific test may use the letter yo (`U+0451`/`U+0401`) to prove Unicode behavior; the editor has no built-in restriction on that letter or any language.

Null targets skip content checks unless completeness is requested. Errors block saving/building; warnings do not. Code points, graphemes, UTF-16 units, game bytes and rendered width are different measures. Game encodings, font coverage, tags, alignment and pointer budgets require adapter validation after conversion.

## Context screenshots

`screenshots` is an optional array of `{path, caption?}` with a required game-relative PNG path and optional caption defaulting to empty. An empty array hides the block. Screenshots belong to the record's context, not one translation. They are read-only and may be shared across records.

The game project supplies/replaces files. The GUI shows thumbnails and an enlarged view without copying resources. A missing/corrupt image does not block independent text editing; unsafe paths invalidate the affected catalog. CLI `--media` checks existence and PNG signature; GUI decoding is an additional check. Screenshots are outside the source hash and preserved on save.

## Media catalogs

Required: `schemaVersion`, `kind` (`audio`/`images`), `sourceLanguage`, `languages`, `entries`; optional `extensions`. Each entry requires `id`, `label`, `assets`; optional `context`, `comment`, `extensions`.

`assets` contains every declared language. Source is a side object; a target is a side or null. A side requires `previewPath`; optional `assetPath` identifies the real build resource. If absent, the preview itself is the resource. Optional `derivedFromSha256` requires `assetPath` and hashes its bytes when the preview was generated. A missing/changed asset marks the preview stale.

Supported previews: PNG and WAV with integer PCM at 8/16/24/32 bits. The adapter converts game-specific formats. Target null never falls back silently to source. The GUI does not edit media files or side descriptions.

## Translated image alternatives

Only a target side in an `images` catalog may instead contain `{selectedVariantId, variants}`. Source images and audio remain ordinary sides. `variants` is non-empty; each member requires a unique stable `id`, non-empty `label` and `previewPath`, plus optional `comment`, `assetPath`, `derivedFromSha256`. The selected ID must explicitly reference a member; no implicit first choice exists.

Array order controls browsing. Browsing does not dirty the project; choosing changes only `selectedVariantId`, and Save persists it. Choices are independent per target language and participate in draft/previous snapshots. Descriptions and all media binaries remain unchanged.

Builders must use `Project.asset_side(tab_id, entry_id, language)` to resolve the saved choice. `media_side(..., variant_id=None)` resolves preview and staleness; the optional ID supports previewing an alternative. Never build from `variants[0]` or a duplicated selection in a second config. CLI `--media` checks all alternatives, not only the selected one.

## Compatibility

Old single-side catalogs remain valid. New optional fields are supported by the current contract-1 reader, but older strict readers can reject them. Update app, CLI and SDK together; do not copy `core.py` without its matching schemas and translations. Future schema versions are rejected until supported. Game-specific `extensions` do not change schemaVersion.
