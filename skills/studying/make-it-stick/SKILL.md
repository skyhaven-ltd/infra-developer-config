---
name: make-it-stick
description: Test a user on the contents of a Markdown file using evidence-informed learning principles from Make It Stick. Use when the user asks to be quizzed, tested, drilled, revised, or helped to remember a .md file, note, study guide, README, documentation page, or pasted Markdown content.
---

# Make It Stick

## Overview

Use the Markdown source as the syllabus, then run an interactive retrieval-practice session. Prefer productive struggle, short feedback, and repeated recall over passive summaries.

## Core Principles

- **Retrieval practice:** ask the user to produce answers from memory before showing explanations.
- **Spacing:** return to missed or high-value ideas later in the same session, and suggest follow-up review intervals.
- **Interleaving:** mix headings, concepts, definitions, procedures, examples, and edge cases instead of testing one section exhaustively.
- **Elaboration:** ask "why", "how", "compare", and "give an example" questions that connect ideas.
- **Generation:** ask the user to predict, infer, or solve before revealing the source wording.
- **Calibration:** have the user rate confidence occasionally, then compare confidence with correctness.
- **Desirable difficulty:** make questions challenging but answerable from the file; avoid trick questions and rote fill-in unless exact wording matters.
- **Feedback:** give concise corrective feedback after each answer, then move on; do not dump the whole note.

## Workflow

1. **Load the Markdown file**
   - If the user provides a path, read the file directly.
   - If the user pastes Markdown, use the pasted content.
   - If no file/content is provided, ask for the Markdown path or content.
   - Preserve YAML frontmatter as metadata, not primary quiz content, unless the user asks to test it.

2. **Build a mental model of the file**
   - Identify headings, key claims, definitions, processes, commands, examples, decisions, warnings, and dependencies.
   - Prioritize concepts that are central, surprising, frequently connected, procedural, or easy to confuse.
   - For very long files, sample across all major sections rather than only the beginning.

3. **Create a hidden question queue**
   - Use a mixed set of question types:
     - free recall: "What are the main reasons...?"
     - concept check: "What does X mean?"
     - application: "Given scenario Y, what would you do?"
     - comparison: "How is X different from Y?"
     - sequencing: "What are the steps in order?"
     - error diagnosis: "What is wrong with this approach?"
     - generation: "Predict the consequence of..."
   - Avoid multiple choice by default. Use it only when the user asks for an easier mode or when discriminating similar options is the point.
   - Keep exact-answer questions rare unless the file contains commands, names, limits, dates, syntax, or definitions that need precision.

4. **Run the quiz interactively**
   - Ask one question at a time and wait for the user's answer.
   - Do not reveal the answer in the question.
   - After the user answers:
     - mark it `Correct`, `Partly correct`, or `Not yet`;
     - give the shortest useful explanation;
     - quote or closely paraphrase only the relevant part of the Markdown;
     - record missed ideas for later retrieval.
   - Every 3-5 questions, re-test one missed or important idea in a different form.

5. **Adapt difficulty**
   - If the user is struggling, narrow the question, add cues, or switch temporarily to recognition before returning to recall.
   - If the user is doing well, increase transfer: scenarios, comparisons, exceptions, and synthesis.
   - Ask for confidence ratings when useful: `Confidence 1-5?` Use mismatches to identify overconfidence or underconfidence.

6. **Close the session**
   - Summarize strengths, weak spots, and misconceptions.
   - List 3-7 follow-up questions for spaced review.
   - Suggest a review cadence, such as later today, tomorrow, and in a week, adjusted to the user's performance.

## Session Defaults

- Default length: 10 questions unless the user specifies otherwise.
- Default style: conversational, one question per turn.
- Default grading: strict on core meaning, lenient on wording.
- Default source handling: keep the Markdown open as the answer key, but do not summarize it before testing unless asked.
- Default final output: concise performance summary plus next review prompts.

## Response Pattern

Start with:

```text
I’ll test you using retrieval practice and mixed question types. I’ll ask one question at a time and give feedback after each answer.

Question 1/N: ...
```

Feedback format:

```text
Partly correct.
You got: ...
Missing: ...
Remember it as: ...

Question 2/N: ...
```

Final format:

```text
Session summary
- Strong: ...
- Needs review: ...
- Re-test later: ...
```
