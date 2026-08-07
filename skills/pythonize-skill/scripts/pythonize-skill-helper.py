#!/usr/bin/env python3
"""Analyze and scaffold Python-backed agent skills.

This helper is intentionally generic. It does not replace LLM judgement; it
extracts stable facts about a target skill and creates a safe starter helper
script when requested.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DETERMINISTIC_KEYWORDS = (
    "run",
    "execute",
    "check",
    "detect",
    "validate",
    "parse",
    "format",
    "list",
    "find",
    "search",
    "stage",
    "commit",
    "push",
    "pull",
    "clone",
    "status",
    "diff",
    "read",
    "write",
    "copy",
    "move",
    "rename",
    "delete",
    "create",
    "generate",
    "extract",
    "convert",
    "sort",
    "deduplicate",
    "terraform",
    "az ",
    "gh ",
    "git ",
    "python",
    "powershell",
    "json",
    "yaml",
    "frontmatter",
)

JUDGEMENT_KEYWORDS = (
    "ask",
    "decide",
    "choose",
    "review",
    "summarize",
    "summarise",
    "explain",
    "recommend",
    "judge",
    "trade-off",
    "tradeoff",
    "reason",
    "infer",
    "classify",
    "prioritize",
    "prioritise",
    "write a message",
    "commit message",
    "pr description",
    "user approval",
)

COMMAND_PATTERN = re.compile(r"`([^`]+)`|```(?:\w+)?\s*(.*?)```", re.DOTALL)
STEP_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class PythonizeSkillError(RuntimeError):
    """Expected, user-facing failure."""


@dataclass(frozen=True)
class SkillMetadata:
    name: str | None
    description: str | None
    body: str


def load_skill(path: Path) -> tuple[Path, str, SkillMetadata]:
    target = path.expanduser().resolve()
    if target.is_file():
        skill_file = target
        target = target.parent
    else:
        skill_file = target / "SKILL.md"

    if not skill_file.exists():
        raise PythonizeSkillError(f"Target skill does not contain SKILL.md: {target}")

    text = skill_file.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    frontmatter = match.group(1) if match else ""
    body = text[match.end() :] if match else text
    metadata = SkillMetadata(
        name=parse_frontmatter_value(frontmatter, "name"),
        description=parse_frontmatter_value(frontmatter, "description"),
        body=body,
    )
    return target, text, metadata


def parse_frontmatter_value(frontmatter: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*?)\s*$", re.MULTILINE)
    match = pattern.search(frontmatter)
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
        value = value[1:-1]
    return value or None


def slug_to_module(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "skill"


def helper_stem(value: str) -> str:
    stem = slug_to_module(value)
    if not stem.endswith("-helper"):
        stem = f"{stem}-helper"
    return stem


def extract_steps(body: str) -> list[str]:
    steps: list[str] = []
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = STEP_PATTERN.match(line)
        if match:
            steps.append(match.group(1).strip())
    return steps


def looks_like_command(value: str) -> bool:
    value = value.strip()
    if not value or value.startswith(('{', '[', ']', '}')):
        return False
    command_prefixes = (
        "python",
        "py ",
        "git",
        "gh",
        "az",
        "terraform",
        "pwsh",
        "powershell",
        "Get-",
        "Set-",
        "New-",
        "Remove-",
        "Copy-",
        "Move-",
        "./",
        ".\\",
    )
    lower = value.lower()
    return value.startswith(command_prefixes) or lower.startswith(tuple(prefix.lower() for prefix in command_prefixes))


def extract_commands(text: str) -> list[str]:
    commands: list[str] = []
    for match in COMMAND_PATTERN.finditer(text):
        inline = match.group(1)
        fenced = match.group(2)
        if inline:
            candidate = inline.strip()
            if looks_like_command(candidate):
                commands.append(candidate)
        elif fenced:
            stripped = fenced.strip()
            if stripped.startswith(("{", "[")):
                continue
            for line in fenced.splitlines():
                candidate = line.strip()
                if candidate and not candidate.startswith("#") and looks_like_command(candidate):
                    commands.append(candidate)
    return dedupe_preserve_order(commands)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    return [keyword for keyword in keywords if keyword in lower]


def classify_lines(lines: list[str]) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for line in lines:
        deterministic = keyword_hits(line, DETERMINISTIC_KEYWORDS)
        judgement = keyword_hits(line, JUDGEMENT_KEYWORDS)
        if deterministic and judgement:
            classification = "mixed"
        elif deterministic:
            classification = "deterministic_candidate"
        elif judgement:
            classification = "llm_judgement"
        else:
            classification = "unclear"
        classified.append(
            {
                "text": line,
                "classification": classification,
                "deterministic_hits": deterministic[:8],
                "judgement_hits": judgement[:8],
            }
        )
    return classified


def existing_resources(target: Path) -> dict[str, list[str]]:
    resources: dict[str, list[str]] = {}
    for folder in ("scripts", "references", "assets", "agents"):
        path = target / folder
        if path.exists() and path.is_dir():
            resources[folder] = sorted(str(child.relative_to(target)).replace("\\", "/") for child in path.rglob("*") if child.is_file())
        else:
            resources[folder] = []
    return resources


def estimate_pythonization_score(classified_steps: list[dict[str, Any]], commands: list[str], resources: dict[str, list[str]]) -> int:
    score = 0
    score += sum(2 for step in classified_steps if step["classification"] == "deterministic_candidate")
    score += sum(1 for step in classified_steps if step["classification"] == "mixed")
    score += min(len(commands), 6)
    if resources.get("scripts"):
        score += 2
    return min(score, 10)


def recommendations(
    score: int,
    classified_steps: list[dict[str, Any]],
    commands: list[str],
    helper_name: str,
    existing_python_helpers: list[str],
) -> list[str]:
    recs: list[str] = []
    if score >= 6:
        recs.append("Strong candidate for a Python-backed workflow.")
    elif score >= 3:
        recs.append("Partial Pythonization is likely useful; script the repeated checks and keep the prose-heavy parts in SKILL.md.")
    else:
        recs.append("Only add a small helper if there is repeated mechanical work; the skill appears judgement-heavy.")

    if commands:
        recs.append("Wrap repeated shell/API commands in a helper so the skill can consume compact JSON instead of raw logs.")
    if any(step["classification"] == "mixed" for step in classified_steps):
        recs.append("Split mixed steps into script-produced facts and LLM decisions over those facts.")
    if existing_python_helpers:
        recs.append(f"Existing Python helper detected: {existing_python_helpers[0]}")
    else:
        recs.append(f"Suggested helper path: scripts/{helper_name}.py")
    recs.append("Prefer inspect/apply commands; make inspect read-only and apply require an explicit plan for side effects.")
    return recs


def analyze_target(target_arg: str) -> dict[str, Any]:
    target, text, metadata = load_skill(Path(target_arg))
    steps = extract_steps(metadata.body)
    commands = extract_commands(text)
    resources = existing_resources(target)
    skill_name = metadata.name or target.name
    existing_python_helpers = [path for path in resources.get("scripts", []) if path.endswith(".py")]
    helper_name = Path(existing_python_helpers[0]).stem if existing_python_helpers else helper_stem(skill_name)
    classified_steps = classify_lines(steps)
    score = estimate_pythonization_score(classified_steps, commands, resources)

    deterministic_candidates = [step for step in classified_steps if step["classification"] in {"deterministic_candidate", "mixed"}]
    judgement_steps = [step for step in classified_steps if step["classification"] in {"llm_judgement", "mixed"}]

    return {
        "target_skill_dir": str(target),
        "name": metadata.name,
        "description": metadata.description,
        "body_line_count": len(metadata.body.splitlines()),
        "existing_resources": resources,
        "commands_found": commands[:50],
        "steps": classified_steps,
        "deterministic_candidate_count": len(deterministic_candidates),
        "llm_judgement_count": len(judgement_steps),
        "pythonization_score": score,
        "suggested_helper_name": helper_name,
        "recommendations": recommendations(score, classified_steps, commands, helper_name, existing_python_helpers),
    }


def helper_template(skill_name: str, module_name: str) -> str:
    title = skill_name or module_name
    return textwrap.dedent(
        f'''\
        #!/usr/bin/env python3
        """Helper for the {title} skill.

        TODO: Replace placeholder inspection/planning logic with deterministic
        work from the target skill. Keep LLM-only judgement out of this file.
        """

        from __future__ import annotations

        import argparse
        import json
        import sys
        from pathlib import Path
        from typing import Any


        class SkillHelperError(RuntimeError):
            """Expected, user-facing failure."""


        def resolve_target(target_arg: str) -> Path:
            target = Path(target_arg).expanduser().resolve()
            if not target.exists():
                raise SkillHelperError(f"Target does not exist: {{target}}")
            return target


        def inspect_target(target_arg: str) -> dict[str, Any]:
            target = resolve_target(target_arg)
            return {{
                "target": str(target),
                "exists": True,
                "TODO": "Add deterministic inspection fields for this skill.",
                "risk_flags": [],
                "suggested_actions": [],
            }}


        def load_plan(plan_path: str) -> dict[str, Any]:
            try:
                with open(plan_path, "r", encoding="utf-8") as handle:
                    plan = json.load(handle)
            except OSError as exc:
                raise SkillHelperError(f"Could not read plan file: {{exc}}") from exc
            except json.JSONDecodeError as exc:
                raise SkillHelperError(f"Plan is not valid JSON: {{exc}}") from exc
            if not isinstance(plan, dict):
                raise SkillHelperError("Plan must be a JSON object")
            return plan


        def apply_plan(target_arg: str, plan_path: str, *, dry_run: bool) -> dict[str, Any]:
            target = resolve_target(target_arg)
            plan = load_plan(plan_path)
            # TODO: Validate every path/action in plan before side effects.
            return {{
                "target": str(target),
                "dry_run": dry_run,
                "plan_keys": sorted(plan.keys()),
                "TODO": "Implement deterministic side effects for this skill.",
            }}


        def print_json(data: dict[str, Any]) -> None:
            print(json.dumps(data, indent=2, sort_keys=True))


        def build_parser() -> argparse.ArgumentParser:
            parser = argparse.ArgumentParser(description="Deterministic helper for the {title} skill.")
            subparsers = parser.add_subparsers(dest="command", required=True)

            inspect_parser = subparsers.add_parser("inspect", help="Inspect target state without side effects.")
            inspect_parser.add_argument("--target", required=True, help="Target path or resource for the skill.")
            inspect_parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is always emitted.")

            apply_parser = subparsers.add_parser("apply", help="Apply an explicit plan.")
            apply_parser.add_argument("--target", required=True, help="Target path or resource for the skill.")
            apply_parser.add_argument("--plan", required=True, help="Path to plan JSON created outside the target.")
            apply_parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without side effects.")
            return parser


        def main(argv: list[str] | None = None) -> int:
            parser = build_parser()
            args = parser.parse_args(argv)
            try:
                if args.command == "inspect":
                    print_json(inspect_target(args.target))
                    return 0
                if args.command == "apply":
                    print_json(apply_plan(args.target, args.plan, dry_run=args.dry_run))
                    return 0
                parser.error(f"Unknown command: {{args.command}}")
                return 2
            except SkillHelperError as exc:
                print(json.dumps({{"error": str(exc)}}, indent=2), file=sys.stderr)
                return 1


        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    )


def scaffold_target(target_arg: str, helper_name_arg: str | None, *, overwrite: bool) -> dict[str, Any]:
    target, _text, metadata = load_skill(Path(target_arg))
    skill_name = metadata.name or target.name
    helper_stem_value = helper_stem(helper_name_arg or skill_name)
    scripts_dir = target / "scripts"
    helper_path = scripts_dir / f"{helper_stem_value}.py"

    scripts_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []

    if helper_path.exists() and not overwrite:
        skipped.append(str(helper_path))
    else:
        helper_path.write_text(helper_template(skill_name, helper_stem_value), encoding="utf-8")
        created.append(str(helper_path))

    return {
        "target_skill_dir": str(target),
        "scripts_dir": str(scripts_dir),
        "helper_path": str(helper_path),
        "created": created,
        "skipped": skipped,
        "next_steps": [
            f"Implement deterministic inspect/apply logic in {helper_path.name}.",
            "Run python -m py_compile against the helper.",
            "Update the target SKILL.md to call the helper and describe LLM-only judgement points.",
            "Run quick_validate.py for the target skill.",
        ],
    }


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze and scaffold Python-backed skill refactors.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a target skill and recommend Pythonization boundaries.")
    analyze_parser.add_argument("--target", required=True, help="Target skill directory or SKILL.md path.")
    analyze_parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is always emitted.")

    scaffold_parser = subparsers.add_parser("scaffold", help="Create a starter helper script in the target skill.")
    scaffold_parser.add_argument("--target", required=True, help="Target skill directory or SKILL.md path.")
    scaffold_parser.add_argument("--helper-name", help="Optional helper filename stem. Defaults to <skill>-helper.")
    scaffold_parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing helper file.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            print_json(analyze_target(args.target))
            return 0
        if args.command == "scaffold":
            print_json(scaffold_target(args.target, args.helper_name, overwrite=args.overwrite))
            return 0
        parser.error(f"Unknown command: {args.command}")
        return 2
    except PythonizeSkillError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
