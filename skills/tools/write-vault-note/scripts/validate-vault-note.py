#!/usr/bin/env python3
"""Validate an Obsidian vault note against the LLM Vault Workflow schema.

Deterministic gate for the write-vault-note skill: the agent drafts a note,
this script decides whether it conforms. Exit 0 means valid (warnings are
allowed), exit 1 means the note must be fixed, exit 2 means the environment
or arguments are wrong.

Usage:
    python validate-vault-note.py <note-file>

Schema (simplified, 2026-07-19): every note carries exactly the frontmatter
keys title, created, modified, type, tags, source. The `type` field replaces
the old type tags; tags are emergent (reused from the vault) rather than drawn
from a controlled vocabulary.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MOJIBAKE_PATTERN = re.compile(r"â€|Ã.|â€™|â€œ")
REQUIRED_KEYS = ["title", "created", "modified", "type", "tags", "source"]
NOTE_TYPES = {"note", "inbox", "moc", "daily"}
MANAGED_FOLDERS = ["00 - Inbox", "01 - MOCs", "02 - Notes", "03 - Journaling"]


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def load_vault_tags(vault_root: Path) -> set[str]:
    """Collect every tag already used in the managed folders."""
    tags: set[str] = set()
    for folder in MANAGED_FOLDERS:
        folder_path = vault_root / folder
        if not folder_path.is_dir():
            continue
        for note in folder_path.glob("*.md"):
            lines = note.read_text(encoding="utf-8-sig").splitlines()
            frontmatter, _, _ = parse_frontmatter(lines)
            values = frontmatter.get("tags")
            if isinstance(values, list):
                tags.update(tag for tag in values if isinstance(tag, str))
    return tags


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
        if line.strip().startswith("#"):
            continue

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

    content = note_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    errors: list[str] = []
    warnings: list[str] = []

    frontmatter, body_start, frontmatter_errors = parse_frontmatter(lines)
    errors.extend(frontmatter_errors)

    for key in REQUIRED_KEYS:
        if key not in frontmatter:
            errors.append(f"missing frontmatter key: {key}")
    for key in frontmatter:
        if key not in REQUIRED_KEYS:
            errors.append(f"unknown frontmatter key: {key} (schema allows only {', '.join(REQUIRED_KEYS)})")

    note_type = frontmatter.get("type")
    if "type" in frontmatter and note_type not in NOTE_TYPES:
        errors.append(f"type must be one of {', '.join(sorted(NOTE_TYPES))}, got: {note_type}")

    for key in ("created", "modified"):
        value = frontmatter.get(key)
        if isinstance(value, str) and not DATE_PATTERN.match(value):
            errors.append(f"{key} must be YYYY-MM-DD, got: {value}")

    tags = frontmatter.get("tags")
    if "tags" in frontmatter and not isinstance(tags, list):
        errors.append("tags must be a list (use `tags: []` when empty)")
    elif isinstance(tags, list):
        tag_values = [tag for tag in tags if tag is not None]
        for tag in tag_values:
            if not TAG_PATTERN.match(str(tag)):
                errors.append(f"tag must be lowercase-hyphenated: {tag}")
        if "pinned" in tag_values and note_type != "inbox":
            errors.append("`pinned` is only valid on inbox notes")
        topic_tags = [tag for tag in tag_values if tag != "pinned"]
        if note_type == "note" and not topic_tags:
            warnings.append("no topic tags; permanent notes should carry 1-3")
        if len(topic_tags) > 3:
            warnings.append(f"{len(topic_tags)} topic tags; more than 3 usually means the note should be split")
        vault_tags = load_vault_tags(vault_root)
        new_tags = [tag for tag in topic_tags if tag not in vault_tags]
        if new_tags:
            warnings.append(
                f"tags not yet used in the vault: {', '.join(new_tags)} "
                "(reuse an existing tag unless nothing fits)"
            )

    if "source" in frontmatter:
        source = frontmatter.get("source")
        if isinstance(source, list) and not source:
            errors.append("source must be null, a value, or a non-empty list")

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
