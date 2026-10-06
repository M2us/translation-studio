# Contributing

Use English for source comments, public docs, PR descriptions and default diagnostics. Keep Russian UI translations and the Russian user guide in sync. Multilingual fixture text is intentional test data.

## Setup

Use Windows x64 and Python 3.12; follow [README](README.md). `Source/requirements-lock.txt` pins the tested environment; `requirements.txt` contains runtime dependencies; `requirements-dev.txt` adds development tools. Avoid unrelated dependency updates.

Read [Architecture](Docs/Architecture.md) and the affected contract. Run [Testing](Docs/Testing.md)'s checks. For packaging, follow [Distribution](Docs/Distribution.md). Application tests do not prove real-ROM playability.

## Scope

- Keep game-specific extraction, encoding, packing and validation in game adapters. Preserve opaque `extensions`.
- Preserve author edits and source data. Use disposable copies of `Examples` for saves and smoke verification.
- Cover data-loss risks, contract changes and behavioral bugs with meaningful regression checks. Inspect both themes and the minimum window size for layout changes.
- Update each fact in one authoritative document and link to it elsewhere. Add results to the existing `1.0` changelog section; create a new version only when explicitly requested by the maintainer.
- Exclude profiles, logs, recovery files, builds, environments, private plans and ROMs from source control. Run the source audit in [Distribution](Docs/Distribution.md).

PR descriptions should explain the user-visible problem, final behavior, verification and limits. Use synthetic public reproductions. The current application version is 1.0. The project uses the [MIT License](LICENSE), copyright (c) 2026 M2us. Preserve copyright/license notices and third-party license files; do not invent a repository URL.
