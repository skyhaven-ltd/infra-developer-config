---
name: git-cleanup
description: Checkout default branch, delete merged local branches, prune remotes, and pull latest
---

Use the bundled Python helper for deterministic branch/tag discovery and Git command execution. Use the LLM only for judgement: explaining the deletion plan and obtaining confirmation before local deletes.

1. Inspect the repository:

   ```powershell
   python "<skill-dir>\scripts\git-cleanup-helper.py" inspect --target "." --json
   ```

2. Show `default_branch`, `deletable_branches`, and `deletable_tags`. Because local branch/tag deletion is destructive, continue only with explicit approval.

3. Create a plan outside the repo:

   ```json
   {
     "delete_branches": ["old-branch"],
     "delete_tags": ["old-tag"],
     "pull": true,
     "approved": true
   }
   ```

4. Dry-run, then apply:

   ```powershell
   python "<skill-dir>\scripts\git-cleanup-helper.py" apply --target "." --plan "$env:TEMP\git-cleanup.json" --dry-run
   python "<skill-dir>\scripts\git-cleanup-helper.py" apply --target "." --plan "$env:TEMP\git-cleanup.json"
   ```

5. Report deleted branches, deleted tags, fetch/prune, and pull results.
