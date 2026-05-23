---
name: config-repo-gh
description: Configure a GitHub repository — default branch, security settings, branch ruleset, rename, and README generation. Can create the repo from scratch.
---

Use the bundled Python helper for deterministic repository detection, prerequisite checks, and repeatable `gh` operations. Use the LLM only for judgement: confirming user intent, choosing a name, explaining unavailable GitHub features, and deciding README content.

## Workflow

1. Inspect the target repository:

   ```powershell
   python "<skill-dir>\scripts\config-repo-gh-helper.py" inspect --target "." --json
   ```

2. Review `risk_flags`. Stop and resolve `gh_not_found`, `git_not_found`, or `repository_not_inferred`. If there is no remote, ask whether to create one and gather owner, repo, and visibility.

3. Apply configuration only from an explicit approved plan JSON outside the repo:

   ```json
   {
     "repository": "owner/repo",
     "visibility": "private",
     "rename_to": null,
     "link_project": true,
     "approved": true
   }
   ```

4. Dry-run before side effects:

   ```powershell
   python "<skill-dir>\scripts\config-repo-gh-helper.py" apply --target "." --plan "$env:TEMP\config-repo-gh.json" --dry-run
   ```

5. Run apply after confirmation. Then use `/generate-readme` once code is in a working state. Delete default labels and keep `use-type-field-instead` if appropriate for the repo.
