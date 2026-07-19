---
name: process-inbox
description: Process the Obsidian vault inbox (00 - Inbox) into permanent notes following the vault schema. Use when the user asks to process the inbox, triage captures, or file inbox notes.
---

# Process Inbox

Process every note in `00 - Inbox/` of the Obsidian vault (resolve the vault
root from `OBSIDIAN_VAULT_PATH`; if unset, stop and ask the user). The schema
source of truth is `99 - Meta/AI Formatting/LLM Vault Workflow.md` in the
vault; read it first.

## Steps

1. List notes in `00 - Inbox/`. Skip any tagged `pinned` (report them as
   intentionally retained).
2. For each remaining note, decide exactly one action:
   - **merge**: the content belongs in an existing note in `02 - Notes/`.
     Integrate it there and update that note's `modified` date.
   - **promote**: the content stands alone. Create a new note in
     `02 - Notes/` from `99 - Meta/Templates/Note Template.md`.
   - **flag**: the content has no durable value. Do NOT delete; list it for
     the user to approve deletion.
3. Write and validate every merged or promoted note with the write-vault-note
   skill so the schema is enforced deterministically. In addition:
   - Preserve the original `created` date and any source metadata from the
     inbox note.
   - Link the note to exactly one MOC in its `## Related` section and add it
     to that MOC's `## Notes` list (update the MOC's `modified` date).
4. Delete the inbox file only after its content is fully integrated
   (merge or promote). Flagged files stay put.
5. Append one line per item to `99 - Meta/processing-log.md`:
   `YYYY-MM-DD | <inbox note> | merge/promote/flag | <destination or reason>`.
6. Finish with a short summary: what was merged, promoted, flagged, skipped.

## Rules

- Preserve the user's meaning and voice; reorganise, do not rewrite.
- Never invent content, sources, or conclusions.
- Never delete flagged notes without explicit approval.
- If an item is ambiguous between merge and promote, prefer promote.
