---
name: write-vault-note
description: Write or update a note in the Obsidian vault with the LLM Vault Workflow schema enforced by a deterministic validator. Use whenever creating or editing vault notes, promoting inbox items, or filing knowledge into the Second Brain, so agent-written notes match hand-written conventions.
disable-model-invocation: true
---

# Write vault note

Write a note into the Obsidian vault with the vault schema enforced by
`scripts/validate-vault-note.py` before the note lands.

## Preconditions

1. Resolve the vault root from the `OBSIDIAN_VAULT_PATH` environment variable.
   If unset, stop and ask the user; suggest
   `Install-DeveloperConfig.ps1 -ObsidianVaultPath "<vault root>"`.
2. Read `99 - Meta/AI Formatting/LLM Vault Workflow.md` for the schema and
   the folder mapping, and `99 - Meta/AI Formatting/tag-vocabulary.md` for
   allowed tags. Never invent tags; propose new ones under
   `## Pending Approval` in the vocabulary file and ask before using them.

## Workflow

1. Decide the destination from the folder mapping: permanent notes in
   `02 - Notes/`, MOCs in `01 - MOCs/`, raw captures in `00 - Inbox/`.
   When updating an existing note, read it first and preserve its meaning,
   voice, wikilinks, and frontmatter values you are not changing.
2. Draft the note to a temporary file (not in the vault) using the
   frontmatter and section structure from the LLM Vault Workflow.
3. Validate:

   ```powershell
   python "<skill-dir>/scripts/validate-vault-note.py" "<temp-file>"
   ```

   Pass `--inbox` when the target is `00 - Inbox/`. Fix every reported error
   and re-run until the script prints `VALID`. Treat warnings as advice:
   resolve them unless there is a stated reason not to.
4. Move the validated file to its destination in the vault.
5. Integrate: add `[[wikilinks]]` from the note's `## Related` section to
   existing notes, and add the note to the relevant MOC in `01 - MOCs/`
   (validate the MOC edit too if its frontmatter changes).
6. Report the created or updated paths and any tag proposals awaiting
   approval.

## Rules

- Never delete, merge, or discard existing vault content without explicit
  approval.
- Do not touch notes tagged `pinned` except to format them, and never move
  them out of `00 - Inbox/`.
- Set `modified` to today's date when meaningfully editing an existing note;
  keep the original `created`.
