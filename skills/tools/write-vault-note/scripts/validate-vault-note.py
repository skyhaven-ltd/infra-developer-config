#!/usr/bin/env python3
"""Validate an Obsidian vault note against the LLM Vault Workflow schema.

Deterministic gate for the write-vault-note skill: the agent drafts a note,
this script decides whether it conforms. Exit 0 means valid (warnings are
allowed), exit 1 means the note must be fixed, exit 2 means the environment
or arguments are wrong.

Usage:
    python validate-vault-note.py <note-file> [--inbox]

--inbox validates against the inbox-template frontmatter (no learning fields)
instead of the maintained-note frontmatter.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TAG_BULLET_PATTERN = re.compile(r"^- `([a-z0-9-]+)`\s*:")
MOJIBAKE_PATTERN = re.compile(r"â€|Ã.|â€™|â€œ")
LEARNING_TYPES = {"multiple-choice", "short-answer", "rubric", "categorisation"}
MAINTAINED_KEYS = [
    "title", "created", "modified", "sources", "tags", "aliases",
    "learning_status", "learning_question_goal", "learning_question_types",
]
INBOX_KEYS = ["title", "created", "modified", "sources", "tags", "aliases"]


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def load_tag_vocabulary(vault_root: Path) -> tuple[set[str], set[str], set[str]]:
    """Return (all_tags, type_tags, state_tags) from tag-vocabulary.md."""
    vocabulary_path = vault_root / "99 - Meta" / "AI Formatting" / "tag-vocabulary.md"
    if not vocabulary_path.is_file():
        fail(f"tag vocabulary not found: {vocabulary_path}")

    all_tags: set[str] = set()
    type_tags: set[str] = set()
    state_tags: set[str] = set()
    section = ""
    for line in vocabulary_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        match = TAG_BULLET_PATTERN.match(line.strip())
        if not match:
            continue
        tag = match.group(1)
        all_tags.add(tag)
        if section == "Type Tags":
            type_tags.add(tag)
        elif section == "State Tags":
            state_tags.add(tag)
    if not all_tags or not type_tags:
        fail(f"could not parse tags from {vocabulary_path}")
    return all_tags, type_tags, state_tags


def parse_frontmatter(lines: list[str]) -> tuple[dict[str, object], int, list[str]]:
    """Parse the constrained YAML frontmatter used by the vault.

    Supports scalars, inline lists, and block lists. Returns
    (frontmatter, index of the line after the closing ---, errors).
    """
    errors: list[str] = []
    if not lines or lines[0].strip() != "---":
        return {}, 0, ["note must start with a `---` frontmatter block"]

    frontmatter: dict[str, object] = {}
    current_list_key: str | None = None
    index = 1
    while index < len(lines):
        raw = lines[index]
        line = raw.rstrip()
        index += 1
        if line.strip() == "---":
            return frontmatter, index, errors

        if re.match(r"^\s+-\s", line) or line.startswith("- "):
            if current_list_key is None:
                errors.append(f"list item outside a list key: {line.strip()}")
                continue
            item = line.strip()[1:].strip().strip('"').strip("'")
            frontmatter[current_list_key].append(None if item == "null" else item)
            continue

        match = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not match:
            if line.strip():
                errors.append(f"unparseable frontmatter line: {line.strip()}")
            continue
        key, value = match.group(1), match.group(2).strip()
        if value == "":
            frontmatter[key] = []
            current_list_key = key
            continue
        current_list_key = None
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            items = [
                item.strip().strip('"').strip("'")
                for item in inner.split(",")
                if item.strip()
            ]
            frontmatter[key] = [None if item == "null" else item for item in items]
        else:
            cleaned = value.strip('"').strip("'")
            frontmatter[key] = None if cleaned == "null" else cleaned

    return frontmatter, index, ["frontmatter block is never closed with `---`"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("note", help="path to the markdown note to validate")
    parser.add_argument(
        "--inbox",
        action="store_true",
        help="validate as an inbox note (no learning fields required)",
    )
    arguments = parser.parse_args()

    vault_value = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault_value:
        fail("OBSIDIAN_VAULT_PATH is not set")
    vault_root = Path(vault_value)
    if not (vault_root / ".obsidian").is_dir():
        fail(f"OBSIDIAN_VAULT_PATH is not an Obsidian vault: {vault_root}")

    note_path = Path(arguments.note)
    if not note_path.is_file():
        fail(f"note not found: {note_path}")

    all_tags, type_tags, state_tags = load_tag_vocabulary(vault_root)
    content = note_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    errors: list[str] = []
    warnings: list[str] = []

    frontmatter, body_start, frontmatter_errors = parse_frontmatter(lines)
    errors.extend(frontmatter_errors)

    required = INBOX_KEYS if arguments.inbox else MAINTAINED_KEYS
    for key in required:
        if key not in frontmatter:
            errors.append(f"missing frontmatter key: {key}")
    if arguments.inbox:
        for key in ("learning_status", "learning_question_goal", "learning_question_types"):
            if key in frontmatter:
                errors.append(f"inbox notes must not carry learning field: {key}")

    for key in ("created", "modified"):
        value = frontmatter.get(key)
        if isinstance(value, str) and not DATE_PATTERN.match(value):
            errors.append(f"{key} must be YYYY-MM-DD, got: {value}")

    sources = frontmatter.get("sources")
    if "sources" in frontmatter and (not isinstance(sources, list) or not sources):
        errors.append("sources must be a non-empty list (use `- null` when there is no source)")

    tags = frontmatter.get("tags")
    if isinstance(tags, list) and tags:
        tag_values = [tag for tag in tags if tag is not None]
        unknown = [tag for tag in tag_values if tag not in all_tags]
        if unknown:
            errors.append(
                f"tags not in tag-vocabulary.md: {', '.join(unknown)} "
                "(propose under `## Pending Approval` instead of inventing)"
            )
        note_type_tags = [tag for tag in tag_values if tag in type_tags]
        if len(note_type_tags) != 1:
            errors.append(
                f"exactly one type tag required, found {len(note_type_tags)}: "
                f"{', '.join(note_type_tags) or '(none)'}"
            )
        topic = [t for t in tag_values if t not in type_tags and t not in state_tags]
        if not topic:
            errors.append("at least one topic tag is required")
        if len(tag_values) > 4 and "pinned" not in tag_values:
            warnings.append(f"{len(tag_values)} tags; more than 4 usually means the note should be split")
        if arguments.inbox and "inbox" not in tag_values:
            errors.append("inbox notes must carry the `inbox` tag")
        if not arguments.inbox and "inbox" in tag_values:
            errors.append("maintained notes must not carry the `inbox` tag")
    elif "tags" in frontmatter:
        errors.append("tags must be a non-empty list")

    if not arguments.inbox:
        status = frontmatter.get("learning_status")
        if isinstance(status, str) and status != "needs-questions":
            warnings.append(
                f"learning_status is `{status}`; use `needs-questions` unless Liam asked otherwise"
            )
        goal = frontmatter.get("learning_question_goal")
        if isinstance(goal, str):
            if not goal.isdigit() or not (1 <= int(goal) <= 20):
                errors.append(f"learning_question_goal must be an integer 1-20, got: {goal}")
        question_types = frontmatter.get("learning_question_types")
        if isinstance(question_types, list):
            invalid = [q for q in question_types if q not in LEARNING_TYPES]
            if invalid:
                errors.append(f"invalid learning_question_types: {', '.join(map(str, invalid))}")
            if not question_types:
                errors.append("learning_question_types must not be empty")

    body = lines[body_start:]
    h1_lines = [line for line in body if re.match(r"^# \S", line)]
    if len(h1_lines) != 1:
        errors.append(f"exactly one H1 required in the body, found {len(h1_lines)}")
    else:
        h1_title = h1_lines[0][2:].strip()
        title = frontmatter.get("title")
        if isinstance(title, str) and title != h1_title:
            warnings.append(
                f"title `{title}` differs from H1 `{h1_title}`; allowed only when intentional"
            )

    if MOJIBAKE_PATTERN.search(content):
        errors.append("mojibake detected (e.g. `â€`); fix the encoding before saving")
    if "—" in content:
        warnings.append("em dash present; prefer normal punctuation unless quoting source text")
    if re.search(r"[ \t]+$", content, flags=re.MULTILINE):
        warnings.append("trailing whitespace present")

    for warning in warnings:
        print(f"warning: {warning}")
    for error_message in errors:
        print(f"error: {error_message}")
    if errors:
        print(f"\nINVALID: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"\nVALID: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
