# Translation Studio user guide

[Русский](UserGuide.ru.md)

## Starting the application

Extract the portable ZIP and run `TranslationStudio.exe`. Keep the entire folder, including `_internal`, the CLI and documentation. No separate Python installation is required. The folder must be writable: preferences and logs are stored beside the executable in `Data`.

A first launch without an existing or imported profile uses English, regardless of the Windows language. Choose **Русский / English** and a light or dark theme at the bottom of the sidebar. Preferences are saved immediately and restored on the next launch. Updating the application keeps your existing choice.

**User guide** opens the local guide in the current interface language. An internet connection is unnecessary. Changing the interface language does not translate project data or change a build command's target language.

## Opening and closing projects

Click **Open project** or press `Ctrl+O` and select the game root containing `Translation/project.json`. If the configuration is missing, the application shows the expected path. The project defines tabs, languages, constraints, relations and commands. A game agent prepares the integration using the developer [IntegrationGuide](IntegrationGuide.md).

The sidebar lists the last 15 projects and scrolls when space is limited. One project is loaded at a time. **Close project** returns to the start screen and keeps the recent entry. **Remove from list** below the list removes the selected recent entry; if it is active, it also closes that project. Right-click an entry for these commands, including **Close and remove from list**. No game files are deleted.

Unsaved edits require **Save**, **Discard** or **Cancel**. Cancelling keeps the project and its recent entry. Finish or cancel a running build before closing. With no project loaded, the translation language, save status and project controls are hidden; preferences and help remain available.

An **×** button is always visible on the right of each recent project. Its tooltip says **“Close and remove from list”**. For an inactive project it only removes the recent entry, keeping the active project and its edits intact. Clicking the already open project again does nothing and preserves the editor. Use **Reload** explicitly to read changes made to files on disk.

**Examples** opens the sample folder. `Synthetic NES` includes text, relations, test tones, a context screenshot and image alternatives; `Synthetic Sega` includes text and a screenshot. These samples contain no ROMs. Copy a sample to a separate writable folder before experimenting. Their builders produce synthetic data, not patches for real games.

## The table and editing

The entire table is read-only. Select a row and edit its translation in the large field below the table. The original is always read-only. Column separators are visible in both themes. `Ctrl+C` in the table copies the selected row with tabs between columns.

Search includes IDs, text, context and comments. Filters show all records, untranslated records, modifications or errors. Sorting changes the view without changing IDs or the authoring catalog's order. Drag the divider between the table and details to resize them. The details area scrolls to show rules, relations and screenshots.

Use **Translation language** at the top right to choose a target language. Edits to multiple languages are saved together. **Context** (`context`, for example “Main menu”) and **Comment** (`comment`, for example “Start button”) have separate labels. The game agent supplies these fields; empty sections are hidden. **My translation note** is editable and stored in `notes` for the selected language.

**Mark untranslated** sets the value to `null`. An intentionally empty string is different: clear the lower translation field. Empty strings are allowed only with `allowEmpty: true`. Incomplete translations can be saved, although a builder may require every record it uses to be translated.

## Constraints and errors

The **Characters** counter shows usage and any limit, for example `54 / 20`, followed by a readable error when the limit is exceeded. Its tooltip explains that it counts Unicode code points, including spaces, tags and line breaks. A combined visible character may use several units. A configured byte limit is shown separately and includes the declared terminator.

Click **Translation rules** to expand active rules before entering text. They are also available in that button's tooltip. Projects can constrain characters, lines, bytes, empty strings, exact token counts such as `{0}`, an allowed character set, and a separate forbidden set such as `^~`. Matching is case-sensitive. Spaces, newlines and token punctuation must also belong to an allowed set. Text is never automatically truncated or corrected.

Errors appear in red below the field and as an error status in the table. Cell backgrounds mark errors or warnings; row selection may cover that background, so also check the details. Warnings are explicitly labelled. Errors prevent saving; warnings allow it. Character errors show the character and its Unicode code.

The project defines confirmed limits per record and language. An absent limit means it is not configured. The game adapter still checks its encoding, fonts and binary layout. The generic byte limit supports UTF-8 and UTF-16LE; a custom ROM character table must be validated by the builder.

## Context screenshots

If the agent attaches PNG references to a record, **Context screenshots** appears in its details. Thumbnails include captions; longer lists scroll horizontally. Click a thumbnail to enlarge it. Use the wheel to zoom, drag to pan, and **Fit** to show the entire image. Close the viewer to return to editing.

The project owns these files. The application does not capture the game or edit screenshots. Several records can reference the same file without duplication. A missing or corrupt PNG is marked as unavailable but does not block independent text editing. The section is hidden when no screenshots are configured.

## Related fragments

A record belonging to a project-defined sequence displays **Relations**. Select a sequence to see the full original and translated sentences. Component IDs are listed below; clicking a link opens that record, including on another tab. The combined sentence is read-only and recalculated from current edits, including unsaved ones.

One ID can belong to several sequences. Identical words with different IDs do not automatically become related. A missing translation is explicitly marked without substituting the original. The project defines the order and separators; spaces are not added automatically. Each fragment keeps its constraints. Game-specific limits for an entire sequence belong to the project adapter.

## Audio

Select a record and click **Play** on either side. If the project supplies an audio sequence, **Play all** plays parts in order with configured pauses. The status bar shows the current ID and part number. **Stop**, another playback request, or changing the tab, language or project cancels the entire queue.

Supported files are WAV with integer PCM at 8, 16, 24 or 32 bits. A working Windows audio output is required. A missing or invalid part prevents playback of that complete side; parts are never silently skipped. The available original can still be played separately. Playback does not perform seamless audio mixing. The game agent replaces files; selectable audio alternatives are not currently supported.

## Images and alternatives

The image tab compares original and translated PNG files. Use the wheel to zoom and drag to pan. **Link views** synchronizes zoom and scrolling; **Fit** shows full images. Missing translations are shown explicitly. If the project provides a hash for the real asset, a mismatch marks its preview as stale.

With translated alternatives, the comparison shows a name, comment, a counter such as **“1 of 2”**, and arrow buttons. Arrows only change the preview. **Use this variant** changes the build selection; then click **Save**. “Build selection” shows the editor's current choice; the overall save indicator tells you whether it is saved. An external builder reads the last saved state.

Browsing alternatives creates no edits. Selections are separate for each target language and participate in draft recovery and rollback. A normal single asset has no variant controls. Read-only projects allow previewing but not changing the build selection. The agent creates alternatives and edits their pixels within the project. The NES sample copies the chosen image into `Builds/Patch`; its `manifest.json` records the variant ID and resource hash.

## Saving and recovery

**Save**, `Ctrl+S`, writes translations, notes and selected image alternatives to catalogs in `Translation`. The editor and builder use those same files. A second editor opens an occupied project read-only. If another agent changes a file after you open it, saving stops with a conflict message: preserve a draft and reconcile edits before reloading.

`Work/TranslationStudio/Recovery` contains two maintained snapshots: `draft.json` and `previous.json`. The draft updates every 15 seconds while there are edits; the previous snapshot is replaced on a successful save. Saving removes the draft. Saving without changes does not consume rollback. Snapshots contain JSON catalogs for translations and selections, not PNG files, audio files or the game itself.

After a crash, reopening offers to restore the draft, discard it, or cancel opening. Changes since the last draft interval may be lost. Explicit **Discard** removes the draft. **History → Save recovery copy** updates the draft immediately and opens its folder.

**History → Restore previous save** loads the state before one save into the editor. Review it and save. **Restore draft** loads the draft; **Restore edits…** lets you choose an older recovery file. Unique recovery files from earlier versions are not automatically deleted.

Recovery checks the original text and IDs; image recovery also checks resource and variant descriptions. It restores only translations, notes and selections, leaving originals and game extensions unchanged. Changed originals or alternative sets require manual reconciliation; there is no automatic merge. Each file replacement is atomic, but a group of files is not one transaction. A partial-save error lists files already saved. The technical reference is [StorageDiagnostics](StorageDiagnostics.md), in Russian.

## Project commands

Project buttons appear when `actions` are configured. **Rebuild patch** first saves edits and validates input, then starts the project's builder. On first use, the application shows executables, arguments and working directories. Authorization is remembered for that folder and command definitions; a changed command needs new authorization. Opening a project runs no commands by itself.

While a command runs, editing and project switching are disabled. **Build log** toggles the lower panel containing output, the result and **Cancel**, which stops the child process tree. **Build output** becomes available after success. A nonzero exit, cancellation and changed inputs are reported separately.

A command has a fixed `targetLanguage`: changing the right-hand column does not change its build language. The game's README explains its output and installation. A successful command does not imply the game was tested in an emulator or on hardware.

If `python` cannot be found, enter its path in **Settings**. This is a personal preference. The portable examples use `DemoBuilder.exe` and need no Python installation.

## Troubleshooting

**Open logs folder** opens diagnostics. `current.log` belongs to this launch and `previous.log` to the previous launch. Only two logs of up to 2 MiB each are kept. They contain actions and errors, not translation text, notes or keystrokes. After restarting following a failure, preserve `previous.log` before another launch replaces it. Forced termination or power loss may prevent the final error from being recorded.

For builder problems, also collect files from the game's `Work/TranslationStudio/Logs`. Two runs are retained: readable UTF-8 logs and bounded raw `.output.bin` streams, up to 2 MiB each. An external builder controls its own output and may print translation content. If an encoding warning and `\\xNN` escapes appear, ask the agent to check `outputEncoding`: UTF-8, CP1251 or CP866. Previously corrupted logs cannot be repaired automatically.

The developer [Testing](Testing.md) reference records application checks and limitations, in Russian. The game's agent is responsible for encoding, pointers, fonts, block sizes and whether its patch works.
