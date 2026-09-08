"""Dependency-free audit that exported V3 functions carry type annotations."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ROOT / "services" / "ai" / "provider.py",
    ROOT / "services" / "evaluation" / "independent.py",
    ROOT / "services" / "retrieval" / "knowledge_base.py",
    ROOT / "routes" / "v3_operations.py",
)


def main() -> int:
    errors: list[str] = []
    for path in TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name.startswith("_"):
                continue
            if node.returns is None:
                errors.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name} 缺少返回类型")
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            for argument in arguments:
                if argument.arg not in {"self", "cls"} and argument.annotation is None:
                    errors.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}.{argument.arg} 缺少类型")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"type annotation contract passed: {len(TARGETS)} critical modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
