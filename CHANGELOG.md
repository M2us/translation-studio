# Changelog

## 1.0 - 2026-10-06

Initial release.

### Added

- MIT License with attribution to M2us, included in source and portable distributions.

- Universal Windows editor with text, audio and image tabs configured by each game's `Translation/project.json`.
- Stable custom IDs, multilingual author catalogs, opaque game extensions and source-integrity hashes shared with a headless CLI and SDK.
- Read-only originals, editable target text/notes, search, sorting, filters and per-record validation.
- Character/byte/line limits, required tokens, literal allowed/forbidden character sets and readable field-level diagnostics.
- Optional text/audio relations, shared fragments, context screenshots and selectable translated-image alternatives.
- PNG comparison, PCM WAV playback and complete audio sequences.
- Project-defined build/validation commands, output encoding selection and cancellation of Windows process trees.
- Atomic per-file saving, external-change detection, editor locking, one recovery draft and one previous save.
- Bounded action/crash diagnostics without entered field content, plus portable preferences.
- Light/dark themes, English and Russian UI and offline user guides, custom SVG/ICO application icon and portable ZIP.
- English developer/API/integration/troubleshooting documentation, shared Codex/Claude Code instructions and a public-source audit/export tool.

### Known limitations

- Synthetic examples do not establish real-game compatibility. Adapters validate game encodings, fonts, pointers and playable output.
- Atomicity applies to individual catalogs, not a multi-file transaction; external edits are not automatically merged.
- Previews are PNG and integer PCM WAV; no media editor, installer or code signature is provided.
