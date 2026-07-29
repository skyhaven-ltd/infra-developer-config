#!/usr/bin/env python3
"""Update the default branch and remove local Git refs safely stored on origin."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


class GitClearError(RuntimeError):
    pass


def run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if not git:
        raise GitClearError("git was not found on PATH")
    result = subprocess.run(
        [git, *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise GitClearError(message or f"git {' '.join(args)} failed")
    return result


def repository_root(target: str) -> Path:
    path = Path(target).expanduser().resolve()
    if not path.is_dir():
        raise GitClearError(f"target directory does not exist: {path}")
    result = run_git(path, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise GitClearError(f"not inside a Git repository: {path}")
    return Path(result.stdout.strip()).resolve()


def lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def default_branch(root: Path) -> str:
    result = run_git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    if result.returncode == 0 and result.stdout.strip().startswith("origin/"):
        return result.stdout.strip().removeprefix("origin/")

    for candidate in ("main", "master"):
        if run_git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{candidate}", check=False).returncode == 0:
            return candidate
    raise GitClearError("could not determine origin's default branch")


def checked_out_branches(root: Path) -> set[str]:
    result = run_git(root, "worktree", "list", "--porcelain")
    prefix = "branch refs/heads/"
    return {line.removeprefix(prefix) for line in result.stdout.splitlines() if line.startswith(prefix)}


def has_unique_patch(root: Path, branch: str, upstream: str) -> bool:
    """Return whether branch contains a change not patch-equivalent to upstream."""
    result = run_git(root, "cherry", upstream, branch, check=False)
    if result.returncode != 0:
        return True
    return any(line.startswith("+") for line in lines(result))


def github_repository(root: Path) -> str | None:
    result = run_git(root, "remote", "get-url", "origin", check=False)
    if result.returncode != 0:
        return None
    match = re.match(
        r"^(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+?)(?:\.git)?$",
        result.stdout.strip(),
    )
    return match.group(1) if match else None


def is_merged_github_pr_head(root: Path, branch: str) -> bool:
    """Best-effort check for a merged PR whose recorded head is this exact commit."""
    gh = shutil.which("gh")
    repository = github_repository(root)
    if not gh or not repository:
        return False
    head = run_git(root, "rev-parse", branch).stdout.strip()
    result = subprocess.run(
        [
            gh, "pr", "list", "--repo", repository, "--head", branch,
            "--state", "merged", "--limit", "20", "--json", "headRefOid",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return False
    try:
        return any(item.get("headRefOid") == head for item in json.loads(result.stdout))
    except (json.JSONDecodeError, TypeError):
        return False


@dataclass
class RetainedBranch:
    name: str
    reason: str


@dataclass
class Plan:
    repository: str
    default_branch: str
    current_branch: str | None
    delete_branches: list[str]
    delete_tags: list[str]
    retained_branches: list[RetainedBranch]


def discover(root: Path, fetch: bool = True) -> Plan:
    if run_git(root, "remote", "get-url", "origin", check=False).returncode != 0:
        raise GitClearError("remote 'origin' is not configured")
    if fetch:
        run_git(root, "fetch", "origin", "--prune", "--no-tags")

    default = default_branch(root)
    current_result = run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    current = current_result.stdout.strip() if current_result.returncode == 0 else None
    worktree_branches = checked_out_branches(root)
    local_branches = lines(run_git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads"))
    remote_branches = set(lines(run_git(root, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")))

    deletable: list[str] = []
    retained: list[RetainedBranch] = []
    for branch in local_branches:
        if branch == default:
            retained.append(RetainedBranch(branch, "origin default branch"))
            continue
        if branch in worktree_branches and branch != current:
            retained.append(RetainedBranch(branch, "checked out in another worktree"))
            continue
        remote = f"origin/{branch}"
        if remote not in remote_branches:
            merged = run_git(
                root,
                "merge-base",
                "--is-ancestor",
                branch,
                f"origin/{default}",
                check=False,
            )
            if merged.returncode == 0:
                deletable.append(branch)
                continue
            # An ancestry check cannot recognise rebased or squash-merged
            # single-commit branches. `git cherry` compares stable patch IDs,
            # so an equivalent change on the default branch is safe to remove.
            if not has_unique_patch(root, branch, f"origin/{default}"):
                deletable.append(branch)
                continue
            # Multi-commit PRs squash to a different patch shape. GitHub keeps
            # the original head SHA, which lets us confirm the exact local tip
            # was merged without relying on a potentially reused branch name.
            if is_merged_github_pr_head(root, branch):
                deletable.append(branch)
                continue
            local_only = lines(run_git(root, "rev-list", branch, "--not", f"origin/{default}"))
            retained.append(
                RetainedBranch(
                    branch,
                    f"no branch on origin and {len(local_only)} commit(s) are not in origin/{default}",
                )
            )
            continue
        local_only = lines(run_git(root, "rev-list", branch, "--not", remote))
        if local_only:
            retained.append(RetainedBranch(branch, f"{len(local_only)} commit(s) exist only locally"))
            continue
        deletable.append(branch)

    tags = lines(run_git(root, "tag", "--list"))
    return Plan(str(root), default, current, sorted(deletable), sorted(tags), retained)


def ensure_clean(root: Path) -> None:
    if run_git(root, "status", "--porcelain").stdout.strip():
        raise GitClearError("working tree is not clean; commit or stash changes before applying")


def apply_plan(root: Path, plan: Plan) -> None:
    ensure_clean(root)
    run_git(root, "switch", plan.default_branch)
    run_git(root, "pull", "--ff-only", "origin", plan.default_branch)
    for branch in plan.delete_branches:
        run_git(root, "branch", "-D", "--", branch)
    if plan.delete_tags:
        run_git(root, "tag", "--delete", *plan.delete_tags)


def print_plan(plan: Plan, applied: bool) -> None:
    print(f"Repository: {plan.repository}")
    print(f"Default branch: {plan.default_branch}")
    print("\nBranches to delete:")
    print("\n".join(f"  {name}" for name in plan.delete_branches) or "  (none)")
    print("\nTags to delete:")
    print("\n".join(f"  {name}" for name in plan.delete_tags) or "  (none)")
    print("\nRetained branches:")
    print("\n".join(f"  {item.name} - {item.reason}" for item in plan.retained_branches) or "  (none)")
    if applied:
        print("\nCleanup applied.")
    else:
        print("\nDry run only. Run `git clear --apply` to apply this plan.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete the discovered local refs")
    parser.add_argument("--target", default=".", help="repository path (default: current directory)")
    parser.add_argument("--json", action="store_true", help="print the plan as JSON")
    args = parser.parse_args(argv)

    try:
        root = repository_root(args.target)
        plan = discover(root)
        if args.apply:
            apply_plan(root, plan)
        if args.json:
            payload = asdict(plan)
            payload["applied"] = args.apply
            print(json.dumps(payload, indent=2))
        else:
            print_plan(plan, args.apply)
        return 0
    except GitClearError as error:
        print(f"git clear: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
