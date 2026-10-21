# Agent workflow

Every change runs through up to four phases: `/scope`, `/build`, `/review` and `/ship`. `/cycle` runs them all from one session. The skills live in `skills/lifecycle/` and the installer links them into Claude Code and Codex. `system/SYSTEM.md` sets the rules on top. Each skill writes one file named after itself in the task folder, and reads the files the earlier phases wrote, so a new session needs only the phase command.

## 1. Agree the size first

At the start of a task the agent states the size and the phases it will run. Confirm or correct it before work starts. The agent then records both in `.agents/NNN - Name/CYCLE.md` and ticks each phase as it finishes.

| Size | Typical work | Phases |
| --- | --- | --- |
| Bug | Wrong behaviour you can reproduce | `/build`, `/review`, `/ship`. Describe the bug in the `/build` request |
| Small | A change to one or two files with no open decisions | `/build`, `/review`, `/ship`. Describe the change in the `/build` request |
| Medium | One feature across several files | `/scope`, `/build`, `/review`, `/ship` |
| Large | Several modules, or requirements still unclear | All four, with one build run per checkpoint group |

## 2. Run each phase

| Phase | Type | What happens | You do | Output |
| --- | --- | --- | --- | --- |
| Scope | `/scope <what you want>` | Agent asks questions, writes requirements and acceptance criteria, then splits the work into small tasks with checkpoints. No code | Approve the requirements, then the tasks | `SCOPE.md` |
| Build | `/build` | Agent works one task at a time: failing test, code, check, commit, tick `BUILD.md`. Stops at each checkpoint | Review at each checkpoint | Commits, `BUILD.md` |
| Review | `/review` | Checks run, then code, security and test reviewers look at the diff in parallel. Very small diffs get one inline review. Ends in a go or no-go with a rollback plan | Decide which findings to fix | `REVIEW.md` |
| Ship | `/ship` | Pushes the branch and opens the pull request, after a go verdict on the latest commit | Ask for it | `SHIP.md` |

`/build auto` runs every task up to the next checkpoint after one approval. It still tests and commits each task, and stops on failures or risky steps.

## 3. Run the whole cycle

`/cycle` agrees the size, runs scope in the session, then runs each build group and the review in fresh subagents so the main session stays small. It stops at every approval, checkpoint, blocker and no-go, and asks before it ships. Run `/cycle` again to resume from the first unticked phase.

## 4. Fix a bug

1. Run `/build` with the bug and how to see it.
2. The agent reproduces it with a failing test, finds the cause and fixes it there.
3. The test now passes and stays as a guard against the bug returning.
4. The agent commits the fix. Run `/review`, then `/ship` when you want the pull request.

## 5. Find the files

Everything the agent creates sits under `.agents/` at the repository root. The global gitignore excludes it, so nothing there is ever committed.

```text
.agents/
  CONSTRAINTS.md              project quality bar
  001 - NEMS Company Role Validity/
    CYCLE.md                  size and agreed phases, ticked as each finishes
    SCOPE.md                  requirements and tasks
    BUILD.md                  build checklist, ticked with commit hashes
    REVIEW.md                 verdict, findings and rollback plan
    SHIP.md                   pushed branch and pull request
    supporting/               notes, captures, scripts, screenshots
```

- Task numbers are three digits and increase by one per repository.
- `CYCLE.md` is the progress record. Unticked phases mean the task is still open.
- The lifecycle band above the Claude Code prompt shows the phases of the task whose `CYCLE.md` `branch:` line matches the current branch, with the session's context window and cost. A task without `branch:` never shows. Without phases in `CYCLE.md` it assumes all four; with no matching task it reads git state. Older folders that use `spec`, `plan`, `test` and `TODO.md` still show, folded into scope and build.
- If two tasks are open, the agent asks which one to work on.

## 6. Move between sessions

Start a fresh session for each phase of medium and large work, or let `/cycle` run them in subagents. The files carry the work forward, not the chat. In the new session on the task's branch, type only the next phase command, such as `/build`. The skill finds the task from the branch and reads what it needs.

If a long build fills the session, stop at a checkpoint and run `/build` again in a new session.

## 7. Commit, push and open pull requests

- `/build` commits after each task passes its check. Commits stay local.
- `/ship` pushes and opens the pull request, and only when you run it.
- Branch names must start with `patch/`, `minor/` or `major/`.
- Commit messages and pull requests never mention Claude, Codex or AI generation.

## 8. Quick prompts

| Goal | Prompt |
| --- | --- |
| Start a feature | `/scope <describe the feature and why>` |
| Small fix | `/build Fix <bug>. It happens when <steps>.` |
| Run it all | `/cycle <describe the work>` |
| Resume work | The next phase command, such as `/review`, or `/cycle` |
| Ship | `/ship` |
