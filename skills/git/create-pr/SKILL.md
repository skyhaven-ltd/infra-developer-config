---
name: create-pr
description: Create a pull request for the current branch on GitHub or Azure DevOps
---

Create a pull request for the current branch. The helper detects whether the repository is hosted on **GitHub** (via `gh`) or **Azure DevOps** (via `az`) from its `origin` remote and dispatches to the right backend. Use the bundled Python helper for deterministic VCS detection, branch, default branch, existing PR, shared template, and diff-stat checks. Use the LLM only for judgement: drafting the concise PR title/body from the diff, confirming the VCS when it cannot be inferred, and asking when the branch prefix is unclear.

## Step 1 — Inspect

Run from inside the target repository (pass `--target "."`):

```powershell
python "<skill-dir>\scripts\create-pr-helper.py" inspect --target "." --json
```

Inspect these fields:

- `vcs`: `github`, `ado`, or `null`. If `null` (risk flag `vcs_not_detected`), ask the user which VCS to use and pass it as `vcs` in the plan, or fix the `origin` remote.
- Stop if `on_default_branch` is true or `existing_pull_requests` is non-empty.
- Ask the user if `branch_prefix_unclear` appears in `risk_flags`. Branches must be prefixed `patch/`, `minor/`, or `major/` (also accepted: `feature/`, `fix/`, `chore/`, `docs/`).
- `branch_mapping.title_prefix` is derived from the branch type (`patch/foo` -> `[PATCH]`, `minor/foo` -> `[MINOR]`, `major/foo` -> `[MAJOR]`). The PR title must start with it.
- `pull_request_template`: the shared template at `.github/.github/PULL_REQUEST_TEMPLATE/pull-request.md`. Do not invent or use embedded templates.

## Step 2 — Draft and confirm

Draft the title (with the prefix) and a body based on the shared template. Show them to the user and only set `approved: true` after explicit approval.

## Step 3 — Plan

Create a plan JSON outside the repo (for example under `$env:TEMP`). `vcs` is optional — include it only when detection is ambiguous.

GitHub:

```json
{
  "vcs": "github",
  "repository": "owner/repo",
  "base": "main",
  "title": "[MINOR] - Short title",
  "body": "Markdown PR body",
  "approved": true
}
```

Azure DevOps:

```json
{
  "vcs": "ado",
  "ado": { "org": "Org", "project": "Project", "repo": "repo" },
  "base": "main",
  "title": "[MINOR] - Short title",
  "body": "Markdown PR body",
  "work_items": [],
  "approved": true
}
```

`repository` / `ado` are inferred from `origin` when omitted. For Azure DevOps, `base` is the target branch and `work_items` links work items.

## Step 4 — Dry-run, then create

```powershell
python "<skill-dir>\scripts\create-pr-helper.py" apply --target "." --plan "$env:TEMP\pr.json" --dry-run
python "<skill-dir>\scripts\create-pr-helper.py" apply --target "." --plan "$env:TEMP\pr.json"
```

Always run with `--target` pointing at the repository (the helper resolves the head branch and runs the VCS CLI with that directory as its working directory).

## Step 5 — Report

Report `created_pr_url` (GitHub) or `url` (Azure DevOps). If the helper fails, report the concise JSON error and the safest next action.
