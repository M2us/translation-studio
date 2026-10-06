# Translation Studio 1.01 — Windows portable

Run **TranslationStudio.exe** from this folder. No Python installation is required. Keep the entire folder, including `_internal` and `TranslationStudio.Cli.exe`, when moving it.

Click **Open project** and choose a game root containing `Translation/project.json`. **Examples** offers Synthetic NES/Sega projects with generated media and demonstration builders. Copy an example to your own folder before editing. These examples contain no ROMs and are not real-game translations.

- [English user guide](Docs/UserGuide.html) · [Русское руководство](Docs/UserGuide.ru.html).
- [Documentation index](Docs/README.md).
- [Game integration guide](Docs/IntegrationGuide.md).
- [Project format](Docs/ProjectFormat.md) and [JSON Schemas](Docs/Schemas/).
- [API and CLI](Docs/API.md), [architecture](Docs/Architecture.md), [testing](Docs/Testing.md).
- [Agent instructions](AGENTS.md) and [agent navigation guide](Docs/AgentGuide.md).
- [Changelog](CHANGELOG.md).

A fresh profile starts in English. Change theme/language at the bottom of the sidebar; preferences are saved automatically beside the EXE in `Data/profile.json`. The local guide follows the UI language. The comparison table is read-only; edit the selected target in the detail panel. Arrows browse image alternatives; Use this variant and Save persist a build choice.

Translations stay inside the selected game. History restores a draft or one previous save. Application logs stay bounded in `Data/Logs`; see [StorageDiagnostics](Docs/StorageDiagnostics.md). Close/remove commands do not delete game files.

The table margin shows catalog row numbers, preserved by search and sorting. Enable **Bookmark** on a selected record and optionally enter a personal note. Flags and notes save automatically in `Data/profile.json`. When bookmarks exist, their list and previous/next arrows appear above the tabs. Bookmarks do not affect game builds. Keep `Data` when replacing this portable installation to retain personal preferences and bookmarks.

`TranslationStudio.Cli.exe validate <game-root> --language ru --complete` validates without the GUI. CLI messages default to English; use `--ui-language ru` before the subcommand for Russian. `SDK` contains the headless Python reader and requirements for builders. `ThirdParty` contains dependency versions/notices, and `SHA256SUMS.txt` lists package file hashes.

Developer instructions describe commands run from the separate source distribution. This portable package does not contain the full development environment. The application version is 1.01; `schemaVersion: 1` is the data contract. Created by [M2us](https://github.com/M2us), copyright (c) 2026 M2us, under the [MIT License](LICENSE). Retain copyright/license notices when redistributing; third-party dependencies retain their own licenses in `ThirdParty`. The app is unsigned and has no installer. See [Distribution](Docs/Distribution.md).
