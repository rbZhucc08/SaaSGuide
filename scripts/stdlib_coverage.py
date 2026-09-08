"""Run the unittest suite and enforce statement coverage on V3 critical modules."""

from __future__ import annotations

import ast
import sys
import trace
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TARGETS = (
    ROOT / "services" / "ai" / "provider.py",
    ROOT / "services" / "evaluation" / "independent.py",
    ROOT / "services" / "retrieval" / "knowledge_base.py",
    ROOT / "database" / "store.py",
)
MINIMUM_PERCENT = 60.0


def statement_lines(path: Path) -> set[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt)}


def run_suite() -> unittest.result.TestResult:
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        "test_model_reliability",
        "test_independent_evaluation",
        "test_document_retrieval",
        "test_knowledge_base",
        "test_sqlite_store",
        "test_v3_workflow",
    ])
    return unittest.TextTestRunner(verbosity=1).run(suite)


def main() -> int:
    tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix])
    result = tracer.runfunc(run_suite)
    if not result.wasSuccessful():
        return 1
    counts = tracer.results().counts
    total = covered = 0
    for path in TARGETS:
        lines = statement_lines(path)
        hit = {line for (filename, line), count in counts.items() if count and Path(filename).resolve() == path.resolve()}
        executable = len(lines)
        executed = len(lines & hit)
        percent = executed / executable * 100 if executable else 100.0
        print(f"coverage {path.relative_to(ROOT)}: {executed}/{executable} ({percent:.2f}%)")
        total += executable
        covered += executed
    aggregate = covered / total * 100 if total else 100.0
    print(f"critical aggregate statement coverage: {covered}/{total} ({aggregate:.2f}%), minimum {MINIMUM_PERCENT:.2f}%")
    return 0 if aggregate >= MINIMUM_PERCENT else 2


if __name__ == "__main__":
    raise SystemExit(main())
