---
name: review
description: Review the task branch against SCOPE.md on five axes, fanning out to code, security and test reviewers for non-trivial diffs. Ends with GO or NO-GO and a rollback plan in REVIEW.md.
disable-model-invocation: true
---

# Review

Decide whether the task branch is ready to ship. The review checks the branch against what was agreed, not against taste.

## Find the task

1. Run `git branch --show-current` and `git status`.
2. Pick the `.agents/NNN - Name/` folder whose CYCLE.md has a `branch:` line matching the current branch.
3. Otherwise use the only folder whose CYCLE.md has unticked phases. If several are open, ask which one.
4. Find the base branch: `main`, or the repo's default branch if there is no `main`.

## Reads

- CYCLE.md for size and phases.
- SCOPE.md for acceptance criteria, decisions and boundaries. Bug and small work may have only BUILD.md.
- BUILD.md for what was built and any flagged notes.
- `git log --oneline base..HEAD`, `git diff --stat base...HEAD` and `git diff base...HEAD`.
- `.agents/CONSTRAINTS.md` if present: treat any weakened bar as Required.
- `references/security.md` when the diff touches input handling, auth, secrets, data access, dependencies or config.
- `references/performance.md` when the diff touches loops over data, queries, network calls, rendering or startup paths.

## Steps

### 1. Check it works

1. Confirm the working tree is clean and every BUILD.md task is ticked. Otherwise stop and say what is missing.
2. Run the full test suite and the build or lint commands from SCOPE.md. Record the results.
3. Map each acceptance criterion to the tests or evidence that prove it.

### 2. Choose the depth

Do a single inline pass only when all of these are true:

- two files or fewer
- under 50 changed lines
- no auth, data access, secrets, config or environment changes

Otherwise fan out. Start three subagents in one turn so they run in parallel. Give each one the task folder path, the base branch, and its persona file:

| Reviewer | Persona file |
| --- | --- |
| Code | `references/code-reviewer.md` |
| Security | `references/security-auditor.md` |
| Tests | `references/test-engineer.md` |

Tell each to read its persona file, SCOPE.md and the diff, and to return only its report. Where subagents are not available, run each persona yourself in turn.

### 3. Review on five axes

Whether inline or merging the reports, cover:

1. **Correctness**: meets every acceptance criterion; edge cases, error paths, state and concurrency.
2. **Readability**: names, control flow and layout match the repo's conventions.
3. **Architecture**: follows existing patterns; clean boundaries; no needless abstraction.
4. **Security**: untrusted input, secrets, authorisation, dependencies.
5. **Performance**: unbounded work, N+1 calls, blocking I/O, startup cost.

Also check for scope creep, leftover debug code, skipped or weakened tests, and whitespace-only or line-ending churn.

### 4. Classify and decide

| Severity | Meaning |
| --- | --- |
| Critical | Broken behaviour, data loss or an exploitable flaw. Blocks |
| Required | Must fix before shipping: missing test, wrong abstraction, poor error handling |
| Optional | Worth doing, not required |
| Nit | Style; the author may ignore |

Merge duplicates across reviewers. Promote Critical or High security findings to Critical. Every Critical and Required finding has a `file:line` and a specific fix.

The verdict is **NO-GO** if any Critical or Required finding is open, any test fails, or any acceptance criterion is unproven. Otherwise **GO**. A GO needs a rollback plan.

## Writes

`.agents/NNN - Name/REVIEW.md`:

```markdown
# Review: Name

Verdict: GO | NO-GO
Base: main (abc1234) → HEAD (def5678)
Depth: inline | fan-out

## Checks
- Tests: command and result
- Build/lint: command and result

## Acceptance criteria
- AC1: proven by …

## Findings
### Critical
### Required
### Optional
### Nits

## Done well

## Rollback plan
- Trigger: what would prompt a rollback
- Steps: exact commands
```

On a rerun, replace REVIEW.md and keep a one-line note of the previous verdict under `## History`.

## Exit

1. Save REVIEW.md.
2. On GO, tick `- [x] review` in CYCLE.md. Do this last. On NO-GO, leave it unticked.
3. Print the verdict and finding counts, then the next command: `/ship` on GO, or `/build` to fix the findings on NO-GO.

## Rules

- Review only. Do not fix code in this phase unless the user asks.
- Judge against SCOPE.md and the repo's conventions, not personal preference.
- If you are unsure about something, say so and suggest how to check it.
- Always include at least one specific thing that was done well.
