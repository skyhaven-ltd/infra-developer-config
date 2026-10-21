---
name: cycle
description: Run a whole task through the lifecycle from one session. Agree size and phases in CYCLE.md, scope inline, then run each build group and the review in fresh subagents, stopping at every approval.
disable-model-invocation: true
---

# Cycle

Orchestrate scope, build, review and ship so the main session stays small. Each heavy phase runs in a fresh subagent that reads the task folder, and only its summary comes back. The files in the task folder carry the work, never this chat.

## Find the task

1. Run `git branch --show-current` and `git status`.
2. Pick the `.agents/NNN - Name/` folder whose CYCLE.md has a `branch:` line matching the current branch.
3. Otherwise use the only folder whose CYCLE.md has unticked phases. If several are open, ask which one.
4. If none matches and the user has described new work, start a new task (step 1 below).

## Reads

- CYCLE.md, to find the first unticked phase and resume there.
- Only the headings and checklists of SCOPE.md, BUILD.md and REVIEW.md, enough to route. Subagents read the detail.
- The lifecycle skill files, by path. Each phase skill is a sibling of this skill's folder: `<this skill's folder>/../<phase>/SKILL.md`, such as `~/.claude/skills/build/SKILL.md`. Review personas are in `../review/references/`.

## Steps

### 1. Agree the cycle

1. Size the work and propose phases:

| Size | Phases |
| --- | --- |
| bug | build, review, ship |
| small | build, review, ship |
| medium | scope, build, review, ship |
| large | scope, build, review, ship, with one build run per checkpoint group |

2. Propose a branch name starting with `patch/`, `minor/` or `major/`.
3. Wait for agreement. Then create `.agents/NNN - Name/` (NNN is the highest existing number plus one) and write CYCLE.md:

```markdown
type: medium
branch: minor/short-name

- [ ] scope
- [ ] build
- [ ] review
- [ ] ship
```

4. Create the branch in its own worktree where the repo allows it.

### 2. Scope (inline)

Scope needs questions and approvals, which subagents cannot ask. Follow the scope skill in this session. When SCOPE.md is approved and `scope` is ticked, carry on.

### 3. Build (subagent per group)

For each checkpoint group in SCOPE.md, or the whole list for bug and small work:

1. Start one subagent with this brief:
   - Read `<path to build SKILL.md>` and follow it in `auto` mode for the next group only. Treat this brief as the approval.
   - Repository: path. Task folder: path. Branch: name.
   - Stop at the checkpoint, or at any condition where the skill says stop and ask. Do not push.
   - Return only: tasks done with commit hashes, test results, and any question or blocker.
2. Relay the summary to the user in a few lines.
3. On a blocker or question, ask the user, then start a fresh subagent with the answer added to the brief.
4. At each checkpoint, show the summary and wait for the user to continue.

Run the build groups one after another, never in parallel. They share the branch.

### 4. Review (fan-out from here)

Subagents cannot start subagents, so the cycle runs the fan-out itself:

1. Read the review skill's depth rule and apply it to `git diff --stat base...HEAD`.
2. For a fan-out, start three subagents in one turn, one per persona file in the review skill's `references/` folder (`code-reviewer.md`, `security-auditor.md`, `test-engineer.md`). Give each the repository, task folder, base branch and its persona path. Ask each to return only its report.
3. For an inline review, start one subagent told to follow the review skill and return the verdict and findings.
4. Merge the reports and write REVIEW.md exactly as the review skill describes, including the verdict rules and rollback plan. Tick `review` only on GO.
5. On NO-GO, show the blockers and ask whether to run a fix build group. That group's brief lists the findings to fix.

### 5. Ship (inline, on request)

Ship posts to a remote. Ask the user before you start. On a yes, follow the ship skill in this session.

## Writes

`.agents/NNN - Name/CYCLE.md`: created in step 1 and ticked as each phase finishes. The phases write their own files: SCOPE.md, BUILD.md, REVIEW.md and SHIP.md.

## Exit

1. Check each finished phase's file exists and its CYCLE.md item is ticked. If a subagent left one unticked, tick it only when that phase's own exit rule is met.
2. Print where the cycle stopped and why: approval needed, blocker, NO-GO, or shipped.
3. Print the next command: `/cycle` to resume, or the single phase command, such as `/build`, to run one phase by hand.

## Rules

- Keep this session lean. Do not read diffs or full files the subagents already read. Pass paths, not contents.
- Every approval comes from the user. A subagent's summary is never approval.
- Subagent briefs are self-contained: paths, branch, mode and stop conditions. They never rely on this chat.
- Without subagent support, run each phase in this session by following its skill, and suggest a fresh session between groups for large work.
