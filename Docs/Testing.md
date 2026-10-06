# Testing and verification

Run from the repository root using the configured Python 3.12 environment. Tests use disposable copies, including paths with spaces and Cyrillic characters. Cyrillic strings in tests intentionally cover Unicode and localization; they are not untranslated developer instructions.

## Required checks after code or format changes

```powershell
& ./Work/venv/Scripts/python.exe -m pytest Tests -q -p no:cacheprovider
& ./Work/venv/Scripts/python.exe Source/studio_cli.py validate 'Examples/Synthetic NES' --language ru --media --strict-relations
& ./Work/venv/Scripts/python.exe Source/studio_cli.py validate 'Examples/Synthetic Sega' --language ru --complete
& ./Work/venv/Scripts/python.exe Scripts/render_guide.py
& ./Work/venv/Scripts/python.exe Scripts/verify_docs.py
& ./Work/venv/Scripts/python.exe Scripts/verify_source.py
```

Audio tests require an available Windows audio output and use QAudioSink. Do not mask an unavailable device or a failure by silently skipping coverage. GUI tests use Qt offscreen with registered system fonts; native EXE verification remains separate.

## Coverage map

| Area | Tests |
| --- | --- |
| JSON precision, source hashes, constraints, language keys, paths, locks, relations | `Tests/test_contract.py` |
| Models, filtering, cross-fragment views, localization, PCM queue, larger catalogs | `Tests/test_gui.py` |
| Recovery slots, interrupted saves, log limits/privacy, native fault reporting, preferences | `Tests/test_history_diagnostics.py` |
| Worker streams, UTF-8/CP1251/CP866, process-tree cancellation, external builds | `Tests/test_processes.py` |
| Partial saves, absent translations, action validation, cross-tab relations | `Tests/test_regressions.py` |
| Character rules, screenshots, variants, mixed snapshots, help language, close/reopen behavior | `Tests/test_usability.py` |
| English defaults with explicit Russian CLI/SDK diagnostics | `Tests/test_language_defaults.py` |

Tests simulate write failures and an isolated native crash. They do not simulate physical disk loss or guarantee persistence after power failure. Audio output checks do not assess voice quality by ear. Full test counts and timings vary; run the suite rather than relying on a historical count.

## Visual and distribution checks

`Scripts/capture_design.py` captures this app on copied examples and an isolated profile. Inspect light/dark themes, minimum 1060×750 layout, relation panels, context images and alternatives. Check long names and DPI scaling when changing layout. Public README screenshots use English and a neutral display path; no source paths are changed to obtain them.

For executable changes, follow [Distribution](Distribution.md): build, verify candidate, assemble/publish and verify the extracted ZIP. `verify_package.py` checks both synthetic adapters using copied projects and separate profiles, changes text, saves, selects an image variant, runs a builder, and verifies result bytes and bounded logs. It deliberately tests non-ASCII paths. `--smoke-test` is destructive to its input copy; never point it at a user project.

Machine-specific reports and screenshots belong in ignored `Work/QA`; private history belongs in ignored `Internal`. Neither is a public runtime dependency.

## Limits

The tested platform is Windows x64. The synthetic NES/Sega adapters do not establish compatibility with real ROMs. A different Windows version, clean installation without development libraries, long-running sessions and very large media require their own verification. The app is unsigned and has no installer. Game encodings, fonts, pointers and final playable patches remain adapter responsibilities.
