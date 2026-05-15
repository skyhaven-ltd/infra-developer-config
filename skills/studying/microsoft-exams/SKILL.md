---
name: microsoft-exams
description: "Transform Microsoft Learn exam or training module content into meaningful exam knowledge: themes, mental models, decision frameworks, trade-offs, scenario reasoning, and conceptual study notes rather than memorized bullet points. Use when the user asks to study, summarize, revise, understand, teach, quiz, or extract exam-relevant knowledge from a Microsoft Learn module URL, learning path, certification module, or Azure/Microsoft exam training page."
---

# Microsoft Exams

## Overview

Use this skill to turn a Microsoft Learn module into durable understanding for exam preparation. Prefer concepts, themes, "why it matters", and scenario reasoning over rote lists.

## Input requirement

Start by identifying the Microsoft Learn module being studied.

- If the user did not provide a URL, ask for the Microsoft Learn module URL before proceeding.
- If the user provides a learning path or collection URL, confirm whether to process the whole path or a specific module unless the request makes that clear.
- Use the URL as the source of truth. Fetch the module landing page and each unit linked from it before producing study material.

## Source handling

- Browse the Microsoft Learn URL and its unit pages. Prefer `learn.microsoft.com` pages as primary sources.
- Preserve source attribution with links in the final answer.
- Do not reproduce long Microsoft Learn passages. Paraphrase and synthesize.
- Treat assessment answers carefully: explain the reasoning pattern, not just the answer.
- If a page is inaccessible, say which unit could not be read and continue with the accessible units.

## Knowledge abstraction workflow

1. **Map the module**
   - Capture the title, exam/training context, learning objectives, prerequisites, and unit list.
   - Note the apparent intended learner role and the level of depth expected.

2. **Extract themes**
   - Identify 3-7 major themes that recur across the units.
   - Phrase themes as concepts or tensions, for example "governance vs. developer velocity" or "license freedom vs. reciprocal obligations".
   - Link each theme back to the specific units that support it.

3. **Build mental models**
   - Convert facts into reusable reasoning structures:
     - decision trees
     - cause/effect chains
     - responsibility models
     - risk/trade-off matrices
     - "if you see X in a scenario, think Y" patterns
   - Explain why the model helps on an exam scenario.

4. **Connect concepts**
   - Show how ideas relate across units instead of summarizing each unit in isolation.
   - Highlight dependencies, contrasts, and common confusions.
   - Include Microsoft-specific implementation context when the module ties a general concept to Azure, GitHub, Microsoft Defender, Entra, DevOps, or governance tooling.

5. **Produce exam-oriented outputs**
   Choose the output format that matches the user's request. If unspecified, provide:
   - a short module thesis
   - core themes
   - mental models
   - scenario triggers
   - common traps or misconceptions
   - a small set of conceptual practice questions with explanations

## Output style

Use clear, study-focused structure. Avoid dumping bullet-point summaries of every unit unless the user specifically asks for a unit-by-unit digest.

Prefer these sections:

- **Thesis:** one paragraph explaining what the module is really about.
- **Themes:** numbered conceptual themes with brief explanations.
- **Mental models:** reusable frameworks for answering scenario questions.
- **Scenario recognition:** signals in exam wording and what they imply.
- **Misconceptions:** what learners often overgeneralize or confuse.
- **Practice questions:** scenario-based questions with reasoning-first explanations.
- **Sources:** links to the module and units used.

## Practice question guidance

When creating practice questions:

- Test transfer of concepts, not recall of exact wording.
- Make distractors plausible by reflecting common misconceptions.
- Explain why the correct answer is correct and why each distractor fails.
- Prefer realistic Microsoft cloud, DevOps, security, governance, or architecture scenarios where relevant.
- Do not claim questions are official Microsoft exam questions.

## Depth calibration

Adjust depth to the user's request:

- **Quick revision:** thesis, top themes, traps.
- **Deep study:** full theme map, mental models, scenario patterns, practice questions.
- **Teaching mode:** analogies, progressive explanations, checks for understanding.
- **Assessment prep:** more scenario questions and answer reasoning.
