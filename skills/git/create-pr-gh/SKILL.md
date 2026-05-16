---
name: create-pr-gh
description: Create a GitHub pull request for the current branch
---

Use the bundled Python helper for deterministic branch, default branch, existing PR, shared pull request template, and diff-stat checks. Use the LLM only for judgement: deriving the concise PR title/body from the diff and asking when the branch prefix is unclear.

## Workflow

1. Inspect the current repository:

   ```powershell
   python "<skill-dir>\scripts\create-pr-gh-helper.py" inspect --target "." --json
   ```

2. Stop if `on_default_branch` is true or `existing_pull_requests` is non-empty. Ask if `branch_prefix_unclear` appears in `risk_flags`.

3. Use `branch_mapping` and `pull_request_template` to draft a PR title and body. Only use the shared template at `.github/.github/PULL_REQUEST_TEMPLATE/pull-request.md`; do not invent or use embedded PR templates. Keep the title short and include `branch_mapping.title_prefix`, which is derived from the uppercase branch type (`patch/foo` -> `[PATCH]`, `minor/foo` -> `[MINOR]`, `chore/foo` -> `[CHORE]`).

4. Create an approved plan outside the repo:

   ```json
   {
     "repository": "owner/repo",
     "base": "main",
     "title": "[PATCH] - Short title",
     "body": "Markdown PR body",
     "approved": true
   }
   ```

5. Dry-run, then create:

   ```powershell
   python "<skill-dir>\scripts\create-pr-gh-helper.py" apply --target "." --plan "$env:TEMP\pr-gh.json" --dry-run
   python "<skill-dir>\scripts\create-pr-gh-helper.py" apply --target "." --plan "$env:TEMP\pr-gh.json"
   ```

6. Report `created_pr_url`.
