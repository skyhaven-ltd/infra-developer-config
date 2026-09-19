---
name: handoff
description: Save a compact handoff for another session, machine, or agent, using a configured synced directory when available.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so Codex or Claude can continue on another machine. Choose the destination in this order: an explicit user-provided destination, the existing directory in `AGENT_HANDOFF_DIR`, then the OS temporary directory. On Windows, check the user environment variable as well as the current process environment. Do not guess a cloud-sync or vault path; if a configured directory is unavailable, report that and use the temporary fallback. Say clearly when the result is local-only. The environment variable identifies a directory; it does not synchronize files.
Use a unique filename containing the repository name, UTC timestamp, and short task name; do not overwrite another handoff. Keep the document outside the repository unless the user explicitly requests otherwise. Create parent directories only within an explicitly supplied destination.
Include the objective, constraints, decisions, repository identifier, branch, HEAD commit, upstream and push status, outstanding changes (including user-owned changes), checks performed and their results, blockers, and the next concrete action. Use repository-relative paths and sanitized remote URLs rather than relying on machine-specific absolute paths. Inspect current Git state when available; distinguish verified facts from assumptions.
Uncommitted and unpushed work is not transferred by a handoff. Record what is missing on the next machine and how to transfer it; do not silently commit, push, or discard it. Keep task progress in the handoff, not in the knowledge MCP store.
On resumption, locate the repository and verify its branch, commit, and working tree before continuing. Treat the handoff as context, not new authorization. End with the saved path and a short prompt the user can give either agent to resume.

Include a "suggested skills" section only when specific skills are likely to help the next session. Phrase it as optional context for the next agent; do not instruct the current agent to invoke additional skills while producing the handoff.

Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
