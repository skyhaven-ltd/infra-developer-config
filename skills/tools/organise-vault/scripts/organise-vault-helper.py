from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


class SkillError(RuntimeError):
    pass


REQUIRED_FRONTMATTER = ["created", "modified", "tags", "aliases", "source", "status"]
TYPE_TAGS = {"concept", "runbook", "reference", "synopsis", "project", "journal", "moc", "inbox"}
STATUSES = {"unprocessed", "processed", "evergreen", "draft", "stale", "archived"}
PRESERVE_WHEN_FORMATTING = [
    "frontmatter",
    "wikilinks",
    "tags",
    "embeds",
    "tasks",
    "code fences",
    "dates",
    "paths",
    "quoted text",
]
TRIAGE_REPORT_NAME = "triage-report.md"
CONSOLIDATION_REPORT_NAME = "vault-consolidation.md"
CONSOLIDATION_ACTION_RE = re.compile(
    r"^\|\s*(VC-\d+)\s*\|\s*(.*?)\s*\|\s*(pending|approve|approved|run|skip|defer|done)\s*\|",
    flags=re.IGNORECASE | re.MULTILINE,
)


def out(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def fail(message: str) -> int:
    print(json.dumps({"error": message}, indent=2), file=sys.stderr)
    return 1


def target_dir(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise SkillError(f"Target directory does not exist: {path}")
    return path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def frontmatter(text: str) -> str | None:
    if text.startswith("---") and text.count("---") >= 2:
        return text.split("---", 2)[1]
    return None


def find_vault(arg: str | None = None) -> Path:
    if arg:
        return target_dir(arg)
    candidate = Path.home() / "Documents" / "Second Brain"
    if candidate.exists():
        return candidate.resolve()
    raise SkillError("Vault not found; ask for the vault path")


def wikilinks(text: str) -> list[str]:
    return [
        match.split("|", 1)[0].split("#", 1)[0].strip()
        for match in re.findall(r"\[\[([^\]]+)\]\]", text)
    ]


def md_files(path: Path) -> list[Path]:
    return [item for item in path.glob("*.md") if item.is_file()]


def parse_frontmatter_keys(raw: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"^([A-Za-z0-9_-]+):", raw, flags=re.MULTILINE)}


def parse_yaml_list(raw: str, key: str) -> list[str]:
    inline = re.search(rf"^{re.escape(key)}:\s*\[(.*?)\]\s*$", raw, flags=re.MULTILINE)
    if inline:
        return [item.strip().strip('"\'') for item in inline.group(1).split(",") if item.strip()]

    block = re.search(rf"^{re.escape(key)}:\s*\n((?:\s+-\s+.*\n?)*)", raw, flags=re.MULTILINE)
    if not block:
        return []
    return [line.split("-", 1)[1].strip().strip('"\'') for line in block.group(1).splitlines() if "-" in line]


def parse_scalar(raw: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.*?)\s*$", raw, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip().strip('"\'')
    return value or None


def tags_from_file(path: Path) -> list[str]:
    raw = frontmatter(read_text(path))
    if raw is None:
        return []
    return parse_yaml_list(raw, "tags")


def find_report_duplicates(meta: Path, canonical_name: str, legacy_pattern: str) -> list[str]:
    if not meta.exists():
        return []
    candidates = {path for path in meta.glob(legacy_pattern) if path.is_file()}
    canonical = meta / canonical_name
    if canonical.exists():
        candidates.add(canonical)
    return sorted(str(path) for path in candidates)


def parse_consolidation_actions(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "pending_input_count": 0,
            "approved_actions": [],
            "skipped_actions": [],
            "deferred_actions": [],
            "completed_actions": [],
        }

    text = read_text(path)
    actions: list[dict[str, str]] = []
    for match in CONSOLIDATION_ACTION_RE.finditer(text):
        action_id, description, response = match.groups()
        actions.append(
            {
                "id": action_id.strip(),
                "description": re.sub(r"<br\s*/?>", " ", description.strip(), flags=re.IGNORECASE),
                "response": response.lower().strip(),
            }
        )

    approved = [item for item in actions if item["response"] in {"approve", "approved", "run"}]
    skipped = [item for item in actions if item["response"] == "skip"]
    deferred = [item for item in actions if item["response"] == "defer"]
    completed = [item for item in actions if item["response"] == "done"]
    pending = [item for item in actions if item["response"] == "pending"]

    return {
        "exists": True,
        "path": str(path),
        "action_table_count": len(actions),
        "pending_input_count": len(pending),
        "approved_actions": approved,
        "skipped_actions": skipped,
        "deferred_actions": deferred,
        "completed_actions": completed,
        "has_approved_actions_to_run": bool(approved),
        "expected_response_values": ["pending", "approve", "skip", "defer", "done"],
        "expected_table_header": "| ID | Proposed action | Liam response |",
    }


def previous_consolidation_path(meta: Path) -> Path:
    canonical = meta / CONSOLIDATION_REPORT_NAME
    if canonical.exists():
        return canonical

    legacy = [
        path
        for pattern in ["vault-consolidation*.actions.md", "vault-consolidation*.report.md", "vault-consolidation*.md"]
        for path in meta.glob(pattern)
        if path.is_file()
    ]
    if legacy:
        return max(legacy, key=lambda item: item.stat().st_mtime)

    return canonical


def inspect_previous_reports(meta: Path) -> dict[str, Any]:
    triage_paths = find_report_duplicates(meta, TRIAGE_REPORT_NAME, "triage-report*.md")
    consolidation_paths = find_report_duplicates(meta, CONSOLIDATION_REPORT_NAME, "vault-consolidation*.md")
    consolidation_to_check = previous_consolidation_path(meta)

    return {
        "single_report_policy": {
            "triage_report_name": TRIAGE_REPORT_NAME,
            "consolidation_report_name": CONSOLIDATION_REPORT_NAME,
            "legacy_dated_reports_should_be_consolidated": True,
            "separate_actions_file_should_not_be_created": True,
        },
        "triage_reports": triage_paths,
        "triage_report_count": len(triage_paths),
        "consolidation_reports": consolidation_paths,
        "consolidation_report_count": len(consolidation_paths),
        "previous_consolidation": parse_consolidation_actions(consolidation_to_check),
        "report_policy_issues": [
            issue
            for issue, has_issue in {
                "multiple_triage_reports": len(triage_paths) > 1,
                "multiple_consolidation_reports": len(consolidation_paths) > 1,
                "legacy_actions_file_present": any(path.endswith(".actions.md") for path in consolidation_paths),
            }.items()
            if has_issue
        ],
    }


def inspect_frontmatter(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for path in files:
        text = read_text(path)
        raw = frontmatter(text)
        if raw is None:
            issues.append({"file": str(path.relative_to(root)), "issues": ["missing_frontmatter"]})
            continue

        keys = parse_frontmatter_keys(raw)
        file_issues = [f"missing_{field}" for field in REQUIRED_FRONTMATTER if field not in keys]
        tags = parse_yaml_list(raw, "tags")
        type_tags = [tag for tag in tags if tag in TYPE_TAGS]
        status = parse_scalar(raw, "status")

        if len(type_tags) != 1:
            file_issues.append("expected_exactly_one_type_tag")
        if status is not None and status not in STATUSES:
            file_issues.append("invalid_status")
        if file_issues:
            issues.append({"file": str(path.relative_to(root)), "issues": file_issues})
    return issues


def inspect_vault(vault: str | None = None) -> dict[str, Any]:
    root = find_vault(vault)
    inbox = root / "00 - Inbox"
    notes = root / "02 - Notes"
    mocs = root / "01 - MOCs"
    meta = root / "99 - Meta" / "AI Formatting"
    templates = root / "99 - Meta" / "Templates"
    vocab = meta / "tag-vocabulary.md"
    workflow = meta / "LLM Vault Workflow.md"

    scan_dirs = [notes, mocs, root / "99 - Meta" / "Archived Journal"]
    files = [file for directory in scan_dirs if directory.exists() for file in md_files(directory)]
    names = {file.stem for file in files}
    dead: list[dict[str, str]] = []
    backlinks = {name: 0 for name in names}
    tags: dict[str, int] = {}

    for file in files:
        text = read_text(file)
        for link in wikilinks(text):
            if link and link not in names:
                dead.append({"file": str(file.relative_to(root)), "target": link})
            elif link in backlinks:
                backlinks[link] += 1
        for tag in re.findall(r"(?<!\w)#([-\w/]+)", text):
            tags[tag] = tags.get(tag, 0) + 1

    inbox_files = [path for path in inbox.glob("*.md")] if inbox.exists() else []
    inbox_file_tags = {path: tags_from_file(path) for path in inbox_files}
    pinned_inbox_files = [path for path, file_tags in inbox_file_tags.items() if "pinned" in file_tags]
    orphans = [
        name
        for name, count in backlinks.items()
        if count == 0 and (notes / f"{name}.md").exists()
    ]

    return {
        "vault": str(root),
        "workflow_path": str(workflow) if workflow.exists() else None,
        "workflow_exists": workflow.exists(),
        "tag_vocabulary_path": str(vocab) if vocab.exists() else None,
        "tag_vocabulary_exists": vocab.exists(),
        "templates": {
            name: (templates / name).exists()
            for name in [
                "Generic Note Template.md",
                "Inbox Note Template.md",
                "MOC Template.md",
                "Source Note Template.md",
            ]
        },
        "inbox_exists": inbox.exists(),
        "pinned_inbox_count": len(pinned_inbox_files),
        "pinned_inbox_files": [str(path.relative_to(root)) for path in pinned_inbox_files],
        "inbox_files": [
            {
                "path": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "has_frontmatter": frontmatter(read_text(path)) is not None,
                "tags": inbox_file_tags.get(path, []),
                "is_pinned": "pinned" in inbox_file_tags.get(path, []),
            }
            for path in inbox_files
        ],
        "note_titles": [path.stem for path in notes.glob("*.md")] if notes.exists() else [],
        "moc_titles": [path.stem for path in mocs.glob("*.md")] if mocs.exists() else [],
        "files_scanned": len(files),
        "dead_wikilinks": dead[:200],
        "dead_wikilink_count": len(dead),
        "orphan_note_titles": orphans[:200],
        "orphan_count": len(orphans),
        "applied_tags": tags,
        "frontmatter_issues": inspect_frontmatter(root, files)[:200],
        "frontmatter_standard": ["created", "modified", "tags", "aliases", "source", "status", "confidence"],
        "report_paths": {
            "triage": str(meta / TRIAGE_REPORT_NAME),
            "consolidation": str(meta / CONSOLIDATION_REPORT_NAME),
        },
        "previous_reports": inspect_previous_reports(meta),
        "risk_flags": [
            key
            for key, is_risk in {
                "missing_inbox": not inbox.exists(),
                "missing_notes": not notes.exists(),
                "missing_mocs": not mocs.exists(),
                "missing_tag_vocabulary": not vocab.exists(),
                "missing_llm_vault_workflow": not workflow.exists(),
            }.items()
            if is_risk
        ],
        "llm_decisions": [
            "triage bucket selection",
            "pinned inbox retention judgement",
            "source-to-durable-note synthesis",
            "MOC placement",
            "similarity and merge judgement",
            "stale or superseded claim judgement",
            "frontmatter cleanup recommendations",
        ],
    }


def inspect_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.exists() or path.suffix.lower() != ".md":
        raise SkillError(f"Markdown file does not exist: {path}")
    text = read_text(path)
    headings = re.findall(r"(?m)^#\s+(.+)$", text)
    expected_h1 = " ".join(word.capitalize() for word in path.stem.split())
    return {
        "file": str(path),
        "bytes": len(text.encode()),
        "has_frontmatter": frontmatter(text) is not None,
        "h1_headings": headings,
        "expected_h1": expected_h1,
        "wikilink_count": len(re.findall(r"\[\[[^\]]+\]\]", text)),
        "tag_count": len(re.findall(r"(?<!\w)#[-\w/]+", text)),
        "contains_mojibake_em_dash": "Ã¢â‚¬â€" in text,
        "contains_em_dash": "â€”" in text,
        "trailing_whitespace_lines": [index + 1 for index, line in enumerate(text.splitlines()) if line.rstrip() != line][:50],
        "llm_must_preserve": PRESERVE_WHEN_FORMATTING,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--vault", default=None)
    inspect_parser.add_argument("--json", action="store_true")

    file_parser = sub.add_parser("inspect-file")
    file_parser.add_argument("--file", required=True)
    file_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "inspect":
            out(inspect_vault(args.vault))
        elif args.cmd == "inspect-file":
            out(inspect_file(args.file))
        return 0
    except SkillError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
