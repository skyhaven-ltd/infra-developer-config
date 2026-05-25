# Learning-app frontmatter template

Canonical Markdown frontmatter for notes the self-hosted learning review app (`app-learning-review`) ingests. Shared by `learn-content` and `organise-vault` skills. Do not diverge.

```yaml
---
title: "<title>"
created: YYYY-MM-DD
source_type: <learning-synthesis | ad-hoc-note>
sources:
  - "<url-or-source>"
status: inbox
confidence: medium
tags:
  - inbox
  - <topic-tag>
learning_status: needs-questions
learning_question_goal: 6
learning_question_types:
  - multiple-choice
  - short-answer
  - rubric
  - categorisation
learning_generation_notes: "<short hint for Codex on what to emphasise>"
---
```

## Field rules

- `source_type` is the only field whose value reflects origin. `learn-content` writes `learning-synthesis`; `organise-vault` writes `ad-hoc-note`. All other fields are identical across skills.
- `learning_status: needs-questions` is the only value the app's scan picks up. Do not set `active`, `stale`, or `skip` — those belong to the app.
- `learning_question_types` lists every type by default. Remove any type that does not fit the source material; do not invent new types.
- `learning_question_goal` is the target count. Range 1-20. Default 6.
- `learning_generation_notes` is optional but useful for steering Codex.
- Add topic-specific tags after `inbox` as needed. The app filters notes by these tags.

## Body rules

- Do not pre-populate a `## Practice questions` section. The app stores questions in its own database; the markdown body must be pure conceptual content.
- Always include a `## Sources` section with source links or file paths when provenance exists.
