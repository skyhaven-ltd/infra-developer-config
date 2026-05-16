---
name: triage-inbox
description: "Process notes in Liam's Obsidian vault inbox at '00 - Inbox/' — file them into '02 - Notes/' with proper YAML frontmatter, deduplicate against existing notes, and add wikilinks to related material. Use this whenever Liam mentions triaging, processing, filing, sorting, organising, cleaning up, or going through his inbox or brain dump notes — even casual phrasings like 'go through my inbox', 'sort my notes', 'clean up what I dumped today', 'file these away', or 'process my brain dump'. Also use after Liam adds new content to '00 - Inbox/' and asks for any kind of follow-up. Default to running this skill when the request involves the Obsidian vault and inbox in any way."
---

Use the bundled Python helper for deterministic vault discovery and inbox inventory. Use the LLM only for judgement: classifying notes, choosing tags from the vocabulary, deciding related links, and drafting merge/split plans.

1. Inspect the vault:

   ```powershell
   python "<skill-dir>\scripts\triage-inbox-helper.py" inspect --vault "<vault-path>" --json
   ```

   Omit `--vault` only if the default `~/Documents/Second Brain` exists.

2. Stop and ask for the vault path if `missing_inbox`, `missing_notes`, or `missing_tag_vocabulary` appears in `risk_flags`.
3. Read every inbox note, the tag vocabulary, and relevant existing note names from the helper output.
4. For each inbox file, decide one bucket: new permanent note, append to existing, split, or discard. When in doubt, prefer a new permanent note.
5. Before destructive changes (merge, split that removes the original, or discard), show the plan and wait for approval.
6. File notes into `02 - Notes/` with frontmatter: `created`, `modified`, `tags`, `aliases`, a matching H1, body, and `## Related` links. Tags must come from `tag-vocabulary.md`; propose new tags under Pending Approval rather than inventing them.
7. Write a concise triage report under `99 - Meta/AI Formatting/`.
