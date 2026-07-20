# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
| `scripts/Sync-DeveloperMachine.ps1`   | All                 | Single entry point: ensures its own per-user logon task, clones missing org repos, pulls all, then runs the installer |
| `docs/`                               | â€”                   | Per-tool setup documentation                                                                   |

Everything else in each tool's config directory (sessions, history, cache,
credentials, etc.) is excluded.

## Skills

Each skill lives in `skills/<category>/<name>/SKILL.md` (categories: `engineering/`, `git/`, `tools/`) and is a markdown file with YAML frontmatter. The frontmatter fields are:

```yaml
---
name: skill-name
description: shown in the skill picker and used for model auto-invocation matching
disable-model-invocation: true # optional - hides the skill from model auto-invocation; user slash-command only
---
```

The body is the instruction prompt used by Claude or Codex when the skill is invoked. Skills may reference CLI tools (`gh`, `az`, `git`) and are expected to be self-contained instructions.

### Available Skills

**engineering/**

| Skill                     | Purpose                                                                        |
| ------------------------- | ------------------------------------------------------------------------------ |
| `test-driven-development` | Test-first workflow: red-green-refactor via vertical slices, integration-style tests |

**git/**

| Skill             | Purpose                                            |
| ----------------- | -------------------------------------------------- |
| `create-pr`       | Create a pull request (GitHub or Azure DevOps)     |
| `git-commit-push` | Stage, commit, and push with safety checks         |
| `raise-issue`     | Raise a classified GitHub issue (bug/feature/task) |

**tools/**

| Skill                 | Purpose                                                                    |
| --------------------- | -------------------------------------------------------------------------- |
| `create-blog-post`    | CVEngine portfolio blog posts with helper-validated front matter and build |
| `distill-knowledge`   | Promote knowledge MCP memories into Obsidian vault notes; groom the store  |
| `generate-readme`     | Brief project README from repo code                                        |
| `handoff`             | Compact the conversation into a handoff doc for the next session           |
| `humanizer`           | Remove AI-writing patterns from text                                       |
| `process-inbox`       | File Obsidian inbox captures into permanent notes                          |
| `pythonize-skill`     | Move a skill's deterministic work into bundled Python helpers              |
| `show-and-tell`       | Stakeholder-facing demo run sheet from a commit or commit range            |
| `teach`               | Multi-session teaching workspace with lessons and learning records         |
| `terraform-standards` | House Terraform engineering standards for review, refactor, and validation |
| `write-vault-note`    | Write or update Obsidian vault notes with schema validation                |

## Common Tasks

### Syncing a whole machine (single script)

`scripts/Sync-DeveloperMachine.ps1` is the idempotent single entry point — run it once manually on a new machine and it maintains itself from then on. Each run it:

1. Registers/refreshes its own per-user logon scheduled task (RunLevel Limited, no admin needed) and removes the legacy "Git Pull All Repositories" / "Install Developer Config" tasks
2. Lists non-archived repos in the `skyhaven-ltd` GitHub org (via `gh`) and clones any missing under `<RepositoriesRoot>\Sky Haven` — new org repos appear automatically on the next run
3. Runs `Update-GitRepositories.ps1` to `git pull --ff-only` every repo under the root (honouring the per-machine include list in `scripts/git-repositories/<COMPUTERNAME>.txt`)
4. Runs `Install-DeveloperConfig.ps1`, which installs skills into `~/.claude/skills`, `~/.codex/skills`, **and** any existing profile variants (`~/.claude-*`, `~/.codex-*`, e.g. `.claude-work` for enterprise accounts)

```powershell
.\scripts\Sync-DeveloperMachine.ps1   # one-time bootstrap; installs its own logon task
```

Requires `gh auth login` (and `gh auth setup-git` for HTTPS clone credentials). Use `-SkipClone` when offline, `-NoScheduledTask` for a one-off run that leaves tasks alone.

### Adding a new skill

Create `skills/<category>/<name>/SKILL.md` with the frontmatter and prompt body, then commit and push.

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

See `docs/machine-setup.md` for full prerequisites and the manual equivalent
on Linux/macOS.

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

