---
name: create-pr-ado
description: Create an Azure DevOps pull request for the current branch
---

Use the bundled Python helper for deterministic branch, default branch, existing PR, work item, shared pull request template, and diff-stat checks. Use the LLM only for judgement: deriving the concise PR title/description from the diff and asking when the branch prefix is unclear.

## Workflow

1. Inspect the current repository:

   ```powershell
   python "<skill-dir>\scripts\create-pr-ado-helper.py" inspect --target "." --json
   ```

2. Stop if `on_default_branch` is true or `existing_pull_requests` is non-empty. Ask if `branch_prefix_unclear` appears in `risk_flags`.

3. Use `branch_mapping` and `pull_request_template` to draft a PR title and description. Only use the shared template at `.github/.github/PULL_REQUEST_TEMPLATE/pull-request.md`; do not invent or use embedded PR templates. The PR title prefix must be `branch_mapping.title_prefix`, which is derived from the uppercase branch type (`patch/foo` -> `[PATCH]`, `minor/foo` -> `[MINOR]`, `chore/foo` -> `[CHORE]`). If the branch contains a work item number, include it in `work_items`.

4. Create an approved plan outside the repo:

   ```json
   {
     "ado": { "org": "CloudAandE", "project": "Project", "repo": "repo" },
     "target_branch": "main",
     "title": "[PATCH] - Short title",
     "description": "Markdown PR body",
     "work_items": [],
     "approved": true
   }
   ```

5. Dry-run, then create:

   ```powershell
   python "<skill-dir>\scripts\create-pr-ado-helper.py" apply --target "." --plan "$env:TEMP\pr-ado.json" --dry-run
   python "<skill-dir>\scripts\create-pr-ado-helper.py" apply --target "." --plan "$env:TEMP\pr-ado.json"
   ```

6. Report the returned PR URL.
