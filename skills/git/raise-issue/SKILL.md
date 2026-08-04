---
name: raise-issue
description: Open Backlog to prepare and raise a GitHub issue or Azure DevOps work item
disable-model-invocation: true
---

Use the Backlog application for all new GitHub issues and Azure DevOps work
items. Backlog owns destination discovery, classification, refinement, canonical
template loading, review, and provider submission.

Open:

<https://backlog.lab.skyhaven.ltd>

In the application:

1. Select GitHub or Azure DevOps.
2. Select the repository or project from the live destination list.
3. Enter the requested outcome and prepare the draft.
4. Review the generated title, description, acceptance criteria, and metadata.
5. Submit the item only after the user has approved the draft.

Do not invoke `gh issue create`, `az boards work-item create`, or another direct
provider API as a fallback. If a destination or canonical template cannot be
loaded, report the application error. Provider credentials are managed by the
application and must not be requested from the user.

Report the created item link shown by Backlog.
