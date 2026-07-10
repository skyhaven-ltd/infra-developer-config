---
name: git-cleanup
description: Remove local branches safely stored on origin and delete all local tags
---

Use the installed `git clear` command. It deletes a local branch only when a
same-named branch exists on `origin` and the local branch has no commits absent
from that remote branch. It deletes all local tags because tags are managed by
CI/CD on the remote.

1. Show the deterministic dry run:

   ```powershell
   git clear
   ```

2. Explain the branches and tags that will be deleted, then continue without
   prompting for approval and apply the freshly recalculated plan:

   ```powershell
   git clear --apply
   ```

3. Report the deleted and retained refs. If the command refuses because of
   local changes or local-only commits, report that rather than bypassing the
   safety check.
