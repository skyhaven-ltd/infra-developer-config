# Developer workflow

## Check a machine

Run the read-only check from this repository:

```powershell
.\scripts\Test-DeveloperMachine.ps1
.\scripts\Test-DeveloperMachine.ps1 -Offline -Json
```

Python 3.11 or newer is required. The Python helper also runs directly on Linux/macOS with `python3 scripts/test-developer-machine.py`; the installer and machine-sync scripts target Windows. `--home` and `--codex-home` let the helper inspect another installation. Authentication checks use the current process environment and account.

The check reports CLI availability, GitHub/Codex authentication, optional Azure authentication, shared Codex configuration drift, instruction and skill links/copies for both agents, stale managed skills, the handoff directory, and an authenticated Knowledge MCP initialization. It does not run a model, change configuration or reveal credentials. Offline mode skips authentication and network checks. Independent CLI/network checks run concurrently; each CLI check has a 15-second timeout and MCP requests have a 10-second socket timeout.

Exit code 0 means no failures; warnings may still need attention. Exit code 1 means at least one required check failed. JSON output contains `ok` and a `checks` array. Link/copy failures usually need `Install-DeveloperConfig.ps1`; inspect links to another checkout before replacing them.

To check immediately after a machine sync:

```powershell
.\scripts\Sync-DeveloperMachine.ps1 -CheckHealth
```

`-CheckHealth` applies to that invocation; the logon task remains a sync-only task. The installer seeds missing model/reasoning defaults but preserves existing local choices. Permissions, sandbox settings and Knowledge MCP configuration remain managed. Project-level settings, selected profiles and command-line overrides can further change a Codex session; this check compares the user config, not every session's effective configuration. `CODEX_HOME` is respected. Unchanged merged Codex files are not rewritten, and scheduled syncs prefer PowerShell 7 so Claude MCP registration is supported.

## Commit, push and create a PR

An explicit request such as “commit, push and create a PR” authorizes all three named operations through their existing skills. The agent drafts the messages without asking for approval again. Requests to review a draft first remain conditional; secret/risk checks and material scope or target ambiguity still require resolution. Creating a PR does not authorize merging it. Branches use `patch/`, `minor/` or `major/` in both the instructions and PR helper.

## Portable handoffs

Choose an existing directory that your sync software already makes available on your machines. Configure its machine-specific path once:

```powershell
.\scripts\Install-DeveloperConfig.ps1 -HandoffDirectory "D:\Synced\Agent Handoffs"
```

This runs the normal installer and persists `AGENT_HANDOFF_DIR`. Restart existing agent apps to pick up the environment change. To configure only the variable on Windows, use `[Environment]::SetEnvironmentVariable("AGENT_HANDOFF_DIR", "D:\Synced\Agent Handoffs", "User")`. On Linux/macOS, set `AGENT_HANDOFF_DIR` in your shell environment. The directory is not created or synchronized by the installer.

Invoke `$handoff` in Codex or `/handoff` in Claude. An explicit destination overrides the environment setting. Without an available destination the skill uses the OS temporary directory and labels the result local-only. Each handoff records the repository, branch/commit, push state, uncommitted work, verification and next action. It uses relative paths and references existing artifacts. Handoffs transfer context, not unpushed code or authorization, and are not stored as durable knowledge MCP memories.

## Scheduled Codex work

For local projects, ask Codex in the desktop app to schedule a bounded task, or use its Scheduled/Automations interface. For example: “Every weekday at 09:00 Europe/London, check this project's failed CI runs and summarize actionable failures. Do not change files or post comments.” Test the prompt once before scheduling and inspect the first few results. Keep the project available, computer awake, and app running at the scheduled time. The laptop does not need to run 24/7 if tasks run during working hours. Web scheduled tasks can use connected tools but cannot directly access your local checkout. [Official scheduling documentation](https://learn.chatgpt.com/docs/automations?surface=app)

A locked screen normally leaves background CLI/file work running; this is an operating-system expectation, not an explicit locked-screen guarantee in the Codex documentation. Sleep, hibernation, shutdown and signing out prevent local execution. Work-device policies, VPN availability and interactive login prompts can also interrupt it. Desktop UI automation may require an unlocked session. Verify with one scheduled test while the device is locked.

For a headless server, use an OS scheduler (Windows Task Scheduler or a Linux systemd timer/cron) to launch `codex exec` under the account that owns the checkout, settings and credentials. This is separate from the desktop app's scheduling interface. Set the working directory, absolute executable path, environment, timeout, non-overlap policy and output log in that scheduler. The server needs to be awake when jobs run; your laptop can be off. [Non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode)

For a private server using your subscription, sign in there with `codex login --device-auth` when device-code login is enabled. `codex exec` reuses saved CLI authentication. ChatGPT login uses subscription access; API-key login uses separately billed API access. Scheduled execution must use the same account and an accessible credential store; do not put credentials in this repository. [Authentication and headless login](https://learn.chatgpt.com/docs/auth)

For this setup, use one personal server for reliable unattended CLI tasks, or one awake desktop for app-managed tasks. Avoid scheduling the same maintenance task on every synced machine. No scheduled Codex task is installed by these changes.
