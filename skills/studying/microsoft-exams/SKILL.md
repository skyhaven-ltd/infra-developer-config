---
name: microsoft-exams
description: "Transform Microsoft Learn exam or training module content into meaningful exam knowledge: themes, mental models, decision frameworks, trade-offs, scenario reasoning, and conceptual study notes rather than memorized bullet points. Use when the user asks to study, summarize, revise, understand, teach, quiz, or extract exam-relevant knowledge from a Microsoft Learn module URL, learning path, certification module, or Azure/Microsoft exam training page."
---

Use the bundled Python helper for deterministic Microsoft Learn URL validation and source-shape checks. Use the LLM only for judgement: synthesizing themes, mental models, scenario triggers, misconceptions, and practice questions.

1. Inspect the Learn URL:

   ```powershell
   python "<skill-dir>\scripts\microsoft-exams-helper.py" inspect --url "https://learn.microsoft.com/..." --json
   ```

2. If `learning_path_confirm_scope` appears in `risk_flags`, confirm whether to process the whole path or a specific module unless the user already made that clear.
3. Browse the Microsoft Learn landing page and unit pages. Prefer `learn.microsoft.com` as the source of truth and preserve source links.
4. Paraphrase and synthesize. Do not reproduce long Microsoft Learn passages or claim generated questions are official exam questions.
5. If unspecified, output: thesis, themes, mental models, scenario recognition, misconceptions, practice questions, and sources.
