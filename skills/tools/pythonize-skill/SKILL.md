---
name: pythonize-skill
description: Refactor existing Codex or Claude skills into Python-backed workflows that offload deterministic inspection, validation, parsing, file operations, API/CLI orchestration, and repeatable command sequences to bundled Python scripts while keeping the LLM responsible for judgement, explanations, grouping decisions, commit messages, summaries, reviews, and user-facing trade-offs. Use when asked to automate, script, speed up, reduce token use, or make a target skill more deterministic.
---

# Pythonize Skill

Refactor a target skill so `SKILL.md` becomes a thin orchestration guide and bundled Python scripts perform the repeatable work.

## Default workflow

1. Identify the target skill directory. If the user gives only a name, search the central `skills/` tree for a matching folder.

2. Run the analyzer from this skill:

   ```powershell
   python "<this-skill-dir>\scripts\pythonize-skill-helper.py" analyze --target "<target-skill-dir>" --json
   ```

3. Review the analyzer output and define the boundary:
   - Move deterministic work to Python: status checks, parsing, validation, grouping heuristics, file discovery, command orchestration, JSON/YAML manipulation, API/CLI wrappers, idempotent writes, and safety gates.
   - Keep judgement in the LLM: user intent, risk acceptance, prose, commit messages, PR descriptions, code review findings, study explanations, architectural trade-offs, and final summaries.

4. If the target skill does not already have an appropriate helper, scaffold one:

   ```powershell
   python "<this-skill-dir>\scripts\pythonize-skill-helper.py" scaffold --target "<target-skill-dir>"
   ```

5. Implement the target helper script. Prefer this interface:
   - `inspect`: side-effect-free; returns compact JSON for the LLM to judge.
   - `plan`: optional; creates or validates a structured plan file.
   - `apply`: performs side effects from an explicit plan; supports `--dry-run` when practical.

6. Update the target `SKILL.md` so it tells future agents:
   - which helper command to run first;
   - which JSON fields to inspect;
   - when to stop or ask the user;
   - what the LLM must still decide;
   - what plan JSON shape to create, if any;
   - how to run the side-effecting command.

7. Test before finishing:

   ```powershell
   python -m py_compile "<target-skill-dir>\scripts\<helper>.py"
   python "<skill-creator-dir>\scripts\quick_validate.py" "<target-skill-dir>"
   ```

   Also run representative helper tests against a temporary or safe fixture. Do not test destructive operations against live resources.

## Script design rules

- Use Python standard library unless a dependency is already required by the target skill.
- Emit compact JSON by default. Do not print full diffs, large logs, secrets, or whole files.
- Write large artifacts to files and return paths in JSON.
- Validate repository-relative and filesystem paths before writing, moving, or deleting.
- Make `inspect` read-only and safe to run repeatedly.
- Require an explicit plan file for multi-step side effects.
- Keep script output stable so both Codex and Claude can use it.
- Fail closed with clear non-zero exits and machine-readable errors.
- Prefer idempotent operations and dry-run support.

## Target `SKILL.md` pattern

Keep target skills short. A good Python-backed skill usually contains:

````markdown
Use the bundled Python helper for deterministic checks and execution. Use the LLM only for judgement: <specific judgement tasks>.

1. Run inspect:
   ```powershell
   python "<skill-dir>\scripts\<helper>.py" inspect --target "<target>" --json
   ```
````

2. Stop or ask if `<risk field>` is present.
3. Create `<plan>.json` outside the target repo/folder.
4. Run apply:
   ```powershell
   python "<skill-dir>\scripts\<helper>.py" apply --target "<target>" --plan "<plan>.json"
   ```
5. Report concise results.

```

## When not to pythonize heavily

Do not force a script when the skill is mostly judgement, teaching, creative writing, or one-off reasoning. In those cases, only add small validators or artifact extractors if they remove repeated mechanical work.
```
