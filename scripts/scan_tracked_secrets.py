"""Fail when Git-tracked files contain likely live secret values."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("generic_secret", re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]([^'\"\s]{12,})")),
)
PLACEHOLDERS = {"your_key_here", "replace_me", "placeholder", "example", "changeme", "test-key"}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / value.decode("utf-8") for value in output.split(b"\0") if value]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(1).lower() if match.lastindex else ""
                if any(marker in value for marker in PLACEHOLDERS):
                    continue
                findings.append(f"{relative}:{line_number} [{label}]")
    if findings:
        print("疑似密钥出现在 Git 跟踪文件中（不回显匹配值）：")
        print("\n".join(findings))
        return 1
    print("Git 跟踪文件密钥扫描通过（启发式扫描，不替代历史扫描或密钥轮换）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
