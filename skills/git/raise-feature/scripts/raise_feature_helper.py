#!/usr/bin/env python3
"""Deterministic helper for the raise-feature skill.

The LLM remains responsible for understanding the user's request, expanding terse
requirements into meaningful prose, and obtaining explicit user approval before
running the side-effecting ``apply`` command. This helper handles repeatable
repository detection, issue body construction, GitHub CLI calls, and Project V2
field updates.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

FEATURE_PREFIX = "[FEATURE] - "
DEFAULT_LABEL = "use-type-field-instead"
DEFAULT_ASSIGNEE = "liam-goodchild"
PROJECT_ID = "PVT_kwHOB9ID-s4BU_KB"
TYPE_FIELD_ID = "PVTSSF_lAHOB9ID-s4BU_KBzhRbk2o"
FEATURE_OPTION_ID = "c156bb04"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ISSUE_URL_PATTERN = re.compile(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)")


class SkillHelperError(RuntimeError):
    """Expected, user-facing failure."""


def run_command(args: list[str], *, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise SkillHelperError(f"Required executable not found: {args[0]}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SkillHelperError(f"Command failed ({' '.join(args)}): {detail}")
    return result


def resolve_target(target_arg: str) -> Path:
    target = Path(target_arg).expanduser().resolve()
    if not target.exists():
        raise SkillHelperError(f"Target does not exist: {target}")
    if not target.is_dir():
        raise SkillHelperError(f"Target must be a directory: {target}")
    return target


def find_gh() -> str | None:
    gh = shutil.which("gh")
    if gh:
        return gh
    windows_path = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI" / "gh.exe"
    if windows_path.exists():
        return str(windows_path)
    git_bash_path = Path("/c/Program Files/GitHub CLI/gh.exe")
    if git_bash_path.exists():
        return str(git_bash_path)
    return None


def infer_repo_from_remote(remote: str) -> str | None:
    remote = remote.strip()
    if not remote:
        return None

    # git@github.com:owner/repo.git or ssh://git@github.com/owner/repo.git
    scp_match = re.match(r"(?:git@|ssh://git@)github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    if scp_match:
        return scp_match.group(1)

    parsed = urlparse(remote)
    if parsed.netloc.lower() == "github.com":
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if REPO_PATTERN.match(path):
            return path
    return None


def get_git_remote(target: Path) -> tuple[str | None, str | None]:
    git = shutil.which("git")
    if not git:
        return None, "git executable was not found on PATH"
    result = run_command([git, "-C", str(target), "remote", "get-url", "origin"])
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip() or "origin remote not found"
    return result.stdout.strip(), None


def gh_auth_status(gh: str) -> dict[str, Any]:
    result = run_command([gh, "auth", "status", "-h", "github.com"])
    return {
        "ok": result.returncode == 0,
        "summary": "authenticated" if result.returncode == 0 else "not authenticated or auth status failed",
    }


def build_body(problem: str, solution: str) -> str:
    return "\n".join(
        [
            "**Is your feature request related to a problem? Please describe.**",
            problem.strip(),
            "",
            "**Describe the solution you'd like**",
            solution.strip(),
        ]
    )


def normalize_title(title: str) -> str:
    stripped = title.strip()
    if stripped.lower().startswith(FEATURE_PREFIX.lower()):
        return FEATURE_PREFIX + stripped[len(FEATURE_PREFIX) :].strip()
    return FEATURE_PREFIX + stripped


def inspect_target(target_arg: str) -> dict[str, Any]:
    target = resolve_target(target_arg)
    remote, remote_error = get_git_remote(target)
    inferred_repo = infer_repo_from_remote(remote or "") if remote else None
    gh = find_gh()
    auth = gh_auth_status(gh) if gh else {"ok": False, "summary": "gh executable not found"}

    risk_flags: list[str] = []
    if not inferred_repo:
        risk_flags.append("repository_not_inferred")
    if not gh:
        risk_flags.append("gh_not_found")
    elif not auth["ok"]:
        risk_flags.append("gh_not_authenticated")

    return {
        "target": str(target),
        "git_remote_origin": remote,
        "git_remote_error": remote_error,
        "inferred_repository": inferred_repo,
        "gh_path": gh,
        "gh_auth": auth,
        "project": {
            "id": PROJECT_ID,
            "type_field_id": TYPE_FIELD_ID,
            "feature_option_id": FEATURE_OPTION_ID,
        },
        "required_plan_fields": ["repository", "title", "problem", "solution", "approved"],
        "defaults": {"label": DEFAULT_LABEL, "assignee": DEFAULT_ASSIGNEE, "title_prefix": FEATURE_PREFIX},
        "risk_flags": risk_flags,
        "suggested_actions": [
            "Use inferred_repository if correct, otherwise ask the user for owner/repo.",
            "Draft a concise title plus meaningful problem and solution sections.",
            "Show the final title and body to the user and set approved=true only after explicit approval.",
        ],
    }


def load_plan(plan_path: str) -> dict[str, Any]:
    try:
        with open(plan_path, "r", encoding="utf-8") as handle:
            plan = json.load(handle)
    except OSError as exc:
        raise SkillHelperError(f"Could not read plan file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SkillHelperError(f"Plan is not valid JSON: {exc}") from exc
    if not isinstance(plan, dict):
        raise SkillHelperError("Plan must be a JSON object")
    return plan


def require_text(plan: dict[str, Any], field: str) -> str:
    value = plan.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SkillHelperError(f"Plan field '{field}' must be a non-empty string")
    return value.strip()


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    repository = require_text(plan, "repository")
    if not REPO_PATTERN.match(repository):
        raise SkillHelperError("Plan field 'repository' must be in owner/repo format")

    title = normalize_title(require_text(plan, "title"))
    problem = require_text(plan, "problem")
    solution = require_text(plan, "solution")
    approved = plan.get("approved")
    if approved is not True:
        raise SkillHelperError("Plan field 'approved' must be true after explicit user approval")

    label = plan.get("label", DEFAULT_LABEL)
    assignee = plan.get("assignee", DEFAULT_ASSIGNEE)
    if not isinstance(label, str) or not label.strip():
        raise SkillHelperError("Plan field 'label' must be a non-empty string when provided")
    if not isinstance(assignee, str) or not assignee.strip():
        raise SkillHelperError("Plan field 'assignee' must be a non-empty string when provided")

    return {
        "repository": repository,
        "title": title,
        "problem": problem,
        "solution": solution,
        "body": build_body(problem, solution),
        "label": label.strip(),
        "assignee": assignee.strip(),
    }


def graphql(gh: str, query: str, fields: dict[str, str]) -> dict[str, Any]:
    args = [gh, "api", "graphql", "-f", f"query={query}"]
    for key, value in fields.items():
        args.extend(["-f", f"{key}={value}"])
    result = run_command(args, check=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SkillHelperError("GitHub GraphQL API returned invalid JSON") from exc


def create_issue(gh: str, normalized: dict[str, Any]) -> dict[str, str]:
    result = run_command(
        [
            gh,
            "issue",
            "create",
            "--repo",
            normalized["repository"],
            "--title",
            normalized["title"],
            "--label",
            normalized["label"],
            "--assignee",
            normalized["assignee"],
            "--body",
            normalized["body"],
        ],
        check=True,
    )
    issue_url = result.stdout.strip().splitlines()[-1].strip()
    match = ISSUE_URL_PATTERN.search(issue_url)
    if not match:
        raise SkillHelperError(f"Could not parse issue URL from gh output: {issue_url}")
    return {"url": issue_url, "number": match.group(2)}


def get_issue_node_id(gh: str, repository: str, issue_number: str) -> str:
    result = run_command([gh, "api", f"repos/{repository}/issues/{issue_number}", "--jq", ".node_id"], check=True)
    node_id = result.stdout.strip()
    if not node_id:
        raise SkillHelperError("Could not read created issue node_id")
    return node_id


def add_issue_to_project(gh: str, issue_node_id: str) -> str:
    query = """
      mutation($projectId: ID!, $contentId: ID!) {
        addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
          item { id }
        }
      }
    """
    data = graphql(gh, query, {"projectId": PROJECT_ID, "contentId": issue_node_id})
    item_id = data.get("data", {}).get("addProjectV2ItemById", {}).get("item", {}).get("id")
    if not isinstance(item_id, str) or not item_id:
        raise SkillHelperError("Could not add issue to project or read project item id")
    return item_id


def set_project_type_feature(gh: str, item_id: str) -> None:
    query = """
      mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
        updateProjectV2ItemFieldValue(input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: { singleSelectOptionId: $optionId }
        }) { projectV2Item { id } }
      }
    """
    graphql(
        gh,
        query,
        {
            "projectId": PROJECT_ID,
            "itemId": item_id,
            "fieldId": TYPE_FIELD_ID,
            "optionId": FEATURE_OPTION_ID,
        },
    )


def apply_plan(target_arg: str, plan_path: str, *, dry_run: bool) -> dict[str, Any]:
    target = resolve_target(target_arg)
    plan = load_plan(plan_path)
    normalized = validate_plan(plan)
    gh = find_gh()
    if not gh:
        raise SkillHelperError("gh executable not found")

    summary = {
        "target": str(target),
        "dry_run": dry_run,
        "repository": normalized["repository"],
        "title": normalized["title"],
        "body_preview": normalized["body"],
        "label": normalized["label"],
        "assignee": normalized["assignee"],
        "project": {"id": PROJECT_ID, "type": "Feature"},
    }
    if dry_run:
        return {**summary, "would_create_issue": True, "would_set_project_type": True}

    issue = create_issue(gh, normalized)
    issue_node_id = get_issue_node_id(gh, normalized["repository"], issue["number"])
    project_item_id = add_issue_to_project(gh, issue_node_id)
    set_project_type_feature(gh, project_item_id)
    return {
        **summary,
        "created_issue_url": issue["url"],
        "issue_number": issue["number"],
        "issue_node_id": issue_node_id,
        "project_item_id": project_item_id,
        "project_type_set": "Feature",
    }


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic helper for the raise-feature skill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect repository and GitHub CLI state without side effects.")
    inspect_parser.add_argument("--target", required=True, help="Directory to inspect, usually the current repository.")
    inspect_parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is always emitted.")

    apply_parser = subparsers.add_parser("apply", help="Create the approved feature issue and set its Project V2 Type.")
    apply_parser.add_argument("--target", required=True, help="Directory used for context validation.")
    apply_parser.add_argument("--plan", required=True, help="Path to approved plan JSON created outside the target.")
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
        parser.error(f"Unknown command: {args.command}")
        return 2
    except SkillHelperError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
