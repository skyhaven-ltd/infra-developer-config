---
name: organise-vault
description: "Unified Obsidian vault workflow for Liam's Second Brain. Use for ad-hoc note creation (manual notes Liam writes himself, not bulk-ingested via learn-content), inbox triage, processing '00 - Inbox/' notes, source ingestion, Markdown cleanup, note formatting, MOC refreshes, vault consolidation, dead wikilinks, orphan notes, duplicate notes, tag vocabulary cleanup, YAML frontmatter normalization, and applying the LLM-maintained wiki workflow documented in the vault."
---

Use this as the single Obsidian workflow skill. Keep this skill lightweight: the source of truth for vault-specific rules is the vault file `99 - Meta/AI Formatting/LLM Vault Workflow.md`, with controlled tags in `99 - Meta/AI Formatting/tag-vocabulary.md`.

## Required context

Before editing vault notes, read these files when they exist:

1. `99 - Meta/AI Formatting/LLM Vault Workflow.md`
2. `99 - Meta/AI Formatting/tag-vocabulary.md`
3. Relevant templates under `99 - Meta/Templates/`

Do not duplicate those rules in the skill. Pinned inbox notes tagged `pinned` are intentionally retained in `00 - Inbox/` and must not be moved unless explicitly requested. Pinned inbox notes keep the inbox-template YAML frontmatter, including `inbox` and `pinned` tags, but must not receive the learning frontmatter fields until they are processed or promoted. Follow the vault workflow file for YAML frontmatter, Markdown structure, MOC conventions, source handling, status values, confidence values, and report locations.

## Helper commands

Use the bundled helper for deterministic inspection.

Inspect the vault:

```powershell
python "<skill-dir>\scripts\organise-vault-helper.py" inspect --vault "<vault-path>" --json
```

Inspect a single Markdown file before formatting:

```powershell
python "<skill-dir>\scripts\organise-vault-helper.py" inspect-file --file "<note.md>" --json
```

Omit `--vault` only if the default `~/Documents/Second Brain` exists.

The helper inspection includes `previous_reports`. Check this before making vault
changes. If `previous_reports.previous_consolidation.has_approved_actions_to_run`
is true, run only the approved, safe actions first, then mark those rows as
`done` in the consolidation file. Do not run actions marked `pending`, `skip`, or
`defer`. The helper checks the canonical consolidation file first and falls back
to the newest legacy `vault-consolidation*.actions.md` or `.report.md` file when
the canonical file does not exist yet.

There should only be one triage report and one vault consolidation report:

- `99 - Meta/AI Formatting/triage-report.md`
- `99 - Meta/AI Formatting/vault-consolidation.md`

Do not create dated report files. Do not create a separate `.actions.md` file.
If legacy dated reports or `.actions.md` files exist, leave them in place unless
Liam explicitly asks for cleanup, but continue writing only to the canonical
single report files above.

## Route the task

- Ad-hoc note creation: when Liam hands over notes he wrote himself (raw text, partial draft, brain-dump), format them into a single Markdown file in `00 - Inbox/` using the frontmatter standard in `99 - Meta/AI Formatting/LLM Vault Workflow.md`. The note body formatting rules below still apply. The `learn-content` skill handles bulk ingestion from URLs / external markdown; this skill handles manual ad-hoc notes.
- Inbox triage or source ingestion: inspect the vault, read inbox files, preserve source metadata, integrate durable knowledge into `02 - Notes/`, update relevant MOCs, and update `triage-report.md`.
- Markdown formatting: inspect the target file, preserve YAML frontmatter, wikilinks, tags, embeds, tasks, code fences, dates, paths, and quoted text. Improve clarity without adding new claims, links, tags, action items, conclusions, or frontmatter unless explicitly asked.
- Vault consolidation: inspect the vault, first check `previous_reports.previous_consolidation` for Liam-approved actions from the prior run, use dead links/orphans/tags/frontmatter issues as the factual baseline, refresh MOCs, make only already-approved or safe fixes, and update the single `vault-consolidation.md` file with any new recommendations that need Liam input.
- MOC refresh: preserve Liam's existing organisation where possible, add notes under the most specific relevant section, and avoid creating new MOCs unless the report explains why.

## Default full-vault workflow

When Liam invokes this skill by name, asks to process the inbox, or asks for the full vault workflow without a narrower scope, do this exact sequence:

1. Read the required context files and inspect the vault with the helper.
   - Before processing new work, review `previous_reports.previous_consolidation`.
   - If Liam has responded with `approve`, `approved`, or `run` in the previous consolidation table, run those approved actions when they are safe and non-destructive, then change their response to `done`.
   - Do not run actions whose response is `pending`, `skip`, or `defer`.
2. Read every Markdown note in `00 - Inbox/` and the existing MOCs in `01 - MOCs/`.
3. Format inbox notes first.
   - Format pinned inbox notes in place only for safe readability cleanup.
   - Ensure pinned inbox notes keep inbox-template YAML frontmatter with `inbox` and `pinned` tags.
   - Do not add learning frontmatter fields to pinned inbox notes, because they have not been processed.
   - Preserve pinned inbox notes in `00 - Inbox/`.
4. Triage unpinned inbox notes.
   - Create durable notes in `02 - Notes/` for reusable knowledge.
   - Update an existing note when the inbox item is a small addition to an existing topic.
   - Preserve original unpinned inbox source files by moving them to `99 - Meta/AI Formatting/Processed Inbox Sources/YYYY-MM-DD/`; do not delete them.
   - Update new notes' `source` fields to point to the preserved processed source path when relevant.
5. Refresh relevant MOCs.
   - Add new durable notes under the most specific existing MOC sections.
   - Fix obvious MOC wikilink mismatches when the intended target clearly exists.
   - Preserve Liam's existing MOC structure.
6. Update `99 - Meta/AI Formatting/triage-report.md`.
7. Run a final helper inspection.
8. Perform consolidation from the final inspection baseline.
   - Summarise remaining dead wikilinks, orphan notes, pinned inbox notes, frontmatter issues, and risk flags.
   - Make only safe non-destructive fixes, such as obvious MOC link target corrections.
   - Do not move pinned notes, rewrite archived journals at scale, remove image embeds, merge notes, or delete anything without explicit approval.
9. Update only `99 - Meta/AI Formatting/vault-consolidation.md`.
   - Include a short "Actions awaiting Liam input" section when a decision is needed.
   - Use a Markdown table with this exact header:
     `| ID | Proposed action | Liam response |`
   - Use stable IDs such as `VC-001`.
   - Set new rows to `pending`.
   - Tell Liam to edit the `Liam response` cell to one of: `approve`, `skip`, `defer`.
   - On the next run, the helper will surface approved rows for execution.
10. Finish with a concise summary of created notes, updated notes, refreshed MOCs, report paths, and remaining validation counts.

## Learning frontmatter

Use `99 - Meta/AI Formatting/LLM Vault Workflow.md` as the sole source of truth for frontmatter. The learning fields defined in the vault workflow are mandatory on maintained notes after processing, including durable notes, MOCs, reports, and notes promoted from `00 - Inbox/` to `02 - Notes/`. Pinned inbox notes are intentionally unprocessed and are exempt from learning fields only: keep their inbox-template YAML frontmatter, but do not add `learning_status`, `learning_question_goal`, or `learning_question_types` while they remain pinned in `00 - Inbox/`.

## Safety

- Do not delete, merge, archive, discard, or destructively split notes without explicit approval.
- Do not invent tags. Use `tag-vocabulary.md`; propose new tags under `## Pending Approval`.
- Preserve source/provenance fields from clippings where useful.
- Prefer new notes or source notes when uncertain rather than merging away information.
- Report ambiguity left unchanged.
