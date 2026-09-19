# AGENTS.md

This file provides guidance to Codex CLI and other AI coding agents when working with code in this repository.

## Repository Purpose

This is a portable developer configuration repository. Junctions and symlinks
connect each tool's expected config location into this repo, so a single
`git pull` updates all tools on a machine simultaneously.

Tracked in version control (enforced by `.gitignore`):

| Path                                  | Tool                | Purpose                                                                                        |
| ------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------- |
| `skills/`                             | Claude Code + Codex | Shared skill source; linked into `~/.claude/skills` and `~/.codex/skills/<name>`               |
| `claude/settings.json`                | Claude Code         | Global tool permissions and model config                                                       |
| `system/SYSTEM.md`                    | Claude Code + Codex | Canonical global instructions installed under each tool's required filename                    |
| `codex/config.toml`                   | Codex CLI           | Model, reasoning effort, options                                                               |
| `scripts/Install-DeveloperConfig.ps1` | All                 | One-shot link creation for a new Windows machine; can install a per-user logon task for itself |
| `scripts/Update-GitRepositories.ps1`  | Git                 | Pulls all repositories under a configurable root; can install a per-user logon task for itself |
| `scripts/Test-DeveloperMachine.ps1` | All | Read-only CLI, authentication, config, skill and MCP checks |
| `docs/`                               | â€”                   | Per-tool setup documentation                                                                   |

Everything else in each tool's config directory (sessions, history, cache,
credentials, etc.) is excluded.

## Skills

Each skill lives in `skills/<name>/SKILL.md` and is a markdown file with YAML frontmatter. The frontmatter fields are:

```yaml
---
name: skill-name
description: shown in the skill picker
disable-model-invocation: true # optional — Claude slash-command only
---
```

For Codex, use `agents/openai.yaml` with `policy.allow_implicit_invocation: false` to keep a skill available for explicit use while preventing automatic chat invocation.

The body is the instruction prompt used by Claude or Codex when the skill is invoked. Skills may reference CLI tools (`gh`, `az`, `git`) and are expected to be self-contained instructions.

### Available Skills

| Skill | Purpose |
| --- | --- |
| `buy-for-life` | Research durable products and UK value |
| `create-pr` | Create GitHub or Azure DevOps pull requests |
| `distill-knowledge` | Promote durable knowledge into Obsidian notes |
| `generate-readme` | Generate a brief project README |
| `git-commit-push` | Stage, commit and push with safety checks |
| `handoff` | Save portable context for another machine or agent |
| `humanizer` | Remove AI-writing patterns from text |
| `negotiate-voss` | Draft negotiation and difficult-conversation messages |
| `process-inbox` | Process Obsidian inbox captures |
| `terraform-standards` | Apply house Terraform engineering standards |

## Common Tasks

### Adding a new skill

Create `skills/<name>/SKILL.md` with the frontmatter and prompt body, then commit and push.

Existing skill edits are immediately available on linked machines after a `git pull` when junctions or symlinks are available. When the installer falls back to copies, re-run `.\scripts\Install-DeveloperConfig.ps1` after pulling to refresh them. When adding a new skill folder, re-run the installer so both Claude and Codex get per-skill entries under `~/.claude/skills/<name>` and `~/.codex/skills/<name>`.

### Setting up a new device

Clone the repo and run the install script (Windows):

```powershell
git clone https://github.com/liam-goodchild/ops-developer-config.git "C:\Local Files\Repositories\Sky Haven\ops-developer-config"
cd "C:\Local Files\Repositories\Sky Haven\ops-developer-config"
.\scripts\Install-DeveloperConfig.ps1
```

The script creates junctions for skill directories and file symlinks where possible. Global Claude and Codex instructions come from `system/SYSTEM.md`; root-level `CLAUDE.md` and `AGENTS.md` remain repo-local documentation for this configuration repository.
Codex skills are linked under `~/.codex/skills`; the legacy `~/.agents/skills`
path is cleaned up only when it is the old junction to this repo.
On domain-joined machines where Group Policy blocks symlink creation, it falls
back to file copies and prints a reminder â€” run `.\scripts\Install-DeveloperConfig.ps1` again
after each `git pull` to refresh the copies. An Administrator shell bypasses
this restriction and produces true symlinks.

See `docs/developer-workflow.md` for machine checks, portable handoffs,
and scheduling options. The installer and machine sync target Windows.

### Installing user logon tasks

Both PowerShell scripts can idempotently create or update a per-user scheduled
task that runs the same script at user logon. These tasks use `RunLevel Limited`
and do not require local administrator privileges.

Install the developer config refresh task:

```powershell
.\scripts\Install-DeveloperConfig.ps1 -InstallScheduledTask
```

Install the repository update task:

```powershell
.\scripts\Update-GitRepositories.ps1 `
  -InstallScheduledTask `
  -RepositoriesRoot "C:\Local Files\Repositories"
```

If the repositories root differs between machines, pass the machine-specific
path when installing the `Update-GitRepositories.ps1` task.

### Pulling updates on an existing device

```powershell
cd "C:\Local Files\Repositories\Sky Haven\ops-developer-config"
git pull
```

If the install script created **symlinks/junctions** (admin or Developer Mode was available),
the pull is immediately live. If it fell back to **file copies**, re-run the
install script after pulling to refresh them:

```powershell
.\scripts\Install-DeveloperConfig.ps1
```

### gh CLI path (Windows)

The `gh` CLI is not on the bash `PATH` by default. Use the full path:

```bash
/c/Program Files/GitHub CLI/gh.exe
```

## claude/settings.json

Defines globally allowed tools. When adding new MCP tool permissions, add them to the `allow` array. The `deny` array is currently empty â€” prefer allowlist-only control.

Plugins (marketplace and official) are configured under `enabledPlugins` â€” these are not synced via git and must be installed per-device.

## Code Style

These conventions apply across all IaC and scripting work in connected repositories:

- **Terraform**: 2-space indent, explicit provider versions, use `for_each` instead of `count` for resource toggling
- **Shell**: Bash with `set -euo pipefail`; quote all variable expansions; prefer idempotent operations
- **YAML / JSON**: 2-space indent, no trailing whitespace
