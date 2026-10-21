---
name: build
description: Build the next task test-first, or every task with "auto". Failing test, code, full suite, commit, then tick BUILD.md. Bugs start with a failing reproduction test.
disable-model-invocation: true
---

# Build

Implement the scoped tasks one thin, verified slice at a time. BUILD.md is the progress record, so a fresh session can pick up exactly where the last one stopped.

## Modes

- `/build`: the next unticked task, then stop.
- `/build auto`: show the remaining tasks, get one clear approval, then do every task up to the next checkpoint without stopping between them. Hedged replies are not approval.

## Find the task

1. Run `git branch --show-current`, `git status` and `git log --oneline -10`.
2. Pick the `.agents/NNN - Name/` folder whose CYCLE.md has a `branch:` line matching the current branch.
3. Otherwise use the only folder whose CYCLE.md has unticked phases. If several are open, ask which one.
4. If you are not on the task branch, switch to it or create it in its own worktree. Branch names start with `patch/`, `minor/` or `major/`.

## Reads

- CYCLE.md for size, branch and phases.
- BUILD.md for progress and notes from earlier sessions.
- SCOPE.md for the task's acceptance criteria, commands and boundaries. Bug and small work may have no SCOPE.md.
- `git log` and `git status` to confirm the last ticked task is committed.
- Only the code and tests the current task touches.

## Steps

### Start

- **BUILD.md missing, SCOPE.md present:** copy every task and checkpoint heading from SCOPE.md into BUILD.md as a checklist.
- **BUILD.md missing, no SCOPE.md (bug or small):** write BUILD.md from the request: one line of objective, the acceptance criteria and a short task list. For a bug, the first task is the failing reproduction test.
- **Uncommitted changes that are not this task's:** stop and ask before touching them.

### Each task

1. Read the task's acceptance criteria and the files it names.
2. **Red:** write a test for the expected behaviour and run it. It must fail for the right reason. For a bug, the test must reproduce the reported failure.
3. **Green:** write the minimum code to pass.
4. Run the full test suite, then the build or lint command from SCOPE.md.
5. Refactor only if needed, then rerun the suite.
6. Stage only the files this task touched, and commit on the task branch with a plain descriptive message.
7. Tick the task in BUILD.md with a one-line note: what changed, the commit hash, and anything the next task must know.

When a task has no testable behaviour (docs, config), the verification step from SCOPE.md stands in for the failing test.

### Stop and ask when

- You reach a checkpoint. Summarise and wait.
- A test or the build fails and the fix is not obvious after the debugging steps below.
- The scope is ambiguous, or the task needs a decision that SCOPE.md does not cover.
- The step is risky or hard to undo: auth or permissions, data migrations, deletions, secrets, deploys, pushes, or anything `git revert` cannot undo.

### Debugging

1. Reproduce the failure and read the full error.
2. Narrow it to the smallest failing case.
3. Form one hypothesis, test it, and fix the root cause, not the symptom.
4. Add a test that would have caught it.
5. Never weaken, skip or delete a test, or lower a threshold, to get to green.

## Writes

`.agents/NNN - Name/BUILD.md`:

```markdown
# Build: Name

- [x] Task 1: Title. Added contract test (9fb2f22)
- [ ] Task 2: Title

## Checkpoint 1
- [ ] Checkpoint 1 reviewed
```

Plus one commit per task on the task branch.

## Exit

1. Make sure every finished task is committed and ticked in BUILD.md.
2. If every task and checkpoint in BUILD.md is ticked, tick `- [x] build` in CYCLE.md. Do this last. Otherwise leave it unticked.
3. Print a short summary: tasks done this session, tests added, commits, and anything left or flagged. Then print the next command: `/build` while tasks remain, or `/review` when the build is complete.

## Rules

- One task, one commit. Never `git add -A`.
- Follow the patterns already in the code. Match its naming, layout and test style.
- Do not widen scope. Note anything extra you find in BUILD.md instead.
- Commit messages describe the change. They never mention AI tools.
