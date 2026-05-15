---
name: raise-bug
description: Raise a bug report issue on a GitHub repository using the standard bug template
---

Raise a GitHub bug report issue on a repository. Follow this process exactly.

## Step 1 — Gather information

Ask the user for any missing details:

- **Repository**: which GitHub repo (e.g. `liam-goodchild/my-repo`)? If the working directory is a git repo, infer from `git remote get-url origin`.
- **Title**: a short description of the bug (will be prefixed with `[BUG] - `)
- **Describe the bug**: what is happening?
- **Steps to reproduce**: numbered steps to trigger the bug
- **Expected behavior**: what should happen instead?

Do not proceed until you have enough to fill all three body sections meaningfully. If the user provides a terse description, expand it into the template structure — do not ask for every field individually if context makes them inferable.

## Step 2 — Confirm before creating

Show the user the full issue title and body for review before creating. Wait for explicit approval.

## Step 3 — Create the issue

Use the `gh` CLI. On Windows the binary is at `/c/Program Files/GitHub CLI/gh.exe`.

Body follows the bug report template from `liam-goodchild/.github` at `.github/ISSUE_TEMPLATE/bug_report.md`.

```bash
"/c/Program Files/GitHub CLI/gh.exe" issue create \
  --repo "<owner>/<repo>" \
  --title "[BUG] - <title>" \
  --label "use-type-field-instead" \
  --assignee "liam-goodchild" \
  --body "$(cat <<'EOF'
**Describe the bug**
<description>

**To Reproduce**
Steps to reproduce the behavior:

<steps>

**Expected behavior**
<expected>
EOF
)"
```

## Step 4 — Set Type field on project board

After the issue is created, set the **Type** field to **Bug** on the Sky Haven Project Board. Find the item by issue node ID and update the single-select field `PVTSSF_lAHOB9ID-s4BU_KBzhRbk2o` to option ID `951d9251` (Bug).

```bash
ISSUE_ID=$("/c/Program Files/GitHub CLI/gh.exe" api repos/<owner>/<repo>/issues/<number> --jq '.node_id')

"/c/Program Files/GitHub CLI/gh.exe" api graphql -f query='
  mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $projectId
      itemId: $itemId
      fieldId: $fieldId
      value: { singleSelectOptionId: $optionId }
    }) { projectV2Item { id } }
  }
' -f projectId="PVT_kwHOB9ID-s4BU_KB" \
  -f itemId="$ISSUE_ID" \
  -f fieldId="PVTSSF_lAHOB9ID-s4BU_KBzhRbk2o" \
  -f optionId="951d9251"
```

Note: the issue must already be linked to the project board (added as an item) for this to work. If not, add it first via `addProjectV2ItemById`.

## Step 5 — Report back

Print the URL of the created issue.
