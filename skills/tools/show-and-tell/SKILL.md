---
name: show-and-tell
description: Analyse a Git commit or commit range and prepare a stateful, non-technical sprint show-and-tell run sheet with outcomes, audience-friendly explanations, and a safe live demonstration. Use when asked to showcase, demo, present, or explain completed work to stakeholders who are not interested in source-code details.
disable-model-invocation: true
---

# Prepare a show and tell

Turn repository evidence into a short stakeholder story and a reliable live demonstration. Focus on what changed for a user or the organisation, not how the code was written.

## Inputs

Require a commit hash. Accept an optional baseline, output path, audience, and time limit. If no baseline is supplied, compare the commit with its first parent. For a root commit, use Git's empty tree. Do not assume that every changed file represents a stakeholder-visible outcome.

## Workflow

1. Confirm the working repository and resolve the commit without changing the worktree.
2. Run the bundled inspector:

   ```powershell
   python "<skill-dir>\scripts\show-and-tell-helper.py" --repo "." --commit "<commit>" --json
   ```

   Add `--baseline "<baseline>"` when supplied.
3. Read the files and diff portions needed to understand behaviour. Use the `diff_command` from the inspector. Also inspect relevant tests, documentation, configuration, issue references, and commit messages. Treat commit messages as claims to verify against the diff.
4. Group related file edits into stakeholder-visible outcomes. Omit refactors, formatting, dependency churn, and implementation detail unless they materially affect risk, reliability, cost, security, or user experience.
5. Identify what can be demonstrated from local evidence. Never invent a UI, environment, result, metric, or business benefit. Label reasonable but unverified effects as `Expected` and list what needs confirmation.
6. Create or update the requested Markdown run sheet. Default to `SHOW-AND-TELL.md` in the repository root. Start from `assets/show-and-tell-template.md` when it does not exist. Preserve useful notes from prior preparation and update the document in place for statefulness.
7. Tailor the run sheet for speaking aloud:
   - Lead with the problem and outcome.
   - Use plain language and short sentences.
   - Replace technology names with their practical meaning.
   - Include only the minimum context needed to understand the value.
   - Write exact live-demo actions and a short narration cue for each action.
   - Include a fallback using screenshots, logs, test output, or a concise verbal explanation if the live path fails.
8. Validate every factual claim against repository evidence. Mark unknown stakeholder context, production status, metrics, credentials, or environment details as `TODO` rather than guessing.
9. Rehearse non-destructively where possible. Do not deploy, modify shared systems, expose secrets, or invoke paid/external services merely to prepare the showcase. Clearly separate preparation commands from actions the presenter must perform live.

## Output standard

Keep the main story and demo steps visible without excessive scrolling. Put technical evidence in the final reference section. A good run sheet answers:

- What problem did this solve?
- What is different now?
- Why should this audience care?
- What exactly will they see live?
- How will the presenter recover if the demo fails?

Report the run-sheet path, the comparison used, any unverified claims, and whether the demo was rehearsed. Do not commit or push unless explicitly requested through the required Git skill.
