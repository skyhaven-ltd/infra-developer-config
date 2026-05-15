---
name: vault-consolidate
description: "Periodic cleanup pass on Liam's Obsidian Second Brain vault — find dead wikilinks, refresh MOCs to cover newly-added notes, flag duplicates, surface stale or orphaned notes, and tidy the tag vocabulary. Use this when Liam mentions consolidating, cleaning up, tidying, refreshing, auditing, or doing a maintenance pass on his vault — including phrasings like 'spring clean my vault', 'check for issues', 'audit my notes', 'find broken links', 'orphaned notes', 'refresh the MOCs'. Run this monthly-ish or whenever Liam suspects rot has crept in. Default to running this skill for any Obsidian vault maintenance request."
---

# Vault Consolidate



You are doing a reflective maintenance pass over Liam's Obsidian vault. Unlike `triage-inbox` which processes new content, this skill audits what's already filed and tidies up the rough edges that accumulate over time.



## Vault layout



```

Documents/Second Brain/

├── 00 - Inbox/                  ← should be empty after triage

├── 01 - MOCs/                   ← Maps of Content

├── 02 - Notes/                  ← permanent notes

└── 99 - Meta/

    ├── AI Formatting/

    │   ├── tag-vocabulary.md        ← controlled tag list

    │   └── consolidation reports    ← write vault consolidation reports here

    ├── Templates/

    └── (other meta files)

```



## What this pass checks



### 1. Dead wikilinks



Scan every note in `02 - Notes/` and `01 - MOCs/` for `[[Link Target]]` references. Compare against the actual filenames in `02 - Notes/`, `01 - MOCs/`, and `99 - Meta/Archived Journal/`. Any link whose target doesn't exist is dead.



For each dead link, report:

- Where it appears (note + line context)

- The closest existing note name (use Levenshtein distance on the filename)

- Suggested fix (either rename to existing, or create a stub)



Don't auto-fix. Surface for Liam to triage.



### 2. MOC drift



Each MOC in `01 - MOCs/` should list every note in `02 - Notes/` that carries one of its topic tags. Drift happens when:



- New notes get added to `02 - Notes/` (via triage or manual creation) but not added to the MOC.

- Notes get retitled or deleted but the MOC entries still reference the old name.



For each MOC, compute the gap (notes that *should* be linked vs notes currently linked) and offer to refresh in alphabetical order. The MOC's topic-tag set is implicit in its name — `Azure MOC` covers `azure`-tagged notes, `Networking MOC` covers `networking`, etc. If you're unsure of the mapping, defer to how the existing MOCs are built.



### 3. Duplicates and propose-merges



Run a content-similarity pass across `02 - Notes/`:



- **Auto-merge candidates** — pairs with body containment ≥ 0.85 and Jaccard similarity ≥ 0.5 on 5-word shingles (code blocks excluded). These are obvious duplicates — auto-merge into the more developed note, preserve the title of the more-linked one, fold the other's title into `aliases`. Report the merge.

- **Propose-merge candidates** — pairs with Jaccard ≥ 0.25. These overlap but each has unique content. Surface with a diff for Liam's sign-off.

- **Weak title-only similarity** — pairs where titles look alike but body content is genuinely different (e.g. `DNS` vs `DHCP`). List but don't action.



### 4. Orphan notes



A note is orphaned if **no other note links to it AND it doesn't appear in any MOC**. These are dead-ends in the knowledge graph — usually fine, but sometimes they signal a note that should be merged or deleted.



For each orphan, surface with a one-line summary so Liam can decide:

- Is this a useful standalone reference? (Keep, but tag the relevant MOC.)

- Is it an early thought that's been superseded? (Merge or delete.)

- Is it just a list/lookup that doesn't need backlinks? (Keep, mark accepted.)



### 5. Stale notes



A note is stale if its `modified` date is more than 12 months ago **and** it's tagged `concept` or `runbook` (where staleness matters — references and synopses are allowed to age). Surface a list with a "needs review?" prompt; don't take action.



### 6. Tag vocabulary hygiene



Open `99 - Meta/AI Formatting/tag-vocabulary.md` and audit:



- **Unused tags** — tags listed in the vocabulary that are applied to zero notes. Candidates to retire.

- **Frequently-applied tags not in the vocabulary** — tags being used in notes but not listed in the vocabulary doc. Either add them properly or convert offending notes to a vocab tag.

- **Pending Approval section** — list anything Liam needs to approve.



### 7. Frontmatter consistency



Spot-check 5–10 random notes for:



- `created` is a real date string (not `{{date}}` from a template that didn't render)

- `modified` has been updated when the note's been edited

- `tags` is a valid YAML array

- `aliases` is present even if empty



Flag any anomalies.



## Output: the consolidation report

Write every consolidation report under `99 - Meta/AI Formatting/` using this filename pattern:

`vault-consolidation-YYYY-MM-DD.report.md`

If you take follow-up actions based on the report, write the action summary under the same folder using:

`vault-consolidation-YYYY-MM-DD.actions.md`



```markdown

## Vault Consolidation — YYYY-MM-DD



Vault snapshot: N notes, M MOCs, P inbox items.



### Dead links (X)

- [[Some Note]] in `Atomic Habits Synopsis.md` line 42 — closest match: [[Atomic Habits]]?



### MOC drift

- Azure MOC: 3 missing entries (notes tagged `azure` not yet linked)

  - [[New Azure Note 1]]

  - [[New Azure Note 2]]

  - [[New Azure Note 3]]

- Networking MOC: clean



### Duplicate candidates

- AUTO-MERGED: [[Note A]] ← [[Note B]] (containment 0.91)

- PROPOSE: [[Boomi Patching Guide]] ↔ [[Boomi Production Patching]] — overlapping bash, but each has unique prose. Diff attached.



### Orphan notes (Y)

- [[Old Stub]] — last modified 2024-03-12, no inbound links, tagged `concept` only



### Stale concept/runbook notes (Z)

- [[Some 2024 Runbook]] — `modified: 2024-08-04`, may have drifted



### Tag vocabulary

- Unused: `policy-as-code` (0 uses), `kanban` (0 uses)

- Outside vocabulary: `dataops` used in 2 notes — promote or rename?

- Pending approval: 1 entry awaiting sign-off



### Frontmatter anomalies

- [[Note With Bad Frontmatter]] — `tags` field is a string instead of array

```



Keep auto-actions minimal — the value of a consolidation pass is in the *report*, not in surprise edits. The only auto-action allowed is auto-merge of clear duplicate-supersets, and even those get reported.



## Safety



Before any auto-merge, snapshot `02 - Notes/` to a tarball in `99 - Meta/AI Formatting/`. The triage skill uses the same AI Formatting folder for its generated reports and AI-maintained metadata.



Run timestamps on backups: `02-Notes-pre-consolidate-YYYYMMDD-HHMMSS.tar.gz`.



## What success looks like



Liam reads the consolidation report in 2–3 minutes, accepts most suggestions in a quick follow-up, and the vault is measurably tighter: fewer dead links, MOCs that match reality, no orphan rot. The vocabulary stays a controlled vocabulary rather than slowly turning into freeform tagging.
