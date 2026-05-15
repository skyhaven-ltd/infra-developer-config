---
name: git-cleanup
description: Checkout default branch, delete merged local branches, prune remotes, and pull latest
---

Run in sequence:

```
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@') || DEFAULT="main"
git checkout "$DEFAULT"
git fetch --prune --prune-tags
git branch | grep -Ev '^\*|^\s+(main|master)$' | xargs -r git branch -D
git tag | xargs -r git tag -d
git pull
```

List deleted branches and tags.
