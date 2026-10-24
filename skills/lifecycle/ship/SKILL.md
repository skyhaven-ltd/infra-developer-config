---
name: ship
description: Ship a reviewed task. Only after a GO in REVIEW.md, push the task branch and open a pull request, then record it in SHIP.md.
disable-model-invocation: true
---

# Ship

Publish a reviewed branch as a pull request. This phase posts to a remote, so it runs only when the user types `/ship`.

## Find the task

1. Run `git branch --show-current`, `git status` and `git remote -v`.
2. Pick the `.agents/NNN - Name/` folder whose CYCLE.md has a `branch:` line matching the current branch.
3. Otherwise use the only folder whose CYCLE.md has unticked phases. If several are open, ask which one.

## Reads

- CYCLE.md for the branch and phases.
- REVIEW.md for the verdict, the reviewed HEAD and the rollback plan.
- SCOPE.md for the objective and acceptance criteria. Bug and small work may have only BUILD.md.
- `git log --oneline base..HEAD`.

## Steps

### 1. Gate

Stop and say why if any of these is true:

- REVIEW.md is missing or its verdict is not `GO`.
- HEAD has commits after the reviewed HEAD in REVIEW.md. Run `/review` again.
- The working tree is not clean, or the branch name does not start with `patch/`, `minor/` or `major/`.
- The current branch is the base branch.

### 2. Push

1. Push the branch with upstream tracking: `git push -u origin <branch>`.
2. Never force push unless the user asks for it in this session.

### 3. Open the pull request

Pick the tool from the `origin` URL:

| Remote | Tool |
| --- | --- |
| `github.com` | the GitHub MCP `create_pull_request` tool, with `base`, `head`, `title` and `body` |
| `dev.azure.com` or `visualstudio.com` | the Azure DevOps MCP pull request tools |

If a pull request for the branch already exists, update its description instead of opening another.

Write the title from the objective, in plain words. Write the body:

```markdown
## What
One or two sentences from the objective.

## Why
The problem it solves.

## Changes
- Main changes, grouped by area.

## Verification
- Tests and checks from REVIEW.md, with results.

## Rollback
- Steps from REVIEW.md.
```

The title, body and any comments never mention AI tools or say the change was generated. Do not add attribution footers.

### 4. Confirm

Read back the PR URL and check that it targets the right base branch.

## Writes

`.agents/NNN - Name/SHIP.md`:

```markdown
# Ship: Name

- Branch: minor/name
- Base: main
- Commits: abc1234..def5678 (n commits)
- Pull request: URL
- Shipped: YYYY-MM-DD
- Rollback: one line, or "see REVIEW.md"
```

## Exit

1. Save SHIP.md.
2. Tick `- [x] ship` in CYCLE.md. Do this last.
3. Print the PR URL and the remaining steps for the user, such as approvals and merge.

## Rules

- Never merge, delete branches, or change branch policies.
- Never push to the base branch.
- If a push or PR command fails, show the error and stop. Do not retry with different flags or force.
