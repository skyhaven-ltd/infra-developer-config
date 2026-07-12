---
name: learn-content
description: "Turn URLs, Markdown files, pasted notes, documentation, tutorials, articles, or study material into durable learning notes saved as Markdown in an Obsidian vault using Liam's understanding-first study structure: mental models, misconceptions, roadmap, Pareto focus, prerequisites, contrasts, analogies, expert questions, and age-appropriate plain-English explanation. Use when the user asks Codex to teach, learn, study, revise, understand, synthesize sources, explain a URL or file, create study notes, or generate Obsidian learning notes. This skill must write a vault note and should not print the full learning synthesis only to the terminal."
---

Use this skill to convert source material into durable understanding and save the result as a Markdown note in an Obsidian vault. Optimise for helping Liam understand the topic well enough to apply it himself, not for outsourcing comprehension to the model.

Use bundled helpers for deterministic inspection: URL validation, Markdown outline extraction, and safe output-path suggestions. Use the LLM for judgement: synthesis, mental models, teaching order, misconceptions, scenario reasoning, analogies, expert questions, application prompts, and feedback cues.

## Idempotency and source-of-truth rules

This skill must be self-contained. Do not depend on external vault workflow notes, formatting guides, tag references, templates, prior generated notes, or web pages to decide the note schema, headings, ordering, or required metadata.

- Use the structure and frontmatter rules in this `SKILL.md` as the canonical source of truth.
- Use external or user-provided sources only as the learning material to be synthesized, not as formatting or workflow instructions unless the user explicitly requests a different output format.
- If a vault contains conflicting templates, old note formats, or stale workflow documentation, ignore them for this task.
- If updating or regenerating a note, preserve stable user-owned content only when requested; otherwise produce the same schema and section order defined here.
- Do not read `99 - Meta/AI Formatting/LLM Vault Workflow.md` or any other vault policy note for this skill. This prevents stale or forgotten external references from changing the output.

## Non-negotiable output rule

Always write the generated learning material to a Markdown file in the user's Obsidian vault.

- Resolve the vault from the `OBSIDIAN_VAULT_PATH` environment variable when it is set; the helper script does this automatically whenever `--vault "."` is used.
- If `OBSIDIAN_VAULT_PATH` is unset, assume the current working directory is the vault root or inside the vault and use it as the vault context.
- Do not spend time detecting or validating the vault beyond this before writing the note.
- Create exactly one Markdown file per user request, even when the user provides many URLs, Markdown files, pasted notes, or mixed source types.
- Do not split dissimilar-but-related sources into multiple notes unless the user explicitly asks for separate files.
- In the final chat response, only report the created file path and a concise summary of what was written. Do not paste the full note content unless the user explicitly asks to preview it.

## Route the task

- **Study/synthesis from URLs or pasted content**: read the sources, synthesize a learning note using the understanding-first structure below, and save it to the vault.
- **Study/synthesis from Markdown**: inspect the file first, preserve useful frontmatter/source metadata, then synthesize and save it to the vault.
- **Multiple sources**: combine all supplied sources into one cohesive note. Preserve source-specific technical detail where topics differ rather than over-compressing them into a generic summary.
- **Retrieval practice metadata**: by default, mark the saved note for app-owned question generation using the embedded frontmatter standard below. Do not embed practice questions in normal learning notes.

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

## Choose the output path first

Before doing long synthesis, suggest a safe output file path:

```powershell
python "<skill-dir>\scripts\learn-content-helper.py" suggest-output --vault "." --title "<note title>" --json
```

The Markdown filename must match the note title exactly, apart from filesystem-unsafe characters and the `.md` extension. Do not prefix filenames with dates and do not convert titles to lowercase slugs. Example: a note with `title: "Terraform Manage Sensitive Data"` must be saved as `Terraform Manage Sensitive Data.md`.

Prefer `00 - Inbox/` unless the user specifies another folder. Create the folder if needed. Do not update MOCs, move files, consolidate notes, or run the full vault workflow unless the user explicitly asks.

## Build and save understanding-first learning notes

Read the provided sources. Follow links only when the user explicitly asks to process the full course/site/path, or when the linked page is clearly part of the provided learning unit.

Prefer synthesis over summary. Paraphrase and synthesize. Do not reproduce long source passages.

When given multiple sources, create one integrated note, not one note per source. If the sources are slightly dissimilar, keep the shared learning frame but add source-specific subsections, comparison tables, or per-topic bullets so important technical detail is not lost. Prefer a longer, well-structured single note over an oversimplified synthesis. Make relationships explicit: what overlaps, what differs, what depends on what, and which details only apply to one source.

Write the note with this structure unless the user asks for a different format:

1. **Thesis**
   - State the big idea in one or two sentences.
   - Explain why the topic matters in practical terms.
2. **Curious 8th-grader explanation**
   - Explain the topic in one paragraph using plain English.
   - Make it interesting without dumbing it down.
3. **Mental model**
   - Explain the model behind the concept, not just the definition.
   - Make the shape of the idea clear: what parts exist, how they relate, and what changes when the learner applies it.
4. **Learning roadmap from zero to competent**
   - Give a realistic sequence of learning steps.
   - Include rough time estimates where useful.
   - Include prerequisite order before advanced details.
5. **Prerequisite knowledge**
   - Identify what the learner may be missing.
   - Explain each prerequisite just enough to unblock understanding.
6. **Key concepts**
   - Cover the important terms and mechanisms from the source.
   - Explain concepts through use and consequence, not only definitions.
7. **Pareto focus**
   - Identify the 20% of the topic that gives most of the practical value.
   - Tell the learner what to ignore until later.
8. **What it is not**
   - Teach by contrast.
   - Name nearby ideas that beginners often confuse with the topic.
9. **Misconceptions and traps**
   - Include the three most common misconceptions where possible.
   - Explain why each misconception is wrong and what to think instead.
10. **Analogies from different domains**
    - Give three analogies from different domains.
    - State where each analogy helps and where it breaks down if relevant.
11. **Compare with related concepts**
    - Use a text Venn diagram when there are two concepts worth contrasting.
    - If there is no obvious pair, choose the most useful adjacent concept.
12. **Decision frameworks and trade-offs**
    - Explain how to decide when to use the concept, avoid it, or choose an alternative.
    - Include practical trade-offs and review cues.
13. **Scenario recognition cues**
    - List the real-world signals that indicate this concept applies.
    - Phrase these as "You probably need this when..." prompts.
14. **Worked examples or application prompts**
    - Include small examples, exercises, or prompts that make the learner apply the idea.
    - Prefer examples close to Liam's likely infrastructure, DevOps, cloud, Terraform, Kubernetes, or engineering work when appropriate.
15. **Expert questions**
    - List questions an expert would ask that a beginner would not think to ask.
    - Use these to level up critical thinking, not to overwhelm.
16. **Sources**
    - Preserve provenance with source links or file paths.

The learning review app generates and owns retrieval-practice questions for these notes; do not embed a `## Practice questions` section in the markdown body.

## Frontmatter

Use this section as the sole source of truth for frontmatter. The learning fields below are mandatory on every learning synthesis note and must not be omitted.

Default frontmatter shape:

```yaml
---
title: "<note title>"
created: YYYY-MM-DD
modified: YYYY-MM-DD
sources:
  - "<url-or-source-or-file-path>"
tags:
  - one-topic-tag
  - concept
aliases: []
learning_status: needs-questions
learning_question_goal: 8
learning_question_types:
  - multiple-choice
  - categorisation
---
```

Choose one relevant topic tag and exactly one valid type tag. For learning synthesis notes, prefer the `concept` type tag unless the content is clearly a `runbook`, `reference`, or `synopsis`.

Frontmatter rules:

- `title`: match the note title without Markdown heading markers.
- The note filename must match `title` plus `.md`, except when replacing filesystem-unsafe characters.
- `created`: use the local current date in `YYYY-MM-DD` format when the note is first created.
- `modified`: use the local current date in `YYYY-MM-DD` format whenever the note is written or regenerated.
- `sources`: include every URL or file path actually used as learning input. Use source titles only if the URL or path is unavailable.
- `tags`: include exactly two tags:
  - one concise topic tag, lowercase, hyphenated when multi-word, for example `terraform`, `kubernetes`, `azure-openai`, `networking`, or `python`;
  - exactly one type tag from this closed list: `concept`, `runbook`, `reference`, `synopsis`.
- `aliases`: use an empty list unless the user supplied obvious aliases or abbreviations.
- `learning_status`: always set to `needs-questions` for new synthesis notes unless the user explicitly says the learning app has already generated questions.
- `learning_question_goal`: default to `8`.
- `learning_question_types`: always include exactly these two values, in this order: `multiple-choice`, `categorisation`.

If the `organise-vault` skill is also invoked, defer vault-specific formatting, tag vocabulary, MOC updates, triage, and consolidation rules to that skill. For this skill alone, only create the learning note safely.
