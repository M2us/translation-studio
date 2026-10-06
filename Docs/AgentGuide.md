# Guide for AI agents

Read [AGENTS.md](../AGENTS.md), [README](../README.md) and this page before editing or answering implementation-specific questions. Claude Code enters through [CLAUDE.md](../CLAUDE.md). The same rules apply to other agents. Public documentation is English; answer the human in their language.

## Choose the right scope

If working on the editor, read [Architecture](Architecture.md), inspect the affected module and run [Testing](Testing.md). If connecting a game, follow [IntegrationGuide](IntegrationGuide.md) in the game repository: do not add a game-specific branch to this editor. Read that game's own instructions and preserve existing translations.

## Question-to-evidence map

| Question | Authoritative documentation | Code to inspect |
| --- | --- | --- |
| What fields/tabs/rules exist? | ProjectFormat, Schemas | schemas.py, core.py |
| How does a saved edit reach the build? | BuildIntegration, API | core.py, cli.py, game adapter |
| Can a sentence reuse a fragment? | Relations | core.py relation loading, views.py |
| Why does preview differ from selected image? | ProjectFormat, UserGuide | views.py, core.py asset_side/set_variant |
| What can be recovered or deleted? | StorageDiagnostics | core.py snapshot/save/restore methods |
| Where are preferences/logs? | StorageDiagnostics | settings.py, diagnostics.py, processes.py |
| How do buttons run/cancel? | BuildIntegration | processes.py, gui.py |
| Which language is the default? | UserGuide, API, Architecture | gui.py, cli.py, i18n.py, core.py |
| How is the app shipped? | Distribution | Scripts/build.py, verify_package.py, verify_archive.py |
| How do I reproduce a failure? | Testing, Troubleshooting | Tests and disposable Examples copies |

Names in the table refer to the Python package `Source/translation_studio`. Find precise functions with `rg` rather than scanning other projects or relying on a conversation transcript.

## Editing workflow

1. Establish the current behavior from code and a small disposable reproduction.
2. Identify whether the change affects UI, shared contract, persistence or a game adapter. Preserve source, IDs and Decimal values; do not flatten opaque metadata.
3. Make the scoped change and meaningful regression checks. Keep synthetic examples and their generator consistent.
4. Update the authoritative English docs and affected Russian user guidance, export schemas if needed, and update the current changelog section.
5. Run the required checks and, for distribution changes, the package pipeline. Report what actually passed and any remaining limitation.

Do not infer a game's character restrictions from English string length. Unicode test strings, including Cyrillic letter yo and combining characters, are deliberate fixtures. Keep them where required to test behavior; write explanatory comments in English.

## Answering users

Use [UserGuide](UserGuide.md) for ordinary workflows and [Troubleshooting](Troubleshooting.md) for symptoms. Verify uncertain implementation details in source before asserting them. Distinguish implemented features from requests, source tests from packaged execution, and synthetic output from emulator/hardware playability. Do not promise that documentation can answer every future question; identify unsupported behavior and the evidence needed.

Machine-local plans and historical reports are excluded from public source. A clean clone must contain all required instructions. Do not introduce links to a private workspace, personal paths, past chats or a particular commercial-game project.
