---
name: raise-issue
description: Raise a classified GitHub issue (bug, feature, or task) with the right template, native issue type, and project board link
---

Raise a GitHub issue. The LLM classifies the user's request as a **bug**, **feature**, or **task**, decides whether it should be broken into **sub-issues**, and drafts meaningful prose. The bundled Python helper does the deterministic work: loading the matching shared template, creating the issue, setting the native (root-level) GitHub issue type, adding it to the Sky Haven Project Board, and linking any sub-issues.

## Step 1 — Inspect

Run from inside the target repository:

```powershell
python "<skill-dir>\scripts\raise-issue-helper.py" inspect --target "." --json
```

- `inferred_repository`: use it if correct, otherwise ask for `owner/repo`.
- `risk_flags`: resolve `repository_not_inferred`, `gh_not_found`, `gh_not_authenticated`, or `issue_template_not_found` before applying.
- `kinds` / `templates_found`: the three supported kinds and whether each template resolves.
- `project`: the board id and the native issue type set per kind.

## Step 2 — Classify, draft, and decide breakdown

1. **Classify** the request as `bug`, `feature`, or `task`:
   - `bug` — something is broken or behaving incorrectly.
   - `feature` — new functionality or an enhancement.
   - `task` — a unit of work or chore that is neither of the above.
2. **Draft** the kind-specific fields (expand terse input into meaningful prose):
   - `feature`: `problem`, `solution`
   - `bug`: `description`, `steps`, `expected`
   - `task`: `what`, `why`, and optional `acceptance` (a list of criteria)
3. **Decide sub-issues**: if the request is really several pieces of work, break it into a parent plus `sub_issues`, each independently classified. Keep a single issue when the work is cohesive.

Show the title(s) and body(ies) to the user. Only set `approved: true` after explicit approval.

## Step 3 — Plan

Create a plan JSON outside the repo (for example under `$env:TEMP`). `repository` is inferred from `origin` when omitted.

```json
{
  "repository": "owner/repo",
  "kind": "feature",
  "title": "Short title",
  "problem": "Meaningful problem statement.",
  "solution": "Meaningful desired solution.",
  "approved": true,
  "sub_issues": [
    { "kind": "task", "title": "First slice", "what": "...", "why": "..." },
    { "kind": "bug", "title": "Fix the broken bit", "description": "...", "steps": "1. ...", "expected": "..." }
  ]
}
```

Each sub-issue takes the same kind-specific fields as a top-level issue. Omit `sub_issues` for a single issue. `assignee` is optional (defaults to the repository convention).

## Step 4 — Dry-run, then create

```powershell
python "<skill-dir>\scripts\raise-issue-helper.py" apply --target "." --plan "$env:TEMP\issue.json" --dry-run
python "<skill-dir>\scripts\raise-issue-helper.py" apply --target "." --plan "$env:TEMP\issue.json"
```

The helper validates the parent and every sub-issue before any side effects. For each issue it: creates it with `gh issue create`, sets the **native GitHub issue type** (`Bug`/`Feature`/`Task`) on the issue itself, and adds it to the Sky Haven Project Board. Classification lives on the native issue type — the helper does not apply classification labels. Sub-issues are linked to the parent via the GitHub sub-issues API.

## Step 5 — Report

Report `created_issue_url` and any `sub_issues[].url`. If a sub-issue link fails (`linked: false`), surface `link_error`. If the helper fails, report the concise JSON error and the safest next action.
