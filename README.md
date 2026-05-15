# ops-developer-config

Shared developer configuration for Claude Code, Codex CLI, VS Code, Git, and reusable Codex/Claude skills. It keeps machine setup and day-to-day repository maintenance consistent by storing tool settings, hooks, skills, and helper scripts in one source-controlled place.

Skills are grouped by purpose under `skills/`. Any descendant folder that contains
`SKILL.md` is installed flat into both `~/.claude/skills` and `~/.codex/skills`
by `scripts/Install-DeveloperConfig.ps1`.
