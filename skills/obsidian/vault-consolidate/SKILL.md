---
name: vault-consolidate
description: "Periodic cleanup pass on Liam's Obsidian Second Brain vault — find dead wikilinks, refresh MOCs to cover newly-added notes, flag duplicates, surface stale or orphaned notes, and tidy the tag vocabulary. Use this when Liam mentions consolidating, cleaning up, tidying, refreshing, auditing, or doing a maintenance pass on his vault — including phrasings like 'spring clean my vault', 'check for issues', 'audit my notes', 'find broken links', 'orphaned notes', 'refresh the MOCs'. Run this monthly-ish or whenever Liam suspects rot has crept in. Default to running this skill for any Obsidian vault maintenance request."
---

Use the bundled Python helper for deterministic vault scanning: dead wikilinks, orphan candidates, tag usage, and report path suggestions. Use the LLM only for judgement: duplicate/merge assessment, MOC tag mapping, and recommendations.

1. Inspect the vault:

   ```powershell
   python "<skill-dir>\scripts\vault-consolidate-helper.py" inspect --vault "<vault-path>" --json
   ```

2. Use `dead_wikilinks`, `orphan_note_titles`, and `applied_tags` as the factual baseline.
3. Do not auto-fix dead links or stale notes. Surface recommendations for Liam.
4. For duplicate or merge candidates, use the helper output plus note reading; only auto-merge obvious containment duplicates, and show a plan before destructive edits.
5. Write the consolidation report under `99 - Meta/AI Formatting/` using `vault-consolidation-YYYY-MM-DD.report.md`. If actions are taken, write a matching `.actions.md` summary.
