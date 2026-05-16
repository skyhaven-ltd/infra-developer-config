---
name: format-markdown
description: Standardize Markdown files for clear structure, readable formatting, and correct English grammar. Use when Codex needs to clean up Obsidian notes, voice-note captures, fleeting thoughts, brain dumps, rough drafts, or any Markdown content while preserving the original meaning, YAML frontmatter, wikilinks, tags, embeds, tasks, note-taking intent, filename-matched H1 headings, and punctuation standards.
---

Use the bundled Python helper for deterministic Markdown structure checks. Use the LLM only for judgement: improving clarity while preserving meaning, voice, and Obsidian syntax.

1. Inspect the target file:

   ```powershell
   python "<skill-dir>\scripts\format-markdown-helper.py" inspect --file "<note.md>" --json
   ```

2. Preserve the fields in `llm_must_preserve`: YAML frontmatter, wikilinks, tags, embeds, tasks, code fences, dates, paths, and quoted text.
3. Edit the file directly unless the user asks for a preview.
4. Ensure exactly one H1 and make it match `expected_h1`. Remove em dashes, trailing whitespace, excessive blank lines, and voice-capture filler without changing facts.
5. Do not add new claims, links, tags, action items, conclusions, or frontmatter.
6. Respond with the changed path, a brief summary of improvements, and any ambiguity left unchanged.
