---
name: git-commit-push
description: Stage, commit, and push changes to origin
---

You have EXPLICIT authorisation to stage, commit, and push.

1. `git branch --show-current` — if on `main`/`master`, STOP. Tell user to switch to feature branch. If within a `ops-developer-config` directory, you have explicit permission to proceed on `main`/`master`.

2. `git status` + `git diff` — if no changes, STOP. Flag secrets/binaries/`.env` and ask before proceeding.

3. If ≤3 changed files → single commit. If >3 → group logically, one commit per group. Do NOT wait for confirmation.

4. Per group: `git add <files>`, then commit. Messages: short sentence, no prefixes, no trailing period, <72 chars. HEREDOC format. Do NOT add any Co-Authored-By trailer.

5. `git push origin HEAD` (or `git push -u origin $(git branch --show-current)` if no upstream). Do NOT ask — always push. Report result.
