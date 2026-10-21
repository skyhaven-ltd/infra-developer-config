---
name: scope
description: Scope a task before code. Agree requirements and acceptance criteria, then break the work into ordered, verifiable tasks with checkpoints, recorded in SCOPE.md.
disable-model-invocation: true
---

# Scope

Turn a request into an agreed SCOPE.md that a fresh session can build from without chat history. Write no code in this phase.

## Find the task

1. Run `git branch --show-current` and `git status`.
2. Pick the `.agents/NNN - Name/` folder whose CYCLE.md has a `branch:` line matching the current branch.
3. Otherwise use the only folder whose CYCLE.md has unticked phases. If several are open, ask which one.
4. If none exists, agree the size (`bug`, `small`, `medium`, `large`) and phases with the user, then create the folder and CYCLE.md as the global instructions describe.

## Reads

- CYCLE.md for size, branch and phases.
- SCOPE.md if it exists: resume from where it stops.
- The user's request and any files they point at.
- The code the change touches: entry points, existing patterns, tests and how they run, build and lint commands.
- `.agents/CONSTRAINTS.md` if present.

## Steps

### 1. Requirements

1. Restate the objective in one or two sentences and list your assumptions.
2. Ask the questions that would change the design, a few at a time. Do not fill gaps silently.
3. Read enough code to ground the answers: name real files, commands and conventions.
4. Draft the Requirements part of SCOPE.md:
   - **Objective**: what and why, and who it is for.
   - **In scope** and **Out of scope**.
   - **Decisions**: each choice made and why.
   - **Acceptance criteria**: numbered, specific and testable (`AC1`, `AC2`, …).
   - **Commands**: test, build and lint commands for this repo.
   - **Boundaries**: always do, ask first, never do.
5. Stop for approval. Treat hedged replies as not approved.

For large work you may stop here: write SCOPE.md with `Status: requirements approved` and print `/scope` so a fresh session does the task breakdown.

### 2. Tasks

1. Map dependencies and order work bottom-up.
2. Slice vertically: each task delivers one working, testable path, not one layer.
3. Size each task at five files or fewer. Split anything bigger, or any title with "and".
4. Put risky or uncertain tasks early.
5. Add a checkpoint after every two or three tasks. A checkpoint is a review stop, and each group between checkpoints is one build session.
6. Write each task as:

```markdown
### Task N: Title
- Covers: AC1, AC3
- Do: one or two sentences
- Verify: exact command or check
- Files: likely paths
- Depends on: task numbers or none
```

7. Add **Risks** (risk, impact, mitigation) and **Open questions**.
8. Stop for approval of the task list.

## Writes

`.agents/NNN - Name/SCOPE.md` with these sections in order:

1. `Status:` line: `requirements approved` or `approved`
2. Objective
3. In scope / Out of scope
4. Decisions
5. Acceptance criteria
6. Commands
7. Boundaries
8. Tasks, with `## Checkpoint N` headings between groups
9. Risks
10. Open questions

Update SCOPE.md in place when replanning the same work. If it holds an unfinished scope for different work, stop and ask.

## Exit

1. Save SCOPE.md with `Status: approved`.
2. Tick `- [x] scope` in CYCLE.md. Do this last.
3. Print a two-line summary: task count and checkpoint count, then the next command, `/build`.

## Rules

- No implementation, scaffolding or test code in this phase.
- Every acceptance criterion is covered by at least one task, and every task verifies something.
- Prefer existing patterns in the repo over new ones, and name them.
- Keep SCOPE.md factual and short. It is read at the start of every later phase.
