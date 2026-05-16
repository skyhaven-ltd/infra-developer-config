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
| `CLAUDE.md`                           | Claude Code         | Global Claude system instructions                                                              |
| `git/hooks/`                          | Git                 | Global git hooks (pre-commit, etc.)                                                            |
| `codex/instructions.md`               | Codex CLI           | System prompt / custom instructions                                                            |
| `codex/config.toml`                   | Codex CLI           | Model, reasoning effort, options                                                               |
| `vscode/settings.json`                | VS Code             | Editor and extension settings                                                                  |
| `vscode/keybindings.json`             | VS Code             | Custom keyboard shortcuts                                                                      |
| `git/config.shared`                   | Git                 | Shared aliases and core settings (via `[include]`)                                             |
| `git/gitignore_global`                | Git                 | Global gitignore patterns                                                                      |
| `scripts/Install-DeveloperConfig.ps1` | All                 | One-shot link creation for a new Windows machine; can install a per-user logon task for itself |
| `scripts/Update-GitRepositories.ps1`  | Git                 | Pulls all repositories under a configurable root; can install a per-user logon task for itself |
| `docs/`                               | —                   | Per-tool setup documentation                                                                   |

Everything else in each tool's config directory (sessions, history, cache,
credentials, etc.) is excluded.

## Skills

Each skill lives in `skills/<name>/SKILL.md` and is a markdown file with YAML frontmatter. The frontmatter fields are:

```yaml
---
name: skill-name
description: shown in the skill picker
disable-model-invocation: true # optional — runs without a model call (pure bash)
---
```

The body is the instruction prompt used by Claude or Codex when the skill is invoked. Skills may reference CLI tools (`gh`, `az`, `git`) and are expected to be self-contained instructions.

### Available Skills

Naming schema: `{verb}-{subject}[-{qualifier}]`

**Review**

| Skill                  | Purpose                                                   |
| ---------------------- | --------------------------------------------------------- |
| `review-terraform`     | Terraform code and CI/CD pipeline (minimalist lens)       |
| `review-gha-pipelines` | GitHub Actions workflow quality, security, reliability    |
| `review-ado-pipelines` | Azure DevOps YAML pipeline quality, security, reliability |
| `review-pull-request`  | Pull request review (GitHub and ADO)                      |
| `review-security`      | App security review (OWASP, Azure) and CI security gates  |
| `review-waf`           | Azure Well-Architected Framework pillar assessment (RAG)  |
| `review-caf`           | Cloud Adoption Framework landing zone alignment           |

**Format**

| Skill                  | Purpose                                                                      |
| ---------------------- | ---------------------------------------------------------------------------- |
| `format-terraform`     | Terraform file structure, naming, tagging, pinning, and formatting standards |
| `format-ado-pipelines` | Azure DevOps pipeline file structure, layout, and formatting standards       |
| `format-gha-pipelines` | GitHub Actions workflow file structure, layout, and formatting standards     |

**Generate**

| Skill                    | Purpose                                               |
| ------------------------ | ----------------------------------------------------- |
| `generate-diagram`       | Mermaid architecture diagrams from IaC/code           |
| `generate-cost-estimate` | Azure cost estimate from IaC                          |
| `generate-readme`        | Brief project README from code and standards template |

**Create**

| Skill           | Purpose                             |
| --------------- | ----------------------------------- |
| `create-pr-ado` | Create an Azure DevOps pull request |
| `create-pr-gh`  | Create a GitHub pull request        |

**Config**

| Skill             | Purpose                            |
| ----------------- | ---------------------------------- |
| `config-repo-ado` | Standard ADO repo configuration    |
| `config-repo-gh`  | Standard GitHub repo configuration |

**Git**

| Skill             | Purpose                                    |
| ----------------- | ------------------------------------------ |
| `git-cleanup`     | Delete merged branches, prune remotes      |
| `git-commit-push` | Stage, commit, and push with safety checks |

**Microsoft Foundry**

| Skill               | Purpose                                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `microsoft-foundry` | Full Foundry agent lifecycle: deploy, invoke, observe, evaluate, optimize prompts, manage models/quota/RBAC, and provision projects |

**Other**

| Skill   | Purpose                                                |
| ------- | ------------------------------------------------------ |
| `learn` | Quiz on recent code changes to reinforce understanding |

## Common Tasks

### Adding a new skill

Create `skills/<name>/SKILL.md` with the frontmatter and prompt body, then commit and push.

Existing skill edits are immediately available on linked machines after a `git pull`. When adding a new top-level skill folder, re-run `.\scripts\Install-DeveloperConfig.ps1` so Codex gets a new per-skill junction under `~/.codex/skills/<name>`. Claude uses a whole-directory `~/.claude/skills` junction and sees new folders immediately.

### Setting up a new device

Clone the repo and run the install script (Windows):

```powershell
git clone https://github.com/liam-goodchild/ops-developer-config.git "C:\Local Files\Repositories\Sky Haven\ops-developer-config"
cd "C:\Local Files\Repositories\Sky Haven\ops-developer-config"
.\scripts\Install-DeveloperConfig.ps1
```

The script creates junctions for directories and file symlinks where possible.
Codex skills are linked under `~/.codex/skills`; the legacy `~/.agents/skills`
path is cleaned up only when it is the old junction to this repo.
On domain-joined machines where Group Policy blocks symlink creation, it falls
back to file copies and prints a reminder — run `.\scripts\Install-DeveloperConfig.ps1` again
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

Defines globally allowed tools. When adding new MCP tool permissions, add them to the `allow` array. The `deny` array is currently empty — prefer allowlist-only control.

Plugins (marketplace and official) are configured under `enabledPlugins` — these are not synced via git and must be installed per-device.

## git/hooks/

Global git hooks wired via `git config --global core.hooksPath`. Applied to every repo on the machine. The `pre-commit` hook auto-formats staged files before each commit:

- **`.tf` / `.tfvars`** — runs `terraform fmt -recursive`
- **`.yaml` / `.yml` / `.json`** — runs `prettier --write`, using `.github/linters/.prettierrc.json` if present

Both formatters re-stage the files they modify. Formatting errors are non-fatal (the commit proceeds).

## Code Style

These conventions apply across all IaC and scripting work in connected repositories:

- **Terraform**: 2-space indent, explicit provider versions, use `for_each` instead of `count` for resource toggling
- **Shell**: Bash with `set -euo pipefail`; quote all variable expansions; prefer idempotent operations
- **YAML / JSON**: 2-space indent, no trailing whitespace
