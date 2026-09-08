"""Provider-neutral contracts and deterministic token-budget guards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class JsonModelProvider(Protocol):
    provider_name: str
    model: str
    last_usage: dict[str, int]
    last_run: dict[str, Any]

    def create_json(self, messages: list[dict[str, str]], *, batch_budget: "BatchBudget | None" = None) -> str:
        ...


@dataclass(frozen=True)
class BudgetPolicy:
    version: str = "model-budget-v1"
    max_input_tokens: int = 8_000
    max_output_tokens: int = 2_000
    max_total_tokens: int = 10_000
    max_batch_calls: int = 10
    max_batch_total_tokens: int = 30_000


class BudgetExceededError(ValueError):
    code = "over_budget"


def estimate_message_tokens(messages: list[dict[str, str]]) -> int:
    """Conservative local estimate used only as a pre-call spending guard."""
    characters = sum(len(str(item.get("role", ""))) + len(str(item.get("content", ""))) for item in messages)
    return max(1, (characters + 2) // 3)


class BatchBudget:
    """Reserve worst-case tokens before each call in an explicitly bounded batch."""

    def __init__(self, policy: BudgetPolicy | None = None) -> None:
        self.policy = policy or BudgetPolicy()
        self.calls = 0
        self.reserved_tokens = 0

    def reserve(self, input_tokens: int, output_tokens: int) -> dict[str, int]:
        requested = input_tokens + output_tokens
        if self.calls + 1 > self.policy.max_batch_calls:
            raise BudgetExceededError("批量模型调用次数超过预算上限")
        if self.reserved_tokens + requested > self.policy.max_batch_total_tokens:
            raise BudgetExceededError("批量模型调用 Token 预算不足")
        self.calls += 1
        self.reserved_tokens += requested
        return {"calls": self.calls, "reserved_tokens": self.reserved_tokens}
