---
name: triage-inbox
description: "Process notes in Liam's Obsidian vault inbox at '00 - Inbox/' — file them into '02 - Notes/' with proper YAML frontmatter, deduplicate against existing notes, and add wikilinks to related material. Use this whenever Liam mentions triaging, processing, filing, sorting, organising, cleaning up, or going through his inbox or brain dump notes — even casual phrasings like 'go through my inbox', 'sort my notes', 'clean up what I dumped today', 'file these away', or 'process my brain dump'. Also use after Liam adds new content to '00 - Inbox/' and asks for any kind of follow-up. Default to running this skill when the request involves the Obsidian vault and inbox in any way."
---

# Triage Inbox



You are processing Liam's Obsidian vault inbox. Your job is to take rough brain-dump notes from `00 - Inbox/` and file them properly into `02 - Notes/` — adding YAML frontmatter, picking tags from the controlled vocabulary, linking to related notes, and merging into existing notes when the content fits there better than as a new note.



This is a workflow skill that runs against a real vault on disk. Be careful — these are Liam's actual notes, not test data. Always show what you're about to do before destructive changes (merges, splits, deletions), and produce a triage report at the end.



## Vault layout



```

Documents/Second Brain/

├── 00 - Inbox/                  ← raw brain dumps you process from

├── 01 - MOCs/                   ← Maps of Content (entry points by theme)

├── 02 - Notes/                  ← permanent notes (your filing destination)

└── 99 - Meta/

    ├── Archived Journal/        ← old daily notes (don't touch)

    ├── AI Formatting/

    │   ├── tag-vocabulary.md    ← THE source of truth for allowed tags

    │   └── triage reports       ← write triage reports here

    ├── Templates/

    │   ├── Generic Note Template.md

    │   ├── Inbox Note Template.md

    │   └── MOC Template.md

    ├── Attachments/

```



The vault path will usually be one of:

- `~/Documents/Second Brain` (Liam's actual location)

- A connected folder mount — check the conversation context for the actual path



If you can't find the vault, ask Liam where it is rather than guessing.



## Note schema



Every permanent note carries this YAML frontmatter:



```yaml

---

created: YYYY-MM-DD

modified: YYYY-MM-DD

tags: [topic-tag, another-topic, type-tag]

aliases: []

---

# Title



body...



## Related



- [[Other Note]]

- [[Some MOC]]

```



Rules:

- `created` preserves the original creation date if known. For inbox notes that came from the Inbox template, use the date in the existing frontmatter. Otherwise use today.

- `modified` is always today.

- `tags` must be drawn from `99 - Meta/AI Formatting/tag-vocabulary.md`. Don't invent tags. If a note genuinely needs a new tag, propose it to Liam and add it under `## Pending Approval` in the vocabulary file.

- Every note carries at least one **topic tag** (what it's about) and exactly one **type tag** (what kind: `concept`, `runbook`, `reference`, `synopsis`, `project`, `moc`).

- Cap at 5 tags. More than that usually means the note should be split.

- `aliases` only when there's an obvious alternative name (e.g. "AVD" alias for "Azure Virtual Desktop"). Otherwise leave empty.



## The triage loop



For each file in `00 - Inbox/`, decide one of four things and act on it.



### Step 1 — Read everything



Before processing any single note, do a quick survey:



1. List `00 - Inbox/` and read every note in full.

2. Read `99 - Meta/AI Formatting/tag-vocabulary.md` end-to-end so you know what tags are allowed.

3. Get a list of filenames in `02 - Notes/` and `01 - MOCs/` — you don't need to read the bodies, just know what exists. This is what lets you spot duplicates and pick link targets.



You're now ready to make decisions across the whole batch rather than one note at a time.



### Step 2 — Classify each inbox note



For each inbox note, decide which bucket it falls into:



- **New permanent note** — the dominant case. The content is a single coherent topic that doesn't already exist in `02 - Notes/`. Action: file it.

- **Append to existing** — the content extends or updates a note that already exists in `02 - Notes/`. Action: merge.

- **Split into multiple notes** — the inbox note is actually 2+ unrelated topics jammed into one file. Action: split.

- **Discard** — the note is just noise, a transient reminder that's no longer relevant, or a one-line shopping-list item that doesn't belong in a knowledge vault. Action: flag for Liam's confirmation. Never delete without asking.



When in doubt, prefer **new permanent note**. Splitting and merging are reversible only via backup; over-eager deduplication loses content.



### Step 3 — File the new notes



For each inbox note classified as a new permanent note:



1. **Pick a title** — clean up the existing `# Title` if it's there, or invent one from the content. Title Case, descriptive, no dates in the title unless it's intrinsically date-bound.

2. **Pick tags** — pull from `99 - Meta/AI Formatting/tag-vocabulary.md`. Use the title as the strongest signal, body as supporting. Cap at 5.

3. **Build the frontmatter** — using the schema above.

4. **Add a `## Related` section** — this is the linking-to-related-notes part. Look at the filenames in `02 - Notes/` and `01 - MOCs/` and pick 1–4 that genuinely relate (shared tags, same topic family, sequential learning material). Always link to the topic's MOC. Use Obsidian wikilinks: `[[Note Name]]`. Don't invent links to notes that don't exist.

5. **Write the file** to `02 - Notes/<Title>.md`.

6. **Update relevant MOCs** — open the topic MOC in `01 - MOCs/`, add `- [[New Note Title]]` to the `## Notes` section in alphabetical order. Don't re-sort the whole list; just insert.

7. **Delete the original from `00 - Inbox/`** only after the new note is written.



### Step 4 — Merge into existing notes



For each inbox note classified as an append:



1. **Show Liam the diff first.** Output a clear before/after of the merge target so he can sanity-check before any file write.

2. After confirmation (or if running in auto-mode for obvious continuations), merge:

   - Append the inbox content into the appropriate section of the existing note. If no obvious section exists, add one.

   - Update the `modified` field in the existing note's frontmatter to today.

   - If the merge introduces new tag relevance, expand the `tags` array (still capped at 5).

3. **Delete the original from `00 - Inbox/`** after the merge is written.



### Step 5 — Splits



For each inbox note that needs splitting:



1. Identify the distinct topics inside the file.

2. Treat each as its own new permanent note (Step 3) and run them through filing.

3. Delete the original after all splits are filed.



### Step 6 — Discards



Show Liam a list of discard candidates with one-sentence reasoning each:



```

- "Buy milk" — transient reminder, not knowledge

- "asdf test" — junk

```



Wait for confirmation before deleting. If unsure, leave the note in the inbox.



## Auto-merge of obvious duplicates



If a new inbox note's content is a clear superset/subset of an existing permanent note (containment ≥ 0.85 of body shingles, after stripping code blocks), auto-merge without confirmation. Report the auto-merge in the triage report so Liam can audit. For anything weaker (overlapping but each has unique content), surface as a propose-merge with a diff and wait for sign-off.



## The triage report



End every triage run by writing a single concise report under `99 - Meta/AI Formatting/` using this filename pattern:

`triage-report-YYYY-MM-DD.md`

Also include the report in the chat response.



```markdown

## Triage Report — YYYY-MM-DD



Processed N notes from 00 - Inbox/.



### New permanent notes (M)

- [[Note A]] — tags, MOC linked

- [[Note B]] — tags, MOC linked



### Appended to existing (K)

- "Inbox note X" merged into [[Existing Note]]



### Split (J)

- "Inbox note Y" → [[New Note 1]], [[New Note 2]]



### Auto-merged duplicates (P)

- "Inbox note Z" auto-merged into [[Existing Note]] (containment 0.92)



### Awaiting your decision (Q)

- "Inbox note W" — possible duplicate of [[Other Note]]; unsure whether to merge or keep separate

- "Buy milk" — looks transient; delete?



### MOCs updated

- [[Azure MOC]] (+2 entries)

- [[Health MOC]] (+1 entry)

```



Keep it scannable. Liam reads this report to validate the run, not to learn what each note is about.



## Tag vocabulary discipline



The whole system relies on the controlled vocabulary holding. Every time you're tempted to invent a tag, ask yourself:



- Does an existing tag already cover this? (Usually yes.)

- Is this tag truly cross-cutting (used by ≥ 3 notes)? Single-use tags clutter the vocabulary.



If you genuinely think a new tag is needed, append it to `99 - Meta/AI Formatting/tag-vocabulary.md` under `## Pending Approval` with a one-line justification. Don't apply it to notes until Liam confirms.



## When NOT to be aggressive



- **Ambiguous classifications** — when you can't decide between new-note and append, default to new-note. Liam can ask you to merge later.

- **Sensitive content** — notes about family, mental health, or personal reflection should never be silently merged. Always surface as propose-merge.

- **Code-heavy runbooks** — these often look like duplicates because they share commands but actually solve different problems (see the Boomi Patching Guide vs Boomi Production Patching pair). Keep separate unless body text outside code blocks is also overlapping.



## What success looks like



A clean inbox at the end of the run, every note either filed correctly or surfaced for confirmation, MOCs updated, and a triage report Liam can scan in 30 seconds. The vault gets denser and more interconnected over time without any content loss.
