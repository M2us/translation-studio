# Contract examples

These JSON files illustrate a synthetic **Example Game**. They are not an installed game integration. Complete runnable projects, including generated PNG/WAV resources and adapters, are in the repository's `Examples` directory.

Map `project.example.json` to `Translation/project.json`, `text.example.json` to `Translation/Text/main.json`, and the media/relation examples to their configured catalog paths. Documentation-only examples do not supply media binaries or an executable builder; use the complete synthetic projects for end-to-end testing.

Text entries demonstrate stable custom UUIDs, English/Russian/German values, per-language constraints, translator notes and opaque game metadata. Explanatory labels/context/comments are English. Russian values under `texts.ru`, `notes.ru` and `labels.ru` are intentional translated content. `sourceRevision` is computed from IDs and original text; target changes and formatting do not affect it.

The nested `extensions.game` binding and flags are examples for an adapter, not built-in game fields. The large integer demonstrates exact preservation. The build action targets Russian and does not require completing German.

The first text record includes a PNG screenshot reference and an illustrative `^~` character ban. This has no special relationship to Russian; the project decides supported characters. Image data demonstrates standard/compact target variants with explicit `selectedVariantId`. Builders use `Project.asset_side()` to read the saved choice.

Relations demonstrate a shared text fragment, identical text under another ID, language-specific order, a complete audio queue and a missing target part. See [Relations](../Relations.md). Projects without optional relations or comments are also valid.

For actual integration use [IntegrationGuide](../IntegrationGuide.md) and [ProjectFormat](../ProjectFormat.md). The portable distribution supplies `Tools/DemoBuilder.exe` in each complete example; from source use the Python adapter with `--sdk`.
