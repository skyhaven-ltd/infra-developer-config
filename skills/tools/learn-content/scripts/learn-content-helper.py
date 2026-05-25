from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class SkillError(RuntimeError):
    pass


def out(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def fail(message: str) -> int:
    print(json.dumps({"error": message}, indent=2), file=sys.stderr)
    return 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def strip_frontmatter(text: str) -> tuple[str | None, str]:
    if text.startswith("---"):
        match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, flags=re.S)
        if match:
            return match.group(1), text[match.end():]
    return None, text


def inspect_file(path_text: str) -> dict[str, Any]:
    path = Path(path_text).expanduser().resolve()
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".md":
        raise SkillError(f"Markdown file does not exist: {path}")

    text = read_text(path)
    frontmatter, body = strip_frontmatter(text)
    headings = [
        {"level": len(match.group(1)), "title": match.group(2).strip()}
        for match in re.finditer(r"(?m)^(#{1,6})\s+(.+)$", body)
    ]

    return {
        "file": str(path),
        "has_frontmatter": frontmatter is not None,
        "word_count": len(re.findall(r"\w+", body)),
        "headings": headings[:100],
        "bullet_count": len(re.findall(r"(?m)^\s*[-*+]\s+", body)),
        "code_block_count": len(re.findall(r"```", body)) // 2,
        "suggested_learning_outputs": [
            "thesis",
            "learning map",
            "mental models",
            "trade-offs",
            "misconceptions",
            "application prompts",
            "sources",
            "learning-app frontmatter",
        ],
        "valid_learning_question_types": [
            "multiple-choice",
            "short-answer",
            "rubric",
            "categorisation",
        ],
    }


def inspect_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SkillError(f"Unsupported URL scheme for {url}")
    if not parsed.netloc:
        raise SkillError(f"Missing host in URL: {url}")

    host = parsed.netloc.lower()
    path = parsed.path.lower().rstrip("/")
    risk_flags: list[str] = []

    broad_paths = {"", "/", "/docs", "/learn", "/training", "/courses", "/blog", "/articles"}
    listing_markers = ("/search", "/tag/", "/tags/", "/category/", "/categories/", "/archive")

    if path in broad_paths:
        risk_flags.append("broad_source_confirm_scope")
    if any(marker in path for marker in listing_markers):
        risk_flags.append("index_or_listing_confirm_scope")
    if host in {"github.com", "www.github.com"} and len([p for p in path.split("/") if p]) <= 2:
        risk_flags.append("repository_root_confirm_scope")
    if "learn.microsoft.com" in host and "/training/paths/" in path:
        risk_flags.append("learning_path_confirm_scope")

    return {
        "url": url,
        "host": host,
        "path": parsed.path,
        "risk_flags": risk_flags,
    }


def inspect_urls(urls: list[str]) -> dict[str, Any]:
    sources = [inspect_url(url) for url in urls]
    return {
        "source_count": len(sources),
        "hosts": sorted({source["host"] for source in sources}),
        "sources": sources,
        "has_scope_risks": any(source["risk_flags"] for source in sources),
        "llm_tasks": [
            "fetch and read provided sources",
            "preserve source links",
            "extract learning structure",
            "synthesize themes and mental models",
            "build scenario reasoning",
            "set learning_status to needs-questions",
            "set learning_question_types to the canonical valid values",
        ],
    }


def find_vault(start_text: str) -> Path:
    start = Path(start_text).expanduser().resolve()
    current = start if start.is_dir() else start.parent

    for candidate in [current, *current.parents]:
        if (candidate / ".obsidian").is_dir():
            return candidate

    raise SkillError(f"No Obsidian vault found at or above: {start}")


def detect_vault(path_text: str) -> dict[str, Any]:
    vault = find_vault(path_text)
    preferred = vault / "00 - Inbox" / "Learning Notes"
    return {
        "vault": str(vault),
        "has_obsidian_dir": True,
        "preferred_output_dir": str(preferred),
        "preferred_output_dir_exists": preferred.is_dir(),
    }


def slugify(title: str) -> str:
    slug = title.strip().lower()
    slug = re.sub(r"[\\/:*?\"<>|]+", " ", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80] or "learning-note"


def suggest_output(vault_text: str, title: str, folder: str | None) -> dict[str, Any]:
    vault = find_vault(vault_text)
    relative_folder = Path(folder) if folder else Path("00 - Inbox")
    if relative_folder.is_absolute():
        raise SkillError("Output folder must be relative to the vault root")

    output_dir = (vault / relative_folder).resolve()
    if not str(output_dir).startswith(str(vault.resolve())):
        raise SkillError("Output folder escapes the vault root")

    file_name = f"{date.today().isoformat()} - {slugify(title)}.md"
    output_file = output_dir / file_name

    return {
        "vault": str(vault),
        "output_dir": str(output_dir),
        "output_file": str(output_file),
        "output_file_exists": output_file.exists(),
        "create_directory_if_missing": not output_dir.exists(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    inspect_file_parser = sub.add_parser("inspect-file")
    inspect_file_parser.add_argument("--file", required=True)
    inspect_file_parser.add_argument("--json", action="store_true")

    inspect_urls_parser = sub.add_parser("inspect-urls")
    inspect_urls_parser.add_argument("--urls", nargs="+", required=True)
    inspect_urls_parser.add_argument("--json", action="store_true")

    detect_vault_parser = sub.add_parser("detect-vault")
    detect_vault_parser.add_argument("--path", default=".")
    detect_vault_parser.add_argument("--json", action="store_true")

    suggest_output_parser = sub.add_parser("suggest-output")
    suggest_output_parser.add_argument("--vault", default=".")
    suggest_output_parser.add_argument("--title", required=True)
    suggest_output_parser.add_argument("--folder")
    suggest_output_parser.add_argument("--json", action="store_true")

    ns = parser.parse_args(argv)

    try:
        if ns.cmd == "inspect-file":
            out(inspect_file(ns.file))
        elif ns.cmd == "inspect-urls":
            out(inspect_urls(ns.urls))
        elif ns.cmd == "detect-vault":
            out(detect_vault(ns.path))
        elif ns.cmd == "suggest-output":
            out(suggest_output(ns.vault, ns.title, ns.folder))
        else:
            raise SkillError(f"Unsupported command: {ns.cmd}")
        return 0
    except SkillError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

