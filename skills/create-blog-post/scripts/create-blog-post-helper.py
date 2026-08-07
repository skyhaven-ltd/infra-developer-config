#!/usr/bin/env python3
"""Deterministic helper for creating CVEngine portfolio blog posts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REQUIRED_PATHS = [
    Path("docs/blog"),
    Path("scripts/build_blog.py"),
    Path("frontend/index.html"),
]
VALID_STATUSES = {"draft", "published"}
FORBIDDEN_EM_DASH_PATTERNS = (chr(8212), "&" + "mdash;", "&#" + "8212;")
EM_DASH_REPLACEMENT_GUIDANCE = "replace it with a comma, colon, parentheses, or hyphen"


class SkillHelperError(RuntimeError):
    """Expected, user-facing failure."""


def resolve_target(target_arg: str) -> Path:
    target = Path(target_arg).expanduser().resolve()
    if not target.exists():
        raise SkillHelperError(f"Target does not exist: {target}")
    if not target.is_dir():
        raise SkillHelperError(f"Target is not a directory: {target}")
    return target


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "post"


def contains_em_dash_reference(value: str) -> bool:
    lower_value = value.lower()
    return any(pattern in lower_value for pattern in FORBIDDEN_EM_DASH_PATTERNS)


def append_em_dash_errors(errors: list[str], field_name: str, value: str) -> None:
    if contains_em_dash_reference(value):
        errors.append(f"{field_name} contains an em dash; {EM_DASH_REPLACEMENT_GUIDANCE}")


def split_tags(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_tags = [str(item) for item in value]
    else:
        raw_tags = re.split(r"[,;]", str(value))
    tags: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        cleaned = " ".join(tag.strip().split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            tags.append(cleaned)
            seen.add(key)
    return tags


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    try:
        _, raw_meta, body = normalized.split("---\n", 2)
    except ValueError:
        return {}, normalized

    meta: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in raw_meta.splitlines():
        if not line.strip():
            continue
        list_match = re.match(r"^\s+-\s+(.+)$", line)
        if list_match and current_list_key:
            meta.setdefault(current_list_key, []).append(clean_meta_value(list_match.group(1)))
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not key_match:
            continue
        key, value = key_match.groups()
        current_list_key = None
        if value == "":
            meta[key] = []
            current_list_key = key
        else:
            meta[key] = clean_meta_value(value)
    return meta, body.strip()


def clean_meta_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def is_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "published"}


def discover_posts(target: Path) -> list[dict[str, Any]]:
    blog_dir = target / "docs" / "blog"
    posts: list[dict[str, Any]] = []
    if not blog_dir.exists():
        return posts

    for path in sorted(blog_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(text)
        if not meta:
            continue
        title = str(meta.get("title") or path.stem.replace("-", " ").title()).strip()
        draft = is_truthy(meta.get("draft"))
        posts.append(
            {
                "path": path.relative_to(target).as_posix(),
                "slug": str(meta.get("slug") or slugify(title)),
                "title": title,
                "date": str(meta.get("date") or ""),
                "description": str(meta.get("description") or ""),
                "tags": split_tags(meta.get("tags")),
                "draft": draft,
                "published": not draft,
                "body_chars": len(body),
            }
        )
    return posts


def inspect_target(target_arg: str) -> dict[str, Any]:
    target = resolve_target(target_arg)
    missing_paths = [path.as_posix() for path in REQUIRED_PATHS if not (target / path).exists()]
    posts = discover_posts(target)
    slugs: dict[str, int] = {}
    issues: list[str] = []
    blog_dir = target / "docs" / "blog"
    if blog_dir.exists():
        for source_path in sorted(blog_dir.glob("*.md")):
            if source_path.name.lower() == "readme.md":
                continue
            raw = source_path.read_text(encoding="utf-8")
            if contains_em_dash_reference(raw):
                issues.append(
                    f"Blog source contains an em dash: {source_path.relative_to(target).as_posix()}"
                )

    for post in posts:
        slugs[post["slug"]] = slugs.get(post["slug"], 0) + 1
        if post["published"] and not post["description"]:
            issues.append(f"Published post missing description: {post['path']}")
        if post["published"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", post["date"]):
            issues.append(f"Published post date must be YYYY-MM-DD: {post['path']}")
    duplicate_slugs = sorted(slug for slug, count in slugs.items() if count > 1)
    for slug in duplicate_slugs:
        issues.append(f"Duplicate slug: {slug}")

    return {
        "ok": not missing_paths and not issues,
        "target": str(target),
        "missing_paths": missing_paths,
        "post_count": len(posts),
        "published_count": sum(1 for post in posts if post["published"]),
        "draft_count": sum(1 for post in posts if not post["published"]),
        "posts": posts,
        "issues": issues,
        "suggested_plan_dir": str(Path.cwd()),
    }


def today_iso() -> str:
    return dt.date.today().isoformat()


def validate_plan(plan: dict[str, Any], target: Path) -> dict[str, Any]:
    title = str(plan.get("title") or "").strip()
    description = str(plan.get("description") or "").strip()
    date = str(plan.get("date") or today_iso()).strip()
    status = str(plan.get("status") or "draft").strip().lower()
    slug = str(plan.get("slug") or slugify(title)).strip().lower()
    tags = split_tags(plan.get("tags"))
    body_markdown = str(plan.get("body_markdown") or "").strip()

    errors: list[str] = []
    if not title:
        errors.append("title is required")
    if not description:
        errors.append("description is required")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        errors.append("date must use YYYY-MM-DD")
    if status not in VALID_STATUSES:
        errors.append("status must be draft or published")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        errors.append("slug must be URL-safe kebab-case")
    if not (1 <= len(tags) <= 5):
        errors.append("tags must contain 1 to 5 values")
    if not body_markdown:
        errors.append("body_markdown is required")

    append_em_dash_errors(errors, "title", title)
    append_em_dash_errors(errors, "description", description)
    append_em_dash_errors(errors, "slug", slug)
    append_em_dash_errors(errors, "body_markdown", body_markdown)
    for index, tag in enumerate(tags, start=1):
        append_em_dash_errors(errors, f"tags[{index}]", tag)

    output_path = (target / "docs" / "blog" / f"{slug}.md").resolve()
    blog_dir = (target / "docs" / "blog").resolve()
    if blog_dir not in output_path.parents:
        errors.append("resolved output path is outside docs/blog")

    if errors:
        raise SkillHelperError("; ".join(errors))

    return {
        "title": title,
        "description": description,
        "date": date,
        "tags": tags,
        "status": status,
        "slug": slug,
        "body_markdown": body_markdown,
        "output_path": output_path,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    tags = "\n".join(f"  - {tag}" for tag in plan["tags"])
    return (
        "---\n"
        f"title: {plan['title']}\n"
        f"description: {plan['description']}\n"
        f"date: {plan['date']}\n"
        f"slug: {plan['slug']}\n"
        + (f"draft: true\n" if plan["status"] == "draft" else "")
        + "tags:\n"
        + f"{tags}\n"
        + "---\n\n"
        + f"{plan['body_markdown'].rstrip()}\n"
    )


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


def create_plan(args: argparse.Namespace) -> dict[str, Any]:
    target = resolve_target(args.target)
    if args.body_file:
        body = Path(args.body_file).expanduser().resolve().read_text(encoding="utf-8")
    else:
        body = args.body or ""
    raw_plan = {
        "title": args.title,
        "description": args.description,
        "date": args.date or today_iso(),
        "tags": split_tags(args.tags),
        "status": args.status,
        "slug": args.slug or slugify(args.title),
        "body_markdown": body,
    }
    validated = validate_plan(raw_plan, target)
    plan_for_file = {key: value for key, value in validated.items() if key != "output_path"}
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(plan_for_file, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "target": str(target),
        "plan_path": str(Path(args.out).expanduser().resolve()) if args.out else None,
        "planned_post_path": str(validated["output_path"]),
        "plan": plan_for_file,
    }


def run_build(target: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "scripts/build_blog.py"],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "build_ran": True,
        "build_returncode": proc.returncode,
        "build_stdout": proc.stdout.strip(),
        "build_stderr": proc.stderr.strip(),
    }


def apply_plan(
    target_arg: str,
    plan_path: str,
    *,
    dry_run: bool,
    force: bool,
    build: bool,
) -> dict[str, Any]:
    target = resolve_target(target_arg)
    if inspect_target(str(target))["missing_paths"]:
        raise SkillHelperError("Target does not look like the CVEngine portfolio repository")
    raw_plan = load_plan(plan_path)
    plan = validate_plan(raw_plan, target)
    output_path: Path = plan["output_path"]
    generated_path = target / "frontend" / "posts" / f"{plan['slug']}.html"
    exists = output_path.exists()

    if exists and not force:
        raise SkillHelperError(f"Post already exists; pass --force to overwrite: {output_path}")

    result: dict[str, Any] = {
        "ok": True,
        "target": str(target),
        "dry_run": dry_run,
        "slug": plan["slug"],
        "status": plan["status"],
        "written_path": str(output_path),
        "generated_path": str(generated_path),
        "would_overwrite": exists,
        "build_ran": False,
    }

    if dry_run:
        result["markdown_preview_chars"] = len(render_markdown(plan))
        return result

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(plan), encoding="utf-8")
    if build:
        result.update(run_build(target))
        result["generated_exists"] = generated_path.exists()
    return result


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create CVEngine portfolio blog posts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect target repo without side effects.")
    inspect_parser.add_argument("--target", required=True)
    inspect_parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is always emitted.")

    plan_parser = subparsers.add_parser("plan", help="Create and validate a blog post plan JSON.")
    plan_parser.add_argument("--target", required=True)
    plan_parser.add_argument("--title", required=True)
    plan_parser.add_argument("--description", required=True)
    plan_parser.add_argument("--tags", required=True, help="Comma-separated tags")
    plan_parser.add_argument("--status", choices=sorted(VALID_STATUSES), default="draft")
    plan_parser.add_argument("--date", default=None)
    plan_parser.add_argument("--slug", default=None)
    plan_parser.add_argument("--body", default=None)
    plan_parser.add_argument("--body-file", default=None)
    plan_parser.add_argument("--out", default=None)
    plan_parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is always emitted.")

    apply_parser = subparsers.add_parser("apply", help="Apply an explicit blog post plan.")
    apply_parser.add_argument("--target", required=True)
    apply_parser.add_argument("--plan", required=True)
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--force", action="store_true")
    apply_parser.add_argument("--build", action="store_true")
    apply_parser.add_argument("--json", action="store_true", help="Emit JSON. JSON is always emitted.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print_json(inspect_target(args.target))
            return 0
        if args.command == "plan":
            print_json(create_plan(args))
            return 0
        if args.command == "apply":
            print_json(
                apply_plan(
                    args.target,
                    args.plan,
                    dry_run=args.dry_run,
                    force=args.force,
                    build=args.build,
                )
            )
            return 0
        parser.error(f"Unknown command: {args.command}")
        return 2
    except (OSError, SkillHelperError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
