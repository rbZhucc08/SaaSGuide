"""Cross-platform entry point used by PowerShell and CI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JAVASCRIPT_FILES = (
    "app.js", "builder.js", "shell.js", "data-sources.js", "risk-radar.js",
    "evidence-intake.js", "knowledge-base.js", "action-tracker.js", "reports.js", "input-lab.js",
)


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    node = shutil.which("node")
    git = shutil.which("git")
    if not node or not git:
        print("需要可用的 Node.js 和 Git", file=sys.stderr)
        return 2
    try:
        run([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"])
        run([sys.executable, "scripts/stdlib_coverage.py"])
        run([sys.executable, "scripts/type_contract_check.py"])
        run([sys.executable, "validate_data.py"])
        run([sys.executable, "scripts/check_markdown_links.py"])
        for filename in JAVASCRIPT_FILES:
            run([node, "--check", filename])
        run([git, "diff", "--check"])
    except subprocess.CalledProcessError as error:
        return error.returncode or 1
    print("全部检查通过：自动测试、数据、Markdown、JavaScript 和 Git 差异。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
