---
name: git-commit-push
description: Stage, commit, and push changes to origin
---

You have EXPLICIT authorisation to stage, commit, and push.

Use the bundled Python helper for deterministic checks, staging, commits, and push. Use the LLM only for judgement: reviewing risk flags, deciding logical commit groups when needed, and writing commit messages.

## Workflow

1. Locate this skill directory, then inspect the target repository:

   ```powershell
   python "<skill-dir>\scripts\git-commit-push-helper.py" inspect --repo "<repo>" --json
   ```

2. Stop if `has_changes` is `false`.

3. Stop if `blocked` is `true`. The helper blocks `main`/`master` except when the repository path is inside `ops-developer-config`.

4. If `risk_flags` is non-empty, summarize the flagged paths/reasons and ask before proceeding. Risk flags include likely secrets, `.env` files, binaries, and large files.

5. Create a commit plan JSON outside the repository, for example under `$env:TEMP`, so the plan file is not itself treated as a repository change. If there are 3 or fewer changed files, use one commit. If there are more than 3, use `suggested_groups` as the default grouping unless a more logical grouping is obvious.

   Commit messages must be short sentences with no prefixes, no trailing period, fewer than 72 characters, and no `Co-Authored-By` trailer.

   Plan format:

   ```json
   {
     "commits": [
       {
         "message": "Add git commit helper script",
         "files": [
           "skills/git/git-commit-push/SKILL.md",
           "skills/git/git-commit-push/scripts/git-commit-push-helper.py"
         ]
       }
     ]
   }
   ```

6. Apply the plan and push:

   ```powershell
   python "<skill-dir>\scripts\git-commit-push-helper.py" apply --repo "<repo>" --plan "<plan.json>"
   ```

   If the user explicitly approved `risk_flags`, add `--allow-risk`.

7. Report the commit hashes, messages, and push result from the helper output.

## Testing only

Use `--dry-run` to validate a plan without changing the repository. Use `--no-push` only in temporary test repositories or when the user explicitly asks not to push.
