---
name: create-pr-ado
description: Create an Azure DevOps pull request for the current branch
---

PR templates live in the `liam-goodchild/.github` repo at `.github/PULL_REQUEST_TEMPLATE/`.

1. `git branch --show-current` + `az repos show --query defaultBranch -o tsv | sed 's|refs/heads/||'`. If on default branch, STOP.

2. Check existing PR: `az repos pr list --source-branch $(git branch --show-current) --status active`. If exists → output URL, STOP.

3. Push if needed: if `git log origin/{branch}..HEAD` shows unpushed commits → `git push origin HEAD`.

4. Map branch prefix → title prefix + template. If branch has work item number (e.g. `feature/12345-thing`) → `--work-items 12345`.

   | Branch prefix | Title prefix | Template |
   |---|---|---|
   | `feature/` | `[FEATURE]` | `feature.md` |
   | `major/` / `breaking/` | `[MAJOR]` | `feature.md` |
   | `fix/` / `hotfix/` / `bug/` | `[PATCH]` | `bug_fix.md` |
   | `minor/` / `patch/` / `chore/` / `docs/` | `[MINOR]` | `maintenance.md` |

   If unclear, ask.

5. `git diff {default}...HEAD` → derive brief title (<60 chars after prefix).

6. Fill the selected template body with content derived from the diff:

   **feature.md**
   ```
   **What does this PR do?**
   <description>

   **Related issue**
   Closes #

   **Testing done**
   <testing>

   **Checklist**
   - [ ] Code follows project conventions
   - [ ] No secrets or credentials included
   ```

   **bug_fix.md**
   ```
   **What is the bug?**
   <description>

   **Root cause**
   <root cause>

   **Related issue**
   Fixes #

   **Testing done**
   <testing>

   **Checklist**
   - [ ] Root cause identified and addressed
   - [ ] No secrets or credentials included
   ```

   **maintenance.md**
   ```
   **What does this PR change?**
   <description>

   **Why?**
   <reason>

   **Related issue**
   Closes # (if applicable)

   **Checklist**
   - [ ] No functional behaviour changed
   - [ ] No secrets or credentials included
   ```

7. Create PR:

```
az repos pr create --target-branch {default} --title "<PREFIX> - <title>" --description "<filled template body>"
```

8. Extract `pullRequestId`, `repository.name`, `repository.project.name` from response. Output URL: `https://dev.azure.com/CloudAandE/{project}/_git/{repo}/pullrequest/{id}`
