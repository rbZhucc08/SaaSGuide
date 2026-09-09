"""Analyze an authorized, de-identified phase-eleven pilot evidence file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.validation.pilot import PilotValidationError, analyze_study  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    path = args.input if args.input.is_absolute() else ROOT / args.input
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        result = analyze_study(document)
    except (OSError, json.JSONDecodeError, PilotValidationError) as error:
        print(f"Pilot evidence rejected: {error}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
