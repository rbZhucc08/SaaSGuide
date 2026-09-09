"""Scan reachable Git blobs for likely secrets and personal-data indicators."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    ("private_key", "blocking", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_token", "blocking", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("assigned_secret", "blocking", re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]([^'\"\s]{12,})")),
    ("email", "review", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("china_mobile", "review", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("windows_user_path", "review", re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+")),
)
PLACEHOLDER_MARKERS = ("test-key", "example.com", "your_key", "replace_me", "placeholder", "changeme")

def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)

def audit() -> dict[str, object]:
    objects = _git("rev-list", "--objects", "--all").decode("utf-8", errors="replace").splitlines()
    seen: set[str] = set()
    findings: list[dict[str, str]] = []
    scanned = 0
    for line in objects:
        oid, _, path = line.partition(" ")
        if not path or oid in seen:
            continue
        seen.add(oid)
        try:
            content = _git("cat-file", "-p", oid)
        except subprocess.CalledProcessError:
            continue
        if b"\0" in content[:4096] or len(content) > 5 * 1024 * 1024:
            continue
        text = content.decode("utf-8", errors="ignore")
        scanned += 1
        for category, severity, pattern in PATTERNS:
            for match in pattern.finditer(text):
                value = (match.group(1) if match.lastindex else match.group(0)).lower()
                if any(marker in value for marker in PLACEHOLDER_MARKERS):
                    continue
                findings.append({"path": path.replace("\\", "/"), "category": category, "severity": severity})
    unique = sorted({(item["path"], item["category"], item["severity"]) for item in findings})
    normalized = [{"path": path, "category": category, "severity": severity} for path, category, severity in unique]
    counts = Counter(item["severity"] for item in normalized)
    return {
        "status": "blocked" if counts["blocking"] else ("review_required" if counts["review"] else "passed"),
        "reachable_text_blobs_scanned": scanned,
        "findings": normalized,
        "counts": dict(counts),
        "matched_values_included": False,
        "limitations": "启发式扫描；不会证明历史绝对无密钥，二进制文件需要另行检查。",
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit()
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        target = args.report if args.report.is_absolute() else ROOT / args.report
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    print(f"Git history audit: {result['status']}; text blobs={result['reachable_text_blobs_scanned']}; findings={len(result['findings'])}")
    return 1 if result["status"] == "blocked" else 0

if __name__ == "__main__":
    raise SystemExit(main())
