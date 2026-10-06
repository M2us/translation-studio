# Storage, recovery and diagnostics

## Three translation states

The author catalogs in `Translation` remain the only builder input. The editor changes in-memory copies. It maintains two fixed service files in the game's `Work/TranslationStudio/Recovery`:

| File | Purpose |
| --- | --- |
| `draft.json` | Complete current text catalogs and image catalogs with variants, including all languages. Updated every 15 seconds while dirty, before writes and on save failure; unchanged drafts are not rewritten. |
| `previous.json` | One snapshot from before the last save, covering multiple tabs and image choices. Restores one saved operation. |

These are **three states**, not necessarily three files total: a project can have several main catalogs, consolidated into each snapshot. Audio/image binaries, original ROMs and build intermediates are not copied into recovery.

A successful save updates previous and deletes draft. Saving without changes does not replace previous. Explicit Discard deletes draft; a crash leaves it. On reopening, the user can restore, discard or cancel opening. Restore loads target texts, notes and selected image IDs into memory; ordinary Save is still required. It does not replace source, IDs or extensions. Changed source prevents restore. For image catalogs, resource descriptions and variants must match except for selection. Older text-only snapshots restore only text. Browsing alternatives does not create edits or drafts.

Before writes, validate structure, constraints and external file hashes. Each catalog uses a temporary file, flush/fsync and atomic replacement. Short-lived `previous.pending.tmp` prepares previous before modifying catalogs. On the next open after interruption, it becomes previous if catalogs changed; otherwise it is removed. On partial multi-file save, previous contains the state before the entire attempt, draft the desired edits, and the UI reports which files were saved. This is not a filesystem-wide transaction or a guarantee against disk failure.

Recovery does not replace external project backups. Builders never read it. Older uniquely named recovery files are not automatically deleted because they may contain unique edits; the user may inspect them through History and remove them manually. Unrelated files in that folder are left alone.

## Preferences and portability

`Data/profile.json` beside the EXE stores theme, UI language, recent projects, action trust and Python path. Theme/language changes persist immediately. Source runs use `Data` in the repository root. `TRANSLATION_STUDIO_PROFILE` overrides the file for isolated tests.

A new empty portable profile may automatically import an existing `%LOCALAPPDATA%/TranslationStudio/profile.json`; the old file is preserved. Subsequent changes use the portable profile. Without a saved/imported language, English is selected. Release ZIPs contain no personal profile. The application directory must be writable.

A second instance using the same profile is refused to protect shared settings/logs. A separate portable installation may open the same game, but the editor lock still prevents concurrent writes. `session.lock` is a fixed lock file, not another log.

## Application logs

`Data/Logs/current.log` covers the current run; `previous.log` the preceding run. Startup rotates current into previous. Each is bounded to **2 MiB**, with space reserved for crash stacks; old leading data is dropped. No dated log names accumulate. Files are unbuffered at Python level so operation-start events are written before completion.

Events include project open/close, tab/theme/language selection, an edit-completed event after a pause, saving, builds, cancellation, recovery and errors. Logs exclude field contents, translator notes, searches, individual keys, locals and source-code lines. Exceptions include type, Studio/OS code and stack frames (file, line, function); arbitrary exception text is excluded because it could contain translation data.

Handlers cover uncaught main/background Python exceptions, errors passed to the UI, and an available native crash stack via `faulthandler`. Forced termination, power loss or disk failure may prevent the final reason from being recorded. Existing events can still help. After a crash, the first restart preserves its log as previous; another restart replaces it. **Open logs folder** locates the files.

## Project command logs

The game's `Work/TranslationStudio/Logs` stores `current.log`, `previous.log` and matching `current.output.bin`/`previous.output.bin`: two runs, each file at most 2 MiB. The readable tail is UTF-8; the binary tail preserves original output bytes. Very long lines and UI queues are bounded. A fixed `action.lock` prevents simultaneous rotation. Legacy generated command-log names are cleaned on a new command; unrelated files are not deleted.

`outputEncoding` controls decoding. Invalid bytes are shown as escaped `\\xNN` with a warning. Incremental decoding tolerates a multibyte character split across reads.

**External tools control their own output.** A builder can print translations or private paths. The application's field-content privacy guarantee does not extend to arbitrary external stdout/stderr. Review logs before sharing and configure game adapters accordingly. See [BuildIntegration](BuildIntegration.md).
