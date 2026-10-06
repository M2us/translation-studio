# Source and portable distribution

## Public source boundary

The public project consists of `Source`, `Scripts`, `Tests`, `Assets`, `Examples`, `Docs` and the root README, changelog, contributor/agent instructions and repository settings. It is self-contained; it has no dependency on a personal parent workspace.

`Internal` retains private plans/history locally and is ignored. `Work`, `Builds`, `Data`, Python caches/environments and generated user-guide HTML are also ignored. Example `Work`/`Builds` directories are excluded. A Git ignore rule cannot remove an already tracked file; inspect tracked files before any future push.

```powershell
& ./Work/venv/Scripts/python.exe Scripts/verify_source.py
& ./Work/venv/Scripts/python.exe Scripts/export_source.py
```

The source audit checks English comments/docstrings, explanatory example metadata and the public file boundary; `Scripts/verify_docs.py` separately validates documentation links, schemas and the minimal integration example. The exporter writes `Builds/Source/Translation-Studio-Source.zip` plus its checksum using the explicit public-file selection, not a recursive copy of the workspace. This archive can seed a future repository without local work/history. It is not a substitute for reviewing a future `git diff --cached`.

No repository is initialized, remote configured, commit pushed or release published by these scripts. If preparing an existing repository, inspect `git status --short --ignored` and `git ls-files` as well; remove unintended tracked files from the index without deleting local originals.

## Build Windows binaries

Use the pinned environment from README:

```powershell
& ./Work/venv/Scripts/python.exe Scripts/build.py
& ./Work/venv/Scripts/python.exe Scripts/verify_package.py
& ./Work/venv/Scripts/python.exe Scripts/build.py --assemble-only --publish
& ./Work/venv/Scripts/python.exe Scripts/verify_archive.py
```

The first command stages a candidate under `Work/Package/TranslationStudio` using PyInstaller. The second checks actual EXEs on disposable examples. Only then publish locally. Ensure the installed application is closed and bundled examples contain no user edits before replacement. `Data` is preserved in the local folder but excluded from the ZIP; author edits inside bundled examples are not automatically merged by the publisher.

`--assemble-only` refreshes public docs/assets/SDK/examples; it does **not** rebuild executable code. `--gui-only` may reuse previous CLI/DemoBuilder binaries only when their code/dependencies have not changed. After shared reader, CLI or demo-builder changes, build all executables.

Outputs are the `Builds/Windows/Translation Studio` directory, `Translation-Studio-Windows-Portable.zip` and `Portable-SHA256.txt`. The directory includes a per-file SHA256SUMS manifest. Only the current output of each format is retained. Source ZIP and portable ZIP serve different purposes.

## Package contents

The portable app includes the windowed EXE and `_internal`, the console CLI/worker, current public docs and both local HTML user guides, UI assets, standalone examples with `Tools/DemoBuilder.exe`, the headless SDK and dependency notices. Private plans/history and machine reports never enter the package. Assembly refreshes the staged Docs directory so moved/removed private documents cannot survive from an older candidate.

`verify_archive.py` checks ZIP CRC, hashes, private-file exclusions and EXE workflows after extraction. It also checks a real portable `Data` profile in that disposable extraction.

The packager excludes an incompatible unversioned ICU DLL sometimes collected from an unrelated runtime; the tested Qt build needs the Windows ICU API. Keep the exclusion check and verify actual executables after dependency changes. Third-party license files and installed dependency versions are collected under `ThirdParty`.

## Future public release

The maintainer has assigned application version 1.0. The canonical version is `Source/translation_studio/__init__.py`; the CLI exposes it through `--version`, Qt records it as the application version, and builds embed it in Windows EXE file/product properties (numeric 1.0.0.0). The project uses the [MIT License](../LICENSE), copyright (c) 2026 M2us. Include the root license in both source and portable distributions; preserve third-party notices under their own terms. `schemaVersion: 1` remains the independent data-contract version.

Document supported Windows versions based on actual tests, retain dependency notices, run checks from a clean source copy and test the portable build on a clean machine. The current app is unsigned and has no installer. Upload source through Git and portable binaries/checksums as release assets; do not commit venvs, logs, drafts, game ROMs or generated binaries.
