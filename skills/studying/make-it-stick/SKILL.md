---
name: make-it-stick
description: Test a user on the contents of a Markdown file using evidence-informed learning principles from Make It Stick. Use when the user asks to be quizzed, tested, drilled, revised, or helped to remember a .md file, note, study guide, README, documentation page, or pasted Markdown content.
---

Use the bundled Python helper for deterministic Markdown outline extraction. Use the LLM only for judgement: selecting high-value concepts, grading answers, adapting difficulty, and scheduling retrieval.

1. If the user provides a file path, inspect it:

   ```powershell
   python "<skill-dir>\scripts\make-it-stick-helper.py" inspect --file "<source.md>" --json
   ```

   If the user pasted Markdown, use the pasted content directly.

2. Build a hidden question queue from headings, definitions, procedures, examples, warnings, and dependencies. Preserve YAML frontmatter as metadata unless the user asks to test it.
3. Ask one question at a time. Default to 10 questions and mixed recall, application, comparison, sequencing, and error-diagnosis prompts.
4. After each answer, mark it `Correct`, `Partly correct`, or `Not yet`, give concise feedback, and queue missed ideas for later retrieval.
5. Every 3-5 questions, retest a missed or high-value idea in a different form.
6. Close with strengths, weak spots, 3-7 follow-up prompts, and a review cadence.
