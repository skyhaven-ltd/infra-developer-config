#!/usr/bin/env python3
"""Inspect a Git change without modifying the repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise RuntimeError(message)
    return result.stdout.rstrip("\n")


def resolve(repo: Path, revision: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Path to the Git repository")
    parser.add_argument("--commit", required=True, help="Commit to explain")
    parser.add_argument("--baseline", help="Optional comparison commit")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
        commit = resolve(root, args.commit)
        parents = git(root, "show", "-s", "--format=%P", commit).split()
        if args.baseline:
            baseline = resolve(root, args.baseline)
            baseline_label = baseline
        elif parents:
            baseline = parents[0]
            baseline_label = baseline
        else:
            baseline = git(root, "hash-object", "-t", "tree", "/dev/null").strip()
            baseline_label = "empty tree (root commit)"

        metadata = git(
            root,
            "show",
            "-s",
            "--date=iso-strict",
            "--format=%H%n%h%n%an%n%ad%n%s%n%b",
            commit,
        ).splitlines()
        status_lines = git(root, "diff", "--name-status", baseline, commit).splitlines()
        stat_lines = git(root, "diff", "--numstat", baseline, commit).splitlines()
        files = []
        for line in status_lines:
            fields = line.split("\t")
            files.append({"status": fields[0], "paths": fields[1:]})

        payload = {
            "repository": str(root),
            "commit": commit,
            "short_commit": metadata[1] if len(metadata) > 1 else commit[:7],
            "baseline": baseline,
            "baseline_label": baseline_label,
            "is_merge": len(parents) > 1,
            "parents": parents,
            "author": metadata[2] if len(metadata) > 2 else "",
            "date": metadata[3] if len(metadata) > 3 else "",
            "subject": metadata[4] if len(metadata) > 4 else "",
            "body": "\n".join(metadata[5:]).strip(),
            "files": files,
            "numstat": stat_lines,
            "summary": git(root, "diff", "--shortstat", baseline, commit),
            "diff_command": f'git diff {baseline} {commit} --',
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"{payload['short_commit']}: {payload['subject']}")
            print(f"Compare: {baseline_label}..{commit}")
            print(payload["summary"] or "No file changes")
            for item in files:
                print(f"{item['status']}\t" + " -> ".join(item["paths"]))
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
