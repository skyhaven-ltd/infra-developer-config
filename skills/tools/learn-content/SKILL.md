---
name: learn-content
description: "Turn URLs, Markdown files, pasted notes, documentation, tutorials, articles, or study material into durable learning notes saved as Markdown in an Obsidian vault, with app-owned retrieval-practice generation requested through frontmatter. Use when the user asks to learn, study, revise, remember, synthesize sources, create study notes, parse a list of URLs, or generate Obsidian learning notes. This skill must write a vault note and should not print the full learning synthesis only to the terminal."
---

Use this skill to convert source material into durable understanding and save the result as a Markdown note in an Obsidian vault. Writing the note is mandatory: do not provide the full learning synthesis only in the chat/terminal.

Use bundled helpers for deterministic inspection: URL validation, Markdown outline extraction, vault detection, and safe output-path suggestions. Use the LLM for judgement: synthesis, mental models, teaching order, misconceptions, scenario reasoning, application prompts, feedback cues, and retrieval scheduling notes.

## Non-negotiable output rule

Always write the generated learning material to a Markdown file in the user's Obsidian vault.

- If the current working directory is inside a vault, detect and use that vault.
- If the user supplies a vault path, use that vault.
- If no vault can be detected, stop and ask for the vault path. Do not fall back to terminal-only output.
- In the final chat response, only report the created file path and a concise summary of what was written. Do not paste the full note content unless the user explicitly asks to preview it.

## Route the task

- **Study/synthesis from URLs or pasted content**: read the sources, synthesize a learning note, and save it to the vault.
- **Study/synthesis from Markdown**: inspect the file first, preserve useful frontmatter/source metadata, then synthesize and save it to the vault.
- **Retrieval practice**: by default, mark the saved note for app-owned question generation via the frontmatter standard in `99 - Meta/AI Formatting/LLM Vault Workflow.md`. Do not embed practice questions in the saved note. Only run an interactive one-question-at-a-time quiz when the user explicitly asks for an interactive quiz.

## Inspect sources

For Markdown files:

```powershell
python "<skill-dir>\scripts\learn-content-helper.py" inspect-file --file "<source.md>" --json
```

For URLs:

```powershell
python "<skill-dir>\scripts\learn-content-helper.py" inspect-urls --urls "<url1>" "<url2>" --json
```

If a URL is broad, index-like, or ambiguous, confirm scope before processing the whole site/course/path. Examples: documentation root, course catalogue, blog archive, tag/category page, GitHub repository root, or search result page.

## Detect the vault and output path first

Before doing long synthesis, detect the vault from the supplied path or current working directory:

```powershell
python "<skill-dir>\scripts\learn-content-helper.py" detect-vault --path "." --json
```

Then suggest a safe output file path:

```powershell
python "<skill-dir>\scripts\learn-content-helper.py" suggest-output --vault "." --title "<note title>" --json
```

Prefer `00 - Inbox/` unless the user specifies another folder. Create the folder if needed. Do not update MOCs, move files, consolidate notes, or run the full vault workflow unless the user explicitly asks.

## Build and save learning notes

Read the provided sources. Follow links only when the user explicitly asks to process the full course/site/path, or when the linked page is clearly part of the provided learning unit.

Prefer synthesis over summary. Write the note with this structure unless the user asks for a different format:

1. Thesis
2. Learning map / prerequisite order
3. Key concepts
4. Mental models
5. Decision frameworks and trade-offs
6. Scenario recognition cues
7. Misconceptions and traps
8. Worked examples or application prompts
9. Sources

Paraphrase and synthesize. Do not reproduce long source passages. The learning review app generates and owns retrieval-practice questions for these notes; do not embed a `## Practice questions` section in the markdown body.

Use `99 - Meta/AI Formatting/LLM Vault Workflow.md` as the sole source of truth for frontmatter. Set `source_type: learning-synthesis` for notes created by this skill. The learning fields defined in the vault workflow are mandatory on every maintained note and must not be omitted.

Preserve provenance. Include a `## Sources` section with source links or file paths.

## Interactive quiz mode

Only use this mode when the user explicitly asks for an interactive quiz, drill, or test. If they ask to learn/summarize/study content, create a saved note instead.

1. Build a hidden question queue from headings, definitions, procedures, examples, warnings, trade-offs, and dependencies.
2. Ask one question at a time.
3. Default to 10 questions with a mixed prompt set: free recall, concept check, application, comparison, sequencing, and error diagnosis.
4. After each answer, mark it `Correct`, `Partly correct`, or `Not yet`; give concise feedback; and queue missed ideas for later retrieval.
5. Every 3-5 questions, retest a missed or high-value idea in a different form.
6. Close with strengths, weak spots, 3-7 follow-up prompts, and a review cadence.
7. Save a short quiz recap note to the vault unless the quiz was based on an existing note and the user asks not to create a recap.

If the `organise-vault` skill is also invoked, defer vault-specific formatting, tag vocabulary, MOC updates, triage, and consolidation rules to that skill. For this skill alone, only create the learning note safely.

