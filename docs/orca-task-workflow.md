# Orca task workflow

Use three fresh orchestrator sessions for substantial changes: plan, implement, and review. The shared policy is section 8 of `system/SYSTEM.md`. Its existing links at `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` load that policy globally. Existing instructions remain in force. No project `AGENTS.md` or `CLAUDE.md` is needed.

## Prepare a machine

1. Pull this configuration repository. Linked instructions update immediately; if your installation uses copies, run `scripts/Install-DeveloperConfig.ps1` after pulling.
2. Open Orca and enable orchestration under Settings > Experimental if it is disabled.
3. Install the bundled skills for both agents once on each machine:

   ```powershell
   orca skills install --skill orca-cli --skill orchestration --agent claude-code,codex
   ```

4. Start a fresh agent session in Orca so it discovers the skills and updated global instructions. Select Astra or Fable with high effort for the orchestrator; use extra high for difficult architecture or unresolved failures.

Read-only checks:

```powershell
orca status --json
orca orchestration worker-list --json
orca skills installed --json
```

The workflow needs an available provider and model, not just a model name in the instructions. Worker launch receipts distinguish requested and effective settings. Workers use the authorized defaults in `SYSTEM.md`: Luna/Haiku for narrow searches, Sol/Sonnet for implementation and testing, and Astra/Fable for demanding review. A provider limitation must be reported rather than silently substituted.

Orca's skills are installed separately from this repository's managed skills. Updating developer-config alone does not install Orca skills on another machine. The guides are loaded from the installed Orca executable, keeping commands matched to its version.

## Prepare a project

Use one task workspace for all three phases. A fresh agent session in the same workspace preserves the code, including uncommitted changes. Creating another worktree gives a separate checkout and needs an explicit integration strategy.

Keep private files ignored using your existing global Git ignore or the local exclude file returned by `git rev-parse --git-path info/exclude`. For private project links and task notes, the local patterns are:

```text
/AGENTS.md
/CLAUDE.md
/.claude/
```

Preserve existing exclude rules. These patterns do not untrack files that are already committed. Do not delete or untrack existing repository instructions as part of setup. The workflow checks task-note exclusions before creating its folder.

On the configured Windows workstation, `.gitignore_global` excludes `.claude`, `AGENTS.md`, and `CLAUDE.md`. These are machine-local rules, not committed project files. Check an intended private path with:

```powershell
git check-ignore -v --no-index -- ".claude/001 - Example/PLAN.md" AGENTS.md CLAUDE.md
```

For workers in separate worktrees, add `.claude` under Orca Settings > Repository > Worktree Shared Paths. The directory must exist in the primary checkout. Verify that each worker can read the selected task folder; do not assume existing worktrees received newly configured sharing. Each task has its own folder, and only its orchestrator writes the main handoff files. Shared paths transfer context, not uncommitted application changes. Use explicit paths in prompts even when ignored files do not appear in the agent's file picker.

## Phase 1: plan

Open a fresh Astra/Fable session in the task workspace and paste:

```text
Use the Orca planning phase from our global instructions.

Task: <describe the problem and desired outcome>
Constraints: <relevant boundaries, or omit this line>

Create the next numbered .claude task directory automatically.
Supervise independent workers for repository exploration and requirements/test
investigation, using the authorized role models. Validate their evidence.
Write PLAN.md and CONTEXT.md with ownership, dependencies, acceptance criteria,
verification commands, current code state, and an exact implementation prompt.
Complete planning only and settle the workers before ending the session.
```

The orchestrator returns the chosen folder, for example `.claude/001 - Fix Login Timeout/`. It writes a plan without changing application code. Resolve material open questions before starting implementation. Routine folder names and worker assignments do not need another approval.

## Phase 2: implement

Start a fresh Astra/Fable session in the same workspace. Use the folder returned by planning:

```text
Use the Orca implementation phase for ".claude/001 - Fix Login Timeout".

Read CONTEXT.md and PLAN.md and verify the current code state.
Supervise implementation workers with explicit file ownership and a designated
tester. Use the authorized role models and resolve failures within scope.
Verify the stable integrated result against the acceptance criteria.
Write IMPLEMENTATION.md with actual changes, plan deviations and test outcomes.
Update CONTEXT.md with an exact fresh-review prompt and settle the workers.
Complete implementation only; do not commit or push unless separately authorized.
```

One implementation worker plus a tester is the starting point. Add implementation workers for independent components with disjoint file ownership. The tester may prepare meaningful checks from requirements while implementation proceeds, but final verification runs against the integrated result. The orchestrator writes handoff files and dispatches application changes to workers.

## Phase 3: review

Start another fresh Astra/Fable session in the same workspace:

```text
Use the Orca review phase for ".claude/001 - Fix Login Timeout".

Read CONTEXT.md, PLAN.md and IMPLEMENTATION.md and verify the code state.
Supervise fresh reviewers for correctness, test gaps and relevant design risks.
Validate findings against the actual code and original requirements.
Dispatch necessary fixes to an implementation owner and recheck affected behaviour.
Write REVIEW.md with evidence, the reviewed code state, outstanding issues and
a final verdict. Update CONTEXT.md and settle the workers before finishing.
Do not commit or push unless separately authorized.
```

The review session uses new reviewers, rather than reusing implementation workers as the only reviewers. Add security or browser/UI verification when the change warrants it. Record unavailable checks as limitations, not passes. Review fixes are dispatched and verified in this phase; a material scope change needs an updated plan.

## Task files and resumption

```text
.claude/
  001 - Fix Login Timeout/
    CONTEXT.md
    PLAN.md
    IMPLEMENTATION.md
    REVIEW.md
```

Files appear as their phases complete; do not create empty completion reports in advance. `CONTEXT.md` stays compact and records the request, constraints, decisions, phase/status, branch/worktree, base/current commit, uncommitted work, verification, blockers, and the exact next prompt. The other files preserve intended work, actual work, and review evidence respectively.

Between phases, use a new conversation or terminal in the same Orca workspace rather than resuming the preceding conversation. Finish worker settlement and save the handoff before clearing context. Neither a context file nor an old Dispatch ID authorizes taking over a live worker. If interrupted with workers still active, reconcile the recorded Run and Dispatches through Orca's current recovery guide before launching replacements.

For small tasks, explicitly request combined planning and implementation. Keep independent review when the risk warrants it. After a successful review, ask separately to commit and push, or to commit, push and create a PR; those operations continue to use the existing skills.

References: [Orca orchestration](https://www.onorca.dev/docs/cli/orchestration), [worktree context sharing](https://www.onorca.dev/docs/model/worktrees#shared-directories--gitignored-files). Prefer the version-matched guides from `orca skills get orchestration` and `orca skills get orca-cli` when the installed command differs from a web example.
