# Optional fragment relations

Relations are project-supplied context, not inferred from identical strings, adjacent rows, filenames or game indexes. They do not require changes to the generic editor.

## User behavior

Text fragments remain independent records with their own IDs, translations and constraints. Selecting a member shows every containing sequence. The full original/target sentence is read-only and derived from current data, including unsaved edits. Links identify the member records and navigate to their tabs. Literal separators have no fake record IDs.

For example, `id1` may supply "Maybe" and `id2` "something happened", joined by a literal ", ". Another sentence may reuse `id1`; a separate identical "Maybe" with `id3` remains independent. Editing `id1` updates every derived sentence using it. Combined sentences are never a second author-owned translation.

Audio relations play files in order with optional pauses. Another play request, Stop, a tab/language/project change or reload cancels the queue. Missing, corrupt or unsupported parts prevent complete playback on that side with a diagnostic. Parts are not silently skipped or replaced with source audio. Available individual files and the other complete side remain usable. Playback does not promise seamless mixing or export a combined file.

## Catalog

`project.json` optionally declares `relationsPath`, for example `Translation/Catalogs/relations.json`. Without it, ordinary tabs work and relation controls are absent. The catalog requires `schemaVersion: 1` and `groups` (possibly empty); `extensions` is optional.

A group requires `id`, `type`, `label`, `parts`. Optional fields are `labels`, `comment`, `partsByLanguage`, `extensions`. IDs are unique within the relation catalog. Type is `textSequence` or `audioSequence`. Comment defaults to empty; localized labels use English/Russian UI keys with fallback to `label`.

```json
{
  "id": "sentence.discovery",
  "type": "textSequence",
  "label": "Discovery line",
  "comment": "Two independently stored fragments of the same sentence.",
  "parts": [
    {"ref": {"tabId": "text", "entryId": "id1"}},
    {"literal": ", "},
    {"ref": {"tabId": "text", "entryId": "id2"}}
  ]
}
```

Create the referenced records before using this group. A text part contains exactly a `ref` or `literal`. A ref contains `tabId` and `entryId`, referencing a text tab, including another text tab. Literals are display-only strings: spaces, punctuation or newlines. There is no automatic inserted space and no change to the stored fragments.

An audio part contains `ref` and optional non-negative integer `pauseAfterMs` (default 0). It must reference an audio tab; literals are forbidden. Pauses occur before the following part; the last pause is ignored.

Every sequence needs at least two ref parts. References may repeat; literals do not count as resource parts. Groups cannot reference groups, so there are no nested sequences/cycles.

`partsByLanguage` optionally maps declared source/target language codes to complete replacement arrays. Without an override, use `parts`. All arrays obey the same type/reference rules. Membership lookup includes default and all language arrays, even when the currently viewed language does not use a particular member.

Values resolve through `texts[language]` or `assets[language]`, with no remapping of IDs between languages. Null text is explicitly marked missing with its ID and makes the preview incomplete. An intentionally empty string is not missing. Resource limits still apply individually; combined budgets belong in the game adapter.

## Validation and ownership

Validate the envelope, group IDs/types, references, language keys and pause values. An invalid optional catalog/group yields relation diagnostics and does not prevent independent valid text catalogs from being edited. The CLI treats relation issues as warnings unless `--strict-relations` is requested.

The project author maintains relations. Saving translations does not rewrite their catalog. Relations are excluded from text `sourceRevision`; aggregate previews are recalculated from current data. They are not implicit instructions for the game's binary packer.

See [IntegrationGuide](IntegrationGuide.md) and [complete examples](Examples/relations.example.json).
