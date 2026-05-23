---
name: raise-feature
description: Raise a feature request issue on a GitHub repository using the standard feature template
---

Raise a GitHub feature request issue on a repository. Use the bundled Python helper for deterministic checks, shared issue template loading, and execution. Use the LLM only for judgement: understanding the user's request, expanding terse details into meaningful template prose, deciding whether enough information is present, and confirming the exact issue with the user before creation.

## Step 1 — Inspect repository and tooling

Run the helper from the current working directory or target repository directory:

```powershell
python "C:\Local Files\Repositories\Sky Haven\ops-developer-config\skills\git\raise-feature\scripts\raise-feature-helper.py" inspect --target "." --json
```

Inspect these JSON fields:

- `inferred_repository`: use this if it is correct; otherwise ask for `owner/repo`.
- `risk_flags`: stop and resolve `repository_not_inferred`, `gh_not_found`, or `gh_not_authenticated` before applying.
- `issue_template`: the shared template loaded from `.github/.github/ISSUE_TEMPLATE/feature-request.md`. Do not invent or use embedded issue templates.
- `defaults`: label, assignee, and title prefix used by the helper. The helper intentionally defaults `label` to `use-type-field-instead` rather than inheriting semantic labels from the shared issue template.
- `project`: the Sky Haven Project V2 IDs used to set Type to Feature.

## Step 2 — Gather and draft

Ask the user for any missing details:

- **Repository**: which GitHub repo, in `owner/repo` format, unless `inferred_repository` is correct.
- **Title**: a short description of the feature. The helper prefixes it with `[FEATURE] - ` if needed.
- **Problem**: what problem does this feature solve?
- **Solution**: what should happen?

Do not proceed until you have enough to fill both body sections meaningfully. If the user provides a terse description, expand it into the template structure; do not ask for every field individually if context makes them inferable.

The issue body must follow the feature request template:

```markdown
**Is your feature request related to a problem? Please describe.**
<problem>

**Describe the solution you'd like**
<solution>
```

## Step 3 — Confirm before creating

Show the user the full issue title and body for review. Wait for explicit approval before creating a plan with `approved: true`.

Create a plan JSON file outside the target repository, for example in `$env:TEMP`:

```json
{
  "repository": "owner/repo",
  "title": "Short feature title",
  "problem": "Meaningful problem statement.",
  "solution": "Meaningful desired solution.",
  "approved": true
}
```

Optional plan fields are `label` and `assignee`; defaults are `use-type-field-instead` and `liam-goodchild`. Only override `label` for exceptional repositories; normal classification belongs in the GitHub Project Type field.

## Step 4 — Validate or create the issue

Dry-run first when practical:

```powershell
python "C:\Local Files\Repositories\Sky Haven\ops-developer-config\skills\git\raise-feature\scripts\raise-feature-helper.py" apply --target "." --plan "$env:TEMP\feature-plan.json" --dry-run
```

After approval and validation, create the issue:

```powershell
python "C:\Local Files\Repositories\Sky Haven\ops-developer-config\skills\git\raise-feature\scripts\raise-feature-helper.py" apply --target "." --plan "$env:TEMP\feature-plan.json"
```

The helper uses `gh issue create`, adds the created issue to the Sky Haven Project Board, and sets the **Type** field to **Feature** using option ID `c156bb04`.

## Step 5 — Report back

Report the created issue URL from `created_issue_url`. If the helper fails, report the concise JSON error and the safest next action.
