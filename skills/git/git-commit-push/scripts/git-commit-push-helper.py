#!/usr/bin/env python3
"""Deterministic helper for the git-commit-push skill.

The agent should use `inspect` first, generate a compact commit plan, then use
`apply` to stage, commit, and push exact files from that plan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

PROTECTED_BRANCHES = {"main", "master"}
MAX_SCAN_BYTES = 1_000_000
LARGE_FILE_BYTES = 5 * 1024 * 1024

RISKY_FILENAMES = {
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
    "credentials",
}

RISKY_SUFFIXES = {
    ".key",
    ".pem",
    ".pfx",
    ".p12",
}

RISKY_PATH_WORDS = (
    "secret",
    "secrets",
    "credential",
    "credentials",
)

SECRET_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?key|secret|password|passwd|token|client[_-]?secret)\b\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:@~-]{8,}"
        ),
        "possible hard-coded secret assignment",
    ),
    (
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
        "private key material",
    ),
)


class GitCommitPushError(RuntimeError):
    """Expected, user-facing failure."""


def run_git(repo: Path, args: list[str], *, check: bool = True, text: bool = True) -> subprocess.CompletedProcess[Any]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace").strip()
        stdout = result.stdout.strip() if isinstance(result.stdout, str) else result.stdout.decode("utf-8", "replace").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise GitCommitPushError(f"git {' '.join(args)} failed: {detail}")
    return result


def normalize_rel_path(path: str) -> str:
    path = path.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/") or path == ".." or path.startswith("../") or "/../" in path:
        raise GitCommitPushError(f"Unsafe repository-relative path in plan: {path!r}")
    return path


def repo_root(repo_arg: str) -> Path:
    repo = Path(repo_arg).expanduser().resolve()
    result = run_git(repo, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def decode_git_path(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape").replace("\\", "/")


def parse_status_z(raw: bytes) -> list[dict[str, Any]]:
    parts = raw.split(b"\0")
    entries: list[dict[str, Any]] = []
    i = 0

    while i < len(parts):
        record = parts[i]
        if not record:
            break
        if len(record) < 3:
            raise GitCommitPushError(f"Unexpected git status record: {record!r}")

        code = record[:2].decode("ascii", errors="replace")
        path = decode_git_path(record[3:])
        original_path = None
        stage_paths = [path]

        # In porcelain v1 -z, rename/copy records store the destination path in
        # the first record and the source path in the following NUL record.
        if code[0] in {"R", "C"} or code[1] in {"R", "C"}:
            i += 1
            if i >= len(parts) or not parts[i]:
                raise GitCommitPushError(f"Missing source path for rename/copy status record: {record!r}")
            original_path = decode_git_path(parts[i])
            stage_paths = [original_path, path]

        entries.append(
            {
                "status": code,
                "kind": status_kind(code),
                "path": path,
                "original_path": original_path,
                "stage_paths": stage_paths,
            }
        )
        i += 1

    return entries


def status_kind(code: str) -> str:
    if code == "??":
        return "untracked"
    if "U" in code:
        return "unmerged"
    if "R" in code:
        return "renamed"
    if "C" in code:
        return "copied"
    if "A" in code:
        return "added"
    if "D" in code:
        return "deleted"
    if "M" in code:
        return "modified"
    return "changed"


def current_branch(repo: Path) -> str:
    result = run_git(repo, ["branch", "--show-current"])
    branch = result.stdout.strip()
    if branch:
        return branch
    detached = run_git(repo, ["rev-parse", "--short", "HEAD"], check=False)
    short_sha = detached.stdout.strip() if detached.returncode == 0 else "unknown"
    return f"DETACHED@{short_sha}"


def has_upstream(repo: Path) -> bool:
    result = run_git(repo, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=False)
    return result.returncode == 0


def has_origin(repo: Path) -> bool:
    result = run_git(repo, ["remote", "get-url", "origin"], check=False)
    return result.returncode == 0


def is_ops_developer_config_repo(repo: Path) -> bool:
    return any(part.lower() == "ops-developer-config" for part in repo.parts)


def safe_repo_path(repo: Path, rel_path: str) -> Path | None:
    try:
        rel = normalize_rel_path(rel_path)
    except GitCommitPushError:
        return None
    candidate = (repo / rel).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError:
        return None
    return candidate


def file_is_binary(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    with path.open("rb") as handle:
        return b"\0" in handle.read(8192)


def scan_text_risks(path: Path) -> list[str]:
    if not path.exists() or not path.is_file() or file_is_binary(path):
        return []
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ["could not scan file contents"]

    reasons: list[str] = []
    for pattern, reason in SECRET_TEXT_PATTERNS:
        if pattern.search(text):
            reasons.append(reason)
    return reasons


def risk_flags(repo: Path, entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(path: str, severity: str, reason: str) -> None:
        key = (path, reason)
        if key in seen:
            return
        seen.add(key)
        flags.append({"path": path, "severity": severity, "reason": reason})

    for entry in entries:
        path = entry["path"]
        pure = PurePosixPath(path)
        lower_path = path.lower()
        lower_name = pure.name.lower()
        suffix = pure.suffix.lower()

        if lower_name == ".env" or lower_name.startswith(".env."):
            add(path, "high", ".env file")
        if lower_name in RISKY_FILENAMES or suffix in RISKY_SUFFIXES:
            add(path, "high", "credential-like filename or extension")
        if any(word in lower_path for word in RISKY_PATH_WORDS):
            add(path, "medium", "path name suggests secrets or credentials")

        real_path = safe_repo_path(repo, path)
        if real_path is None:
            add(path, "high", "unsafe path")
            continue
        if real_path.exists() and real_path.is_file():
            try:
                size = real_path.stat().st_size
            except OSError:
                size = 0
            if size > LARGE_FILE_BYTES:
                add(path, "medium", f"large file over {LARGE_FILE_BYTES // (1024 * 1024)} MiB")
            if file_is_binary(real_path):
                add(path, "medium", "binary file")
            for reason in scan_text_risks(real_path):
                add(path, "high", reason)

    return flags


def stageable_paths(entries: Iterable[dict[str, Any]]) -> list[str]:
    paths: set[str] = set()
    for entry in entries:
        for path in entry["stage_paths"]:
            paths.add(normalize_rel_path(path))
    return sorted(paths)


def group_key(path: str) -> str:
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] == "skills":
        return "/".join(parts[:3])
    if len(parts) >= 2 and parts[0] in {"scripts", "docs", "codex", "claude", ".github"}:
        return parts[0]
    if len(parts) >= 2:
        return parts[0]
    return "repo-root"


def suggested_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not entries:
        return []

    all_paths = stageable_paths(entries)
    if len(entries) <= 3:
        return [
            {
                "name": "single-commit",
                "reason": "3 or fewer changed files",
                "files": all_paths,
            }
        ]

    grouped: dict[str, set[str]] = {}
    for path in all_paths:
        grouped.setdefault(group_key(path), set()).add(path)

    return [
        {
            "name": key,
            "reason": "grouped by top-level area",
            "files": sorted(paths),
        }
        for key, paths in sorted(grouped.items())
    ]


def inspect_repo(repo_arg: str) -> dict[str, Any]:
    repo = repo_root(repo_arg)
    branch = current_branch(repo)
    status = run_git(repo, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], text=False)
    entries = parse_status_z(status.stdout)
    protected_branch = branch in PROTECTED_BRANCHES
    protected_branch_allowed = protected_branch and is_ops_developer_config_repo(repo)
    blocked = protected_branch and not protected_branch_allowed

    return {
        "repo_root": str(repo),
        "branch": branch,
        "protected_branch": protected_branch,
        "protected_branch_allowed": protected_branch_allowed,
        "blocked": blocked,
        "block_reason": "on main/master outside ops-developer-config" if blocked else None,
        "has_changes": bool(entries),
        "changed_file_count": len(entries),
        "changed_files": entries,
        "stageable_paths": stageable_paths(entries),
        "risk_flags": risk_flags(repo, entries),
        "suggested_groups": suggested_groups(entries),
        "has_upstream": has_upstream(repo),
        "has_origin": has_origin(repo),
    }


def validate_message(message: str) -> str:
    message = message.strip()
    if not message:
        raise GitCommitPushError("Commit message must not be empty")
    if "\n" in message or "\r" in message:
        raise GitCommitPushError("Commit message must be a single short sentence")
    if len(message) >= 72:
        raise GitCommitPushError(f"Commit message must be under 72 characters: {message!r}")
    if message.endswith("."):
        raise GitCommitPushError(f"Commit message must not have a trailing period: {message!r}")
    if "co-authored-by:" in message.lower():
        raise GitCommitPushError("Commit message must not include a Co-Authored-By trailer")
    if re.match(r"^[A-Za-z]+(?:\([^)]+\))?:\s+", message):
        raise GitCommitPushError(f"Commit message must not use a conventional prefix: {message!r}")
    return message


def load_plan(plan_path: str) -> dict[str, Any]:
    try:
        with open(plan_path, "r", encoding="utf-8") as handle:
            plan = json.load(handle)
    except OSError as exc:
        raise GitCommitPushError(f"Could not read plan file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GitCommitPushError(f"Commit plan is not valid JSON: {exc}") from exc

    if not isinstance(plan, dict):
        raise GitCommitPushError("Commit plan must be a JSON object")
    commits = plan.get("commits")
    if not isinstance(commits, list) or not commits:
        raise GitCommitPushError("Commit plan must include a non-empty commits array")
    return plan


def validate_plan(plan: dict[str, Any], inspection: dict[str, Any], *, allow_partial: bool) -> list[dict[str, Any]]:
    allowed_paths = set(inspection["stageable_paths"])
    planned_paths: set[str] = set()
    validated: list[dict[str, Any]] = []

    for index, commit in enumerate(plan["commits"], start=1):
        if not isinstance(commit, dict):
            raise GitCommitPushError(f"Commit #{index} must be an object")
        message = validate_message(str(commit.get("message", "")))
        raw_files = commit.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            raise GitCommitPushError(f"Commit #{index} must include a non-empty files array")
        files = [normalize_rel_path(str(path)) for path in raw_files]
        unknown = sorted(set(files) - allowed_paths)
        if unknown:
            raise GitCommitPushError(f"Commit #{index} includes paths that are not changed: {unknown}")
        duplicates = sorted(planned_paths.intersection(files))
        if duplicates:
            raise GitCommitPushError(f"Paths appear in more than one commit group: {duplicates}")
        planned_paths.update(files)
        validated.append({"message": message, "files": files})

    if not allow_partial:
        omitted = sorted(allowed_paths - planned_paths)
        if omitted:
            raise GitCommitPushError(f"Commit plan omits changed paths: {omitted}")

    return validated


def write_commit_message_file(message: str) -> str:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt")
    try:
        handle.write(message)
        handle.write("\n")
        return handle.name
    finally:
        handle.close()


def apply_plan(args: argparse.Namespace) -> dict[str, Any]:
    inspection = inspect_repo(args.repo)
    repo = Path(inspection["repo_root"])

    if inspection["blocked"]:
        raise GitCommitPushError(str(inspection["block_reason"]))
    if not inspection["has_changes"]:
        raise GitCommitPushError("No changes to commit")
    if inspection["risk_flags"] and not args.allow_risk:
        raise GitCommitPushError("Risk flags are present; inspect them and rerun apply with --allow-risk only after user approval")

    plan = load_plan(args.plan)
    commits = validate_plan(plan, inspection, allow_partial=args.allow_partial)
    push = not args.no_push

    summary: dict[str, Any] = {
        "repo_root": inspection["repo_root"],
        "branch": inspection["branch"],
        "dry_run": args.dry_run,
        "commit_count": len(commits),
        "push": push,
        "commits": [],
    }

    if args.dry_run:
        summary["commits"] = commits
        summary["push_command"] = push_command(repo, inspection["branch"], inspection["has_upstream"]) if push else None
        return summary

    # Ensure only the requested group is staged for each commit.
    run_git(repo, ["reset", "--"])

    for commit in commits:
        run_git(repo, ["add", "-A", "--", *commit["files"]])
        message_file = write_commit_message_file(commit["message"])
        try:
            run_git(repo, ["commit", "-F", message_file])
        finally:
            try:
                os.unlink(message_file)
            except OSError:
                pass
        short_hash = run_git(repo, ["rev-parse", "--short", "HEAD"]).stdout.strip()
        summary["commits"].append({"hash": short_hash, "message": commit["message"], "files": commit["files"]})

    if push:
        command = push_command(repo, inspection["branch"], inspection["has_upstream"])
        run_git(repo, command)
        summary["push_command"] = ["git", *command]
    else:
        summary["push_command"] = None

    return summary


def push_command(repo: Path, branch: str, upstream_exists: bool) -> list[str]:
    if branch.startswith("DETACHED@"):
        raise GitCommitPushError("Cannot push from detached HEAD")
    if not has_origin(repo):
        raise GitCommitPushError("No origin remote is configured")
    if upstream_exists:
        return ["push", "origin", "HEAD"]
    return ["push", "-u", "origin", branch]


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and apply git commit/push plans for agent skills.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect repository state and suggest commit groups.")
    inspect_parser.add_argument("--repo", default=".", help="Repository path. Defaults to current directory.")
    inspect_parser.add_argument("--json", action="store_true", help="Emit JSON. Present for readability; JSON is always emitted.")

    apply_parser = subparsers.add_parser("apply", help="Apply a commit plan, then push unless --no-push is set.")
    apply_parser.add_argument("--repo", default=".", help="Repository path. Defaults to current directory.")
    apply_parser.add_argument("--plan", required=True, help="Path to commit plan JSON.")
    apply_parser.add_argument("--allow-risk", action="store_true", help="Proceed despite inspect risk flags. Use only after user approval.")
    apply_parser.add_argument("--allow-partial", action="store_true", help="Allow the plan to omit changed files.")
    apply_parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without staging, committing, or pushing.")
    apply_parser.add_argument("--no-push", action="store_true", help="Commit without pushing. Intended for tests only.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print_json(inspect_repo(args.repo))
            return 0
        if args.command == "apply":
            print_json(apply_plan(args))
            return 0
        parser.error(f"Unknown command: {args.command}")
        return 2
    except GitCommitPushError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

