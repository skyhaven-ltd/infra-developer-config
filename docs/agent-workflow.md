# Agent workflow

Every change runs through five phases: `/spec`, `/plan`, `/build`, `/review` and `/ship`. The agent-skills plugin supplies them in Claude Code and Codex, and `system/SYSTEM.md` sets the rules on top. You only type the phase command; the agent loads any other skill it needs from the task.

## 1. Agree the size first

At the start of a task the agent states the size and the phases it will run. Confirm or correct it before work starts. The agent then records both in `.agents/NNN - Name/CYCLE.md` and ticks each phase as it finishes.

| Size | Typical work | How to run it |
| --- | --- | --- |
| Small | Bug fix, or a change to one or two files with no open decisions | One session. Describe the change; the agent builds, tests, reviews and commits it. The task folder holds only `CYCLE.md` |
| Medium | One feature across several files | `/plan`, `/build`, `/review`, `/ship`. Put the short spec in the `/plan` request |
| Large | Several modules, or requirements still unclear | All five phases, one fresh session each |

## 2. Run each phase

| Phase | Type | What happens | You do | Output |
| --- | --- | --- | --- | --- |
| Spec | `/spec <what you want>` | Agent asks questions, then writes requirements, decisions and acceptance criteria. No code | Answer questions, approve the spec | `SPEC.md` |
| Plan | `/plan` | Agent reads the code and splits the work into ordered tasks with checks and checkpoints. No code | Approve the plan | `PLAN.md`, `TODO.md` |
| Build | `/build` | Agent works one task at a time: failing test, code, check, commit, tick `TODO.md`. Stops at each checkpoint | Review at each checkpoint | Commits, updated `TODO.md` |
| Review | `/review` | Fresh review of the changes for correctness, readability, architecture, security and performance | Decide which findings to fix | `REVIEW.md` |
| Ship | `/ship` | Three reviewers (code, security, tests) run in parallel, then a go or no-go with a rollback plan | Ask for the push and pull request | `SHIP.md` |

`/build auto` runs every task in the approved plan in one pass. It still tests and commits each task, and stops on failures or risky steps. Use it for routine plans only.

## 3. Fix a bug

1. Describe the bug and how to see it.
2. The agent reproduces it with a failing test, finds the cause and fixes it there.
3. The test now passes and stays as a guard against the bug returning.
4. The agent commits the fix. Review the commit, then ask for the push.

`/test` runs the same loop on request. The debugging skill also loads automatically when a build or test breaks.

## 4. Find the files

Everything the agent creates sits under `.agents/` at the repository root. The global gitignore excludes it, so nothing there is ever committed.

```text
.agents/
  CONSTRAINTS.md              project quality bar, from /constraints
  ADR/
    001 - Use Durable Functions.md
  001 - NEMS Company Role Validity/
    CYCLE.md                  size and agreed phases, ticked as each finishes
    SPEC.md
    PLAN.md
    TODO.md
    REVIEW.md
    SHIP.md
    supporting/               notes, captures, scripts, screenshots
```

- Task numbers are three digits and increase by one per repository.
- `TODO.md` is the progress record. Unticked items mean the task is still open.
- The lifecycle band above the Claude Code prompt shows the phases of the task whose `CYCLE.md` `branch:` line matches the current branch, with the session's context window and cost. A task without `branch:` never shows. Without phases in `CYCLE.md` it assumes all five; with no matching task it reads git state.
- If two tasks are open, the agent asks which one to work on.

## 5. Move between sessions

Start a fresh session for each phase of medium and large work. This keeps the context small and accurate. The files carry the work forward, not the chat. Open the new session with:

```text
Continue task NNN - Name in this repository. Read .agents/NNN - Name/ and git status, then run /build.
```

Swap `/build` for the next phase. If a long build fills the session, stop at a checkpoint and open a new session with the same prompt.

## 6. Commit, push and open pull requests

- `/build` commits after each task passes its check. Commits stay local.
- The agent pushes and opens a pull request only when you ask, for example "push and open a PR".
- Branch names must start with `patch/`, `minor/` or `major/`.
- Commit messages and pull requests never mention Claude, Codex or AI generation.

## 7. Know when other skills run

The agent picks these from the task. You never have to name them, but you can ask for one directly.

| Skill | Runs when |
| --- | --- |
| `git-workflow-and-versioning` | Committing, branching or opening a pull request |
| `debugging-and-error-recovery` | A build or test fails, or behaviour is wrong |
| `ci-cd-and-automation` | You change a pipeline |
| `deprecation-and-migration` | You remove or migrate something |
| `observability-and-instrumentation` | You add logging, metrics or alerts |
| `documentation-and-adrs` | Rarely by itself. Ask "write an ADR for this" to record a decision |
| `interview-me` | Ask "interview me" when you are unsure what you want |
| `doubt-driven-development` | High-risk or unfamiliar work. Ask "doubt this" to stress-test a decision |

## 8. Quick prompts

| Goal | Prompt |
| --- | --- |
| Start a feature | `/spec <describe the feature and why>` |
| Small fix | `Fix <bug>. It happens when <steps>.` |
| Resume work | `Continue task NNN - Name. Read .agents/NNN - Name/ and git status, then run /<phase>.` |
| Ship | `/ship`, then `push and open a PR to main` |
