---
name: config-repo-ado
description: Configure an Azure DevOps repository — default branch, branch policies, Advanced Security, rename, and README generation. Can create the repo from scratch.
---

Configure an Azure DevOps repo using `az` CLI. Work through steps in order, confirm each before proceeding. Org URL format: `https://dev.azure.com/{org}`.

## Step 0 — Prerequisites & Init

**0a — Auth:** Run `az account show`. If not authenticated → tell user to run `! az login`. Verify `az extension show --name azure-devops` (if missing → `! az extension add --name azure-devops`).

**0b — Repo state:** `git remote get-url origin 2>/dev/null`. If remote exists → resolve `{org}`, `{project}`, `{repo}` from URL, skip to Step 1. If no remote → continue.

**0c–0d — Init:** `git init` if needed, then `git branch -m main`.

**0e — Create remote:** Ask user for org + project.

```bash
az repos create --org "https://dev.azure.com/{org}" --project "{project}" --name "{repo}"
git remote add origin "https://dev.azure.com/{org}/{project}/_git/{repo}"
```

**0f — Push:** `git commit --allow-empty -m "chore: initialise repository"` then `git push -u origin main`.

**0g — Working branch:** `git checkout -b major/initial-design`. All file changes happen on this branch from here.

## Step 1 — Default Branch

```bash
az repos update --org "https://dev.azure.com/{org}" --project "{project}" --repository "{repo}" --default-branch main
```

If `main` doesn't exist, STOP.

## Step 2 — Advanced Security

Get repo ID: `az repos show --org "https://dev.azure.com/{org}" --project "{project}" --repository "{repo}" --query id -o tsv`

```bash
az rest --method PATCH \
  --url "https://advsec.dev.azure.com/{org}/{project}/_apis/management/repositories/{repoId}/enablement?api-version=7.2-preview.1" \
  --body '{"isEnabled": true}'
```

If GHAzDo licence unavailable, report to user.

## Step 3 — Branch Policies on `main`

Get project ID: `az devops project show --org "https://dev.azure.com/{org}" --project "{project}" --query id -o tsv`

**3a — Min reviewers:**

```bash
az rest --method POST \
  --url "https://dev.azure.com/{org}/{project}/_apis/policy/configurations?api-version=7.1" \
  --body '{
    "isEnabled": true, "isBlocking": true,
    "type": { "id": "fa4e907d-c16b-452d-8106-7efa0cb84489" },
    "settings": {
      "minimumApproverCount": 1, "creatorVoteCounts": false,
      "allowDownvotes": false, "resetOnSourcePush": false,
      "scope": [{ "repositoryId": "{repoId}", "refName": "refs/heads/main", "matchKind": "exact" }]
    }
  }'
```

**3b — Block direct pushes (require PRs):**

```bash
az rest --method POST \
  --url "https://dev.azure.com/{org}/{project}/_apis/policy/configurations?api-version=7.1" \
  --body '{
    "isEnabled": true, "isBlocking": true,
    "type": { "id": "17c08c16-8094-4537-824c-4a6a9cfd0cb9" },
    "settings": {
      "allowAdminsBypass": false,
      "scope": [{ "repositoryId": "{repoId}", "refName": "refs/heads/main", "matchKind": "exact" }]
    }
  }'
```

**3c — Linked work item:** optional, ask user.
**3d — Required build:** optional, ask user for build definition ID.

## Step 4 — Repository Name

Ask user what repo will contain (if not clear). Fetch naming convention:

```bash
gh api repos/liam-goodchild/docs-engineering-standards/contents/standards/repo-naming.md --jq '.content' | base64 -d
```

Suggest 3 names ranked by fit. Wait for confirmation, then:

```bash
az repos update --org "https://dev.azure.com/{org}" --project "{project}" --repository "{repo}" --name "{confirmed-new-name}"
```

## Step 5 — README

Run the `/generate-readme` skill. Only proceed once user confirms code is in working state.
