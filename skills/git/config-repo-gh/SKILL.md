---
name: config-repo-gh
description: Configure a GitHub repository — default branch, security settings, branch ruleset, rename, and README generation. Can create the repo from scratch.
---

Configure a GitHub repo using `gh` CLI. Work through steps in order, confirm each before proceeding.

## Step 0 — Prerequisites & Init

**0a — Auth:** `gh auth status`. If not authenticated → tell user to run `! gh auth login`.

**0b — Repo state:** `git remote get-url origin 2>/dev/null`. If remote exists → resolve `{owner}/{repo}` from URL, skip to Step 1. If no remote → continue.

**0c–0d — Init:** `git init` if needed, then `git branch -m main`.

**0e — Create remote:** Ask user for public/private (default: private) and org/owner (default: authenticated user).

```bash
gh repo create {owner}/{repo} --public --source=. --remote=origin
```

**0f — Push:** `git commit --allow-empty -m "chore: initialise repository"` then `git push -u origin main`.

**0g — Working branch:** `git checkout -b major/initial-design`. All file changes happen on this branch from here.

## Step 1 — Default Branch

```bash
gh api repos/{owner}/{repo} --method PATCH --field default_branch=main \
  --field allow_squash_merge=true \
  --field allow_merge_commit=false \
  --field allow_rebase_merge=false
```

If `main` doesn't exist, STOP.

## Step 2 — Security Features

```bash
gh api repos/{owner}/{repo}/private-vulnerability-reporting --method PUT
gh api repos/{owner}/{repo}/vulnerability-alerts --method PUT
gh api repos/{owner}/{repo}/automated-security-fixes --method PUT
gh api repos/{owner}/{repo} --method PATCH --input - <<'EOF'
{
  "security_and_analysis": {
    "secret_scanning": {"status": "enabled"},
    "secret_scanning_push_protection": {"status": "enabled"}
  }
}
EOF
```

Note any features unavailable on current plan and explain why.

## Step 3 — Branch Ruleset

Check for existing ruleset first:

```bash
gh api repos/{owner}/{repo}/rulesets --jq '.[] | select(.name=="main-branch-protection") | .id'
```

If exists → `PATCH` to that ID. Otherwise `POST`:

```bash
gh api repos/{owner}/{repo}/rulesets --method POST --input - <<'EOF'
{
  "name": "main-branch-protection",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "exclude": [], "include": ["~DEFAULT_BRANCH"] }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "required_reviewers": [],
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["squash"]
      }
    }
  ],
  "bypass_actors": []
}
EOF
```

## Step 4 — Repository Name

Ask user what repo will contain (if not clear). Fetch naming convention:

```bash
gh api repos/liam-goodchild/docs-engineering-standards/contents/standards/repo-naming.md --jq '.content' | base64 -d
```

Suggest 3 names ranked by fit. Wait for confirmation, then:

```bash
gh api repos/{owner}/{repo} --method PATCH --field name={confirmed-new-name}
```

## Step 5 — README

Run the `/generate-readme` skill. Only proceed once user confirms code is in working state.

## Step 6 — Labels

Delete all default GitHub labels and create the single standard label. Repos use the project board's **Type** field (Feature/Bug) instead of labels.

```bash
# Delete all existing labels
"/c/Program Files/GitHub CLI/gh.exe" label list --repo {owner}/{repo} --json name -q '.[].name' | \
  while IFS= read -r label; do
    "/c/Program Files/GitHub CLI/gh.exe" label delete "$label" --repo {owner}/{repo} --yes
  done

# Create the single standard label
"/c/Program Files/GitHub CLI/gh.exe" label create "use-type-field-instead" \
  --repo {owner}/{repo} \
  --color "EDEDED" \
  --description "Use the Type field on the project board instead"
```

## Step 7 — Link to Sky Haven Project Board

Link repo to the Sky Haven Project Board using GraphQL. Requires `read:project` scope (`gh auth refresh -s read:project` if missing).

Get project node ID (project number = 1, owner = liam-goodchild):

```bash
"/c/Program Files/GitHub CLI/gh.exe" api graphql -f query='
  query {
    user(login: "liam-goodchild") {
      projectV2(number: 3) {
        id
        title
      }
    }
  }
'
```

Confirm title is "Sky Haven Project Board". Then get repo node ID and link it:

```bash
REPO_ID=$("/c/Program Files/GitHub CLI/gh.exe" api repos/{owner}/{repo} --jq '.node_id')
PROJECT_ID="<id from above>"

"/c/Program Files/GitHub CLI/gh.exe" api graphql -f query='
  mutation($projectId: ID!, $repoId: ID!) {
    linkProjectV2ToRepository(input: { projectId: $projectId, repositoryId: $repoId }) {
      repository { nameWithOwner }
    }
  }
' -f projectId="$PROJECT_ID" -f repoId="$REPO_ID"
```
