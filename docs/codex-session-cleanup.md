# Codex session cleanup

`scripts/Clear-CodexSessionData.ps1` deletes known local Codex session data directly, without sending it to the Recycle Bin. Deleted conversations cannot be resumed locally. It preserves `auth.json`, `config.toml`, `AGENTS.md`, skills, rules, hooks, plugins, installation metadata and sandbox tooling. Unknown files are preserved so a future Codex version cannot silently cause unrelated data to be deleted.

Preview the targets:

```powershell
.\scripts\Clear-CodexSessionData.ps1 -WhatIf
```

Register or update the current user's daily 5pm task without deleting anything immediately:

```powershell
.\scripts\Clear-CodexSessionData.ps1 -InstallScheduledTask
```

The task uses local Windows time, runs without elevation while the user is logged on (including a locked screen), and allows battery operation. Missed runs use Task Scheduler's start-when-available setting. It cannot run while the computer is off or the user is signed out, and does not wake the computer. Keep the repository at its installed path; rerun registration if it moves. The resolved Codex, temporary and editor-log directories are saved in the task action; `CODEX_HOME` is respected at registration, or use `-CodexDirectory` explicitly. `-TemporaryDirectory` defaults to the current user's temporary directory and `-EditorLogDirectory` defaults to `%APPDATA%\Code\logs`.

Close Codex and any editor integration using its backend before cleanup. If any `codex*` process is running, the script fails before deletion and Task Scheduler retries every 15 minutes, up to 16 times. It does not terminate processes. Leaving Codex open throughout the retry window means that day's cleanup does not happen. Do not reopen it during cleanup; process checks cannot prevent a concurrent launch. Locked files and permission-related deletion failures produce warnings, cleanup continues with other targets, and a final warning reports incomplete cleanup. These warnings do not fail the task or trigger its failure retries; rerun manually after resolving them or wait for the next daily run. Safety-check failures still stop cleanup.

Run once after closing Codex:

```powershell
.\scripts\Clear-CodexSessionData.ps1
```

Cleanup covers session and archived-session directories, prompt history, session indexes, local memory files, generated images, temporary files, caches, shell snapshots, thread locks, logs (including `.sandbox/sandbox.log`), desktop global state when stored here, and known session/state SQLite databases with their journal files. It refuses linked cleanup targets or a Codex root with linked ancestors, preventing traversal into shared repositories or other directories. Investigate the link rather than overriding that check.

Outside the Codex directory, cleanup also deletes `codex-clipboard-<identifier>.png` files directly inside the temporary directory and numbered `Codex Finish Notifier.log` files beneath the editor-log directory. It checks all selected locations before any deletion and rejects linked external roots, ancestors or editor-log directories. Missing external directories are skipped. Unrelated temporary files and editor logs are preserved. A running editor extension can hold or recreate its log; close VS Code for reliable notifier-log cleanup.

The `.sandbox` directory is retained for sandbox state, and `.sandbox-bin` and `.sandbox_migration` remain preserved as tooling and installation metadata. Only the known sandbox log is deleted.

Task-generated documents, comparison folders and other working files are not automatically disposable merely because their names start with `codex`. They remain outside the cleanup list, as do shared VS Code databases and general shell history. Inspect and remove unwanted work products separately.

This is file deletion, not verified media sanitization. SSD wear levelling, backups, filesystem metadata and recovery mechanisms can retain data. It does not remove cloud history, other desktop/editor data, browser or shell history, Windows event logs, installed applications, or monitoring records. Preserved credentials, settings, plugins and the scheduled task also reveal that Codex is installed or configured. It cannot make the machine appear never to have used Codex. Keeping the login also keeps a usable credential on the machine. Device-management or endpoint-security tooling may already have collected activity centrally; deleting local application files does not remove those records or prevent future collection.

For less future prompt-history storage, OpenAI documents `[history]` with `persistence = "none"` in `config.toml`. This controls `history.jsonl`; do not treat it as disabling every session, database or log. The cleanup script does not change configuration. See [OpenAI's configuration documentation](https://learn.chatgpt.com/docs/config-file/config-advanced).

Inspect the schedule and most recent result:

```powershell
Get-ScheduledTask -TaskName "Codex Session Cleanup"
Get-ScheduledTaskInfo -TaskName "Codex Session Cleanup"
```

Remove the schedule:

```powershell
Unregister-ScheduledTask -TaskName "Codex Session Cleanup" -Confirm:$false
```
