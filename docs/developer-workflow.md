# Developer workflow

## Check a machine

Run the read-only check from this repository:

```powershell
.\scripts\Test-DeveloperMachine.ps1
.\scripts\Test-DeveloperMachine.ps1 -Offline -Json
```

Python 3.11 or newer is required. The Python helper also runs directly on Linux/macOS with `python3 scripts/test-developer-machine.py`; the installer and machine-sync scripts target Windows. `--home` and `--codex-home` let the helper inspect another installation. Authentication checks use the current process environment and account.

The check reports CLI availability, GitHub/Codex authentication, optional Azure authentication, shared Codex configuration drift, instruction and skill links/copies for both agents, and stale managed skills. It does not run a model, change configuration or reveal credentials. Offline mode skips authentication checks. Independent CLI checks run concurrently; each has a 15-second timeout.

Exit code 0 means no failures; warnings may still need attention. Exit code 1 means at least one required check failed. JSON output contains `ok` and a `checks` array. Link/copy failures usually need `Install-DeveloperConfig.ps1`; inspect links to another checkout before replacing them.

To check immediately after a machine sync:

```powershell
.\scripts\Sync-DeveloperMachine.ps1 -CheckHealth
```

`-CheckHealth` applies to that invocation; the logon task remains a sync-only task. The installer seeds missing model/reasoning defaults but preserves existing local choices. Permissions and sandbox settings remain managed. Project-level settings, selected profiles and command-line overrides can further change a Codex session; this check compares the user config, not every session's effective configuration. `CODEX_HOME` is respected. Unchanged merged Codex files are not rewritten, and scheduled syncs prefer PowerShell 7.

## Scheduled Codex work

For local projects, ask Codex in the desktop app to schedule a bounded task, or use its Scheduled/Automations interface. For example: “Every weekday at 09:00 Europe/London, check this project's failed CI runs and summarize actionable failures. Do not change files or post comments.” Test the prompt once before scheduling and inspect the first few results. Keep the project available, computer awake, and app running at the scheduled time. The laptop does not need to run 24/7 if tasks run during working hours. Web scheduled tasks can use connected tools but cannot directly access your local checkout. [Official scheduling documentation](https://learn.chatgpt.com/docs/automations?surface=app)

A locked screen normally leaves background CLI/file work running; this is an operating-system expectation, not an explicit locked-screen guarantee in the Codex documentation. Sleep, hibernation, shutdown and signing out prevent local execution. Work-device policies, VPN availability and interactive login prompts can also interrupt it. Desktop UI automation may require an unlocked session. Verify with one scheduled test while the device is locked.

For a headless server, use an OS scheduler (Windows Task Scheduler or a Linux systemd timer/cron) to launch `codex exec` under the account that owns the checkout, settings and credentials. This is separate from the desktop app's scheduling interface. Set the working directory, absolute executable path, environment, timeout, non-overlap policy and output log in that scheduler. The server needs to be awake when jobs run; your laptop can be off. [Non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode)

For a private server using your subscription, sign in there with `codex login --device-auth` when device-code login is enabled. `codex exec` reuses saved CLI authentication. ChatGPT login uses subscription access; API-key login uses separately billed API access. Scheduled execution must use the same account and an accessible credential store; do not put credentials in this repository. [Authentication and headless login](https://learn.chatgpt.com/docs/auth)

For this setup, use one personal server for reliable unattended CLI tasks, or one awake desktop for app-managed tasks. Avoid scheduling the same maintenance task on every synced machine. No scheduled Codex task is installed by these changes.

## Agent workflow

Global instructions for Claude Code and Codex live in `system/SYSTEM.md`. Both agents use the agent-skills plugin: the installer enables `agent-skills@addy-agent-skills` through `claude/settings.json` and, when the `codex` CLI is available, registers the `addyosmani/agent-skills` marketplace and adds `agent-skills@agent-skills`.

Work moves through the agent-skills phases `/spec`, `/plan`, `/build`, `/review` and `/ship`. Task artefacts live under `.agents/NNN - Name/` (`CYCLE.md`, `SPEC.md`, `PLAN.md`, `TODO.md`, `REVIEW.md`, `SHIP.md` and `supporting/`). Architecture decision records live in `.agents/ADR/` and the project quality bar in `.agents/CONSTRAINTS.md`. `.agents/` is listed in the machine's global gitignore, so these files stay out of repositories.

The `lifecycle-band` mod in `claude/mods/` draws the current phase, next phase, tokens and cost above the Claude Code prompt. The installer links `~/.claude/mods` to that folder and `claude/settings.json` loads it through `CLAUDE_CODE_PLUGIN_DIRS`.

See [agent-workflow.md](agent-workflow.md) for the step-by-step workflow to follow.
