"""Check repository-local links in Markdown files.

The checker deliberately ignores web URLs and in-page anchors. It validates the
filesystem target before an optional ``#anchor`` so moved historical records do
not silently leave broken reader paths behind.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
IGNORED_PREFIXES = ("http://", "https://", "mailto:", "data:", "codex:", "#")


def markdown_files() -> list[Path]:
    excluded = {".git", ".venv", "generated", "resume_work", "work", "__pycache__"}
    return [
        path
        for path in ROOT.rglob("*.md")
        if not any(part in excluded for part in path.relative_to(ROOT).parts)
    ]


def local_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if not target or target.lower().startswith(IGNORED_PREFIXES):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(target) or None


def main() -> int:
    failures: list[str] = []
    checked = 0
    for markdown in markdown_files():
        content = markdown.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            target = local_target(match.group(1))
            if target is None:
                continue
            checked += 1
            resolved = (markdown.parent / target).resolve()
            if not resolved.exists():
                line = content.count("\n", 0, match.start()) + 1
                failures.append(
                    f"{markdown.relative_to(ROOT)}:{line}: missing {match.group(1)}"
                )

    if failures:
        print("Markdown link check failed:")
        print("\n".join(failures))
        return 1
    print(f"Markdown link check passed: {checked} local links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
