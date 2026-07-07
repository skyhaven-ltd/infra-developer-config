# Codex Global Guidance

This file is installed to `~/.codex/AGENTS.md` by
`scripts/Install-DeveloperConfig.ps1`. Skills are installed under
`~/.codex/skills/<name>/SKILL.md`.

## Git and work-item workflow

Always use these skills for these operations — never raw `git commit`,
`git push`, `gh pr create`, or direct issue creation:

| Operation                                            | Skill             |
| ---------------------------------------------------- | ----------------- |
| Commit and push changes                              | `git-commit-push` |
| Create a pull request                                | `create-pr`       |
| Clean up git state (merged branches, prune remotes)  | `git-cleanup`     |
| Raise a GitHub issue or other work item              | `raise-issue`     |

Invocation: the user types the skill name (e.g. `$create-pr`) or asks for it
by name; the agent reads and follows `~/.codex/skills/<name>/SKILL.md`.
Example: asked to "commit and push this", follow
`~/.codex/skills/git-commit-push/SKILL.md` — do not run `git commit`
yourself.

Scope: these skills are only for the mutating operations above. Read-only
git inspection (`git status`, `git log`, `git diff`, `git blame`, branch
listing) is normal tool use — do not invoke a skill for it. Never perform
the mutating operations without the matching skill.
