---
name: review-pull-request
description: Review an open pull request for code quality, security, and IaC best practices
---

You are reviewing a pull request. The user will provide a PR number/URL as an argument (e.g., `/pr-review 123` or `/pr-review https://dev.azure.com/.../pullrequest/3420`), or you should review the PR for the current branch.

## Steps

1. **Extract PR number/URL from arguments.**
   - If the user provided arguments, parse them:
     - If it's a number (e.g., `123`): use it as the PR number
     - If it's an Azure DevOps URL: extract the PR ID from the URL path (e.g., `/pullrequest/3420` → `3420`)
     - If it's a GitHub URL: extract the PR number from the URL (e.g., `/pull/123` → `123`)
   - If no arguments provided, proceed to find the PR for the current branch.

2. **Determine repo type and get PR metadata.**
   - Run `git remote get-url origin` to detect Azure DevOps vs GitHub
   - **For both GitHub and ADO, use git commands** — more reliable than CLI tools which can have parameter issues:
     - Run `git fetch origin refs/pull/{number}/merge` to fetch the PR merge commit
     - Run `git log FETCH_HEAD^..FETCH_HEAD --oneline` to get the commit message (contains PR title)
   - Optional: For GitHub, you can also use `gh pr view {number}` for richer metadata (description, reviewers, etc.)
   - Optional: For ADO, avoid `az repos pr show` — it has parameter naming issues with spaces in project/repo names
   - Otherwise, try to find the PR for the current branch. If no PR exists, STOP.

2. **Check diff size upfront** — run `git diff --stat {base}..{head}` to see file count and total line changes.
   - **If diff < 100 lines:** Proceed with full review
   - **If diff 100–500 lines:** Review all files normally
   - **If diff > 500 lines:** Ask user for guidance: "This diff is large (X files, Y lines). Review (a) all files, (b) only code files (skip XML/YAML metadata), or (c) specific areas?" OR intelligently prioritize: scan all files briefly, flag scope creep (title/description mismatch), then deep-dive on code-heavy files.

3. **Get the diff** using git commands (works for both ADO and GitHub):
   ```bash
   git fetch origin {pr_branch} 2>/dev/null || git fetch origin {source_ref}
   git diff --no-color {base}..{fetched_ref} > /tmp/diff.txt
   ```
   Stream the diff in chunks if it's very large; focus on high-risk areas first (*.js, *.py, *.ts security issues before *.xml metadata).

4. **Review the diff** across these areas. Only comment on things that matter — skip nitpicks and style opinions.

   **Scope & Intent:** Does the diff match the PR title/description? Flag scope creep (unrelated major refactors bundled in).

   **Correctness:** Logic errors, off-by-one, null handling, missing edge cases, broken error propagation.

   **Security:** Secrets in code, injection vectors, auth gaps, overly permissive access. Apply the same lens as the security-engineer skill but scoped to the diff.

   **IaC (if applicable):** Hardcoded values that should be parameters, missing tags, public access where private is expected, missing diagnostic settings.

   **Testing:** Are new code paths covered? Are existing tests broken by the change?

5. **Output format** — keep it concise:

   ```
   ## PR Review: #{number} — {title}

   ### Must Fix
   - **[file:line]** Issue description → suggested fix

   ### Should Fix
   - **[file:line]** Issue description → suggested fix

   ### Looks Good
   - Brief note on what's well done (1-2 lines max)
   ```

6. If the user asks, post the review as a PR comment:
   - For GitHub: Use `gh pr review {number} --comment --body "..."`
   - For ADO: Use `az repos pr update --id {number} --discussion` or similar commands, but note that the az CLI can be unreliable with complex arguments — prefer the web URL or git-based approaches if available.

## Parsing PR argument examples

When the user provides an argument, extract the PR number as follows:

```bash
# Plain number: /pr-review 123
PR_ARG="123"
PR_NUM=$PR_ARG

# Azure DevOps URL: /pr-review https://dev.azure.com/CloudAandE/.../pullrequest/3420
PR_ARG="https://dev.azure.com/CloudAandE/.../pullrequest/3420"
PR_NUM=$(echo "$PR_ARG" | grep -oP 'pullrequest/\K[0-9]+')

# GitHub URL: /pr-review https://github.com/owner/repo/pull/123
PR_ARG="https://github.com/owner/repo/pull/123"
PR_NUM=$(echo "$PR_ARG" | grep -oP 'pull/\K[0-9]+')
```

If argument parsing fails or returns empty, ask the user to provide a valid PR number or URL.
