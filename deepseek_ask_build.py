"""Use DeepSeek to turn a SaaS feature brief into an ASK or BUILD result."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from services.ai.provider import BatchBudget, BudgetExceededError, BudgetPolicy, estimate_message_tokens
from validate_data import HTML_FILE, collect_html_ids, validate_guide_data


API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
PROVIDER_NAME = "deepseek"
CLIENT_PROTOCOL_VERSION = "deepseek-json-v1"

REQUIRED_BRIEF_FIELDS: dict[str, tuple[type, str]] = {
    "featureName": (str, "功能名称"),
    "featureBrief": (str, "功能说明"),
    "targetUsers": (str, "目标用户"),
    "entryPoint": (str, "功能入口"),
    "operationSteps": (list, "操作步骤"),
    "successState": (str, "成功状态"),
    "pageElements": (dict, "页面元素清单"),
}

SYSTEM_PROMPT = """你是 SaaSGuide 的需求判断器。只输出一个合法的 json 对象，不要输出 Markdown 或额外文字。

任务：判断用户提供的功能 Brief 是否足以生成网页操作引导。

规则：
1. 信息缺失、含糊或步骤无法映射到页面元素时，decision 必须是 ASK，并提出最少且明确的问题。
2. 信息充分时，decision 必须是 BUILD，并生成顺序连续、目标不重复的引导步骤。
3. BUILD.pageElements 必须原样使用输入中的页面元素键和值，不得虚构页面 id。
4. 每个 guideSteps.target 必须引用 pageElements 中的键。
5. action 是可选字段；当前只允许 filter-high，不需要动作时不要输出 action。

ASK 的 json 示例：
{
  "decision": "ASK",
  "reason": "缺少目标用户",
  "questions": [
    {"field": "targetUsers", "question": "这个功能主要供哪类用户使用？"}
  ]
}

BUILD 的 json 示例：
{
  "decision": "BUILD",
  "reason": "输入信息完整且步骤可映射到页面元素",
  "guide": {
    "pageElements": {"riskTotal": "metric-imports"},
    "guideSteps": [
      {
        "step": 1,
        "target": "riskTotal",
        "title": "查看风险总数",
        "description": "先确认当前项目的整体风险规模。"
      }
    ]
  }
}
"""


class DeepSeekError(RuntimeError):
    """A classified, safe error that never contains credentials or raw payloads."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_unavailable",
        retryable: bool = False,
        status_code: int | None = None,
        run: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.run = run or {}


class ModelOutputError(ValueError):
    """The model returned data that cannot enter the next project stage."""

    code = "invalid_model_output"

    def __init__(self, message: str, *, run: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.run = run or {}


def find_missing_brief_fields(brief: Any) -> list[tuple[str, str]]:
    """Return clearly missing or empty required fields without spending API credit."""
    if not isinstance(brief, dict):
        return [("brief", "完整的功能 Brief")]

    missing: list[tuple[str, str]] = []
    for field, (expected_type, label) in REQUIRED_BRIEF_FIELDS.items():
        value = brief.get(field)
        if type(value) is not expected_type:
            missing.append((field, label))
        elif isinstance(value, str) and not value.strip():
            missing.append((field, label))
        elif isinstance(value, (list, dict)) and not value:
            missing.append((field, label))
    return missing


def make_local_ask(missing: list[tuple[str, str]]) -> dict[str, Any]:
    """Create a deterministic ASK result for fields that are plainly absent."""
    return {
        "decision": "ASK",
        "reason": "缺少生成引导所需的必填信息",
        "questions": [
            {"field": field, "question": f"请补充{label}。"}
            for field, label in missing
        ],
        "source": "local-precheck",
    }


def build_messages(brief: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "请判断下面的功能 Brief，并按约定输出 json：\n"
            + json.dumps(brief, ensure_ascii=False, indent=2),
        },
    ]


class DeepSeekClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        opener: Callable[..., Any] = urlopen,
        timeout_seconds: float = 20,
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
        budget_policy: BudgetPolicy | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self.opener = opener
        self.provider_name = PROVIDER_NAME
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, min(int(max_retries), 3))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.sleeper = sleeper
        self.budget_policy = budget_policy or BudgetPolicy()
        self.last_usage: dict[str, int] = {}
        self.last_run: dict[str, Any] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def _run_metadata(self, run_id: str, started: float, attempts: int, status: str, error_code: str | None = None) -> dict[str, Any]:
        usage = dict(self.last_usage)
        return {
            "run_id": run_id,
            "provider": self.provider_name,
            "model": self.model,
            "client_protocol_version": CLIENT_PROTOCOL_VERSION,
            "status": status,
            "error_code": error_code,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "attempts": attempts,
            "retry_count": max(0, attempts - 1),
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "cost": None,
            "cost_status": "not_provided_by_provider",
        }

    def create_json(self, messages: list[dict[str, str]], *, batch_budget: BatchBudget | None = None) -> str:
        run_id = f"model-run-{uuid4().hex[:12]}"
        started = time.perf_counter()
        self.last_usage = {}
        if not self.is_configured:
            self.last_run = self._run_metadata(run_id, started, 0, "failed", "provider_unavailable")
            raise DeepSeekError(
                "未配置 DeepSeek，未进行真实 API 调用；规则结果和人工处理仍可使用",
                code="provider_unavailable",
                run=self.last_run,
            )

        estimated_input = estimate_message_tokens(messages)
        output_limit = self.budget_policy.max_output_tokens
        if estimated_input > self.budget_policy.max_input_tokens or estimated_input + output_limit > self.budget_policy.max_total_tokens:
            self.last_run = self._run_metadata(run_id, started, 0, "blocked", "over_budget")
            self.last_run["estimated_input_tokens"] = estimated_input
            raise DeepSeekError("单次模型调用超过 Token 预算，未发送请求", code="over_budget", run=self.last_run)
        try:
            if batch_budget is not None:
                batch_budget.reserve(estimated_input, output_limit)
        except BudgetExceededError as error:
            self.last_run = self._run_metadata(run_id, started, 0, "blocked", "over_budget")
            raise DeepSeekError(str(error) + "，未发送请求", code="over_budget", run=self.last_run) from error

        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": output_limit,
            "stream": False,
        }
        request = Request(
            API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        attempts = 0
        envelope: dict[str, Any] | None = None
        while attempts <= self.max_retries:
            attempts += 1
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    decoded = json.loads(response.read().decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise json.JSONDecodeError("top-level response must be an object", "", 0)
                envelope = decoded
                break
            except HTTPError as error:
                error_map = {
                    400: ("请求格式不正确", "invalid_request", False),
                    401: ("API 密钥无效", "invalid_auth", False),
                    402: ("DeepSeek 账户余额不足", "insufficient_balance", False),
                    422: ("请求参数不正确", "invalid_request", False),
                    429: ("请求过快，请稍后重试", "rate_limited", True),
                    500: ("DeepSeek 服务暂时出错", "provider_unavailable", True),
                    503: ("DeepSeek 服务繁忙，请稍后重试", "provider_unavailable", True),
                }
                detail, code, retryable = error_map.get(error.code, ("DeepSeek 请求失败", "provider_unavailable", False))
                if retryable and attempts <= self.max_retries:
                    self.sleeper(self.backoff_seconds * (2 ** (attempts - 1)))
                    continue
                self.last_run = self._run_metadata(run_id, started, attempts, "failed", code)
                raise DeepSeekError(f"{detail}（HTTP {error.code}）", code=code, retryable=retryable, status_code=error.code, run=self.last_run) from error
            except (TimeoutError, URLError) as error:
                code = "timeout" if isinstance(error, TimeoutError) else "provider_unavailable"
                detail = "DeepSeek 请求超时" if code == "timeout" else "无法连接 DeepSeek，请检查网络后重试"
                if attempts <= self.max_retries:
                    self.sleeper(self.backoff_seconds * (2 ** (attempts - 1)))
                    continue
                self.last_run = self._run_metadata(run_id, started, attempts, "failed", code)
                raise DeepSeekError(detail, code=code, retryable=True, run=self.last_run) from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                self.last_run = self._run_metadata(run_id, started, attempts, "failed", "invalid_response")
                raise DeepSeekError("DeepSeek 返回了无法读取的响应", code="invalid_response", run=self.last_run) from error

        if envelope is None:
            self.last_run = self._run_metadata(run_id, started, attempts, "failed", "provider_unavailable")
            raise DeepSeekError("DeepSeek 请求未完成", code="provider_unavailable", run=self.last_run)

        try:
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            self.last_run = self._run_metadata(run_id, started, attempts, "failed", "invalid_response")
            raise DeepSeekError("DeepSeek 响应缺少模型输出内容", code="invalid_response", run=self.last_run) from error
        if not isinstance(content, str) or not content.strip():
            self.last_run = self._run_metadata(run_id, started, attempts, "failed", "invalid_response")
            raise DeepSeekError("DeepSeek 返回了空内容，请调整提示词后重试", code="invalid_response", run=self.last_run)
        usage = envelope.get("usage", {})
        if isinstance(usage, dict):
            self.last_usage = {
                key: value
                for key, value in usage.items()
                if isinstance(key, str) and type(value) is int
            }
        actual_total = self.last_usage.get("total_tokens")
        if actual_total is not None and actual_total > self.budget_policy.max_total_tokens:
            self.last_run = self._run_metadata(run_id, started, attempts, "failed", "over_budget")
            raise DeepSeekError("DeepSeek 返回的 Token 用量超过单次预算，结果已拒绝", code="over_budget", run=self.last_run)
        self.last_run = self._run_metadata(run_id, started, attempts, "succeeded")
        self.last_run["estimated_input_tokens"] = estimated_input
        return content


def parse_model_json(content: str) -> dict[str, Any]:
    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise ModelOutputError(
            f"模型输出不是合法 JSON：第 {error.lineno} 行，第 {error.colno} 列"
        ) from error
    if not isinstance(result, dict):
        raise ModelOutputError("模型输出顶层必须是对象")
    return result


def validate_ask_build_result(
    result: dict[str, Any], brief: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    decision = result.get("decision")
    reason = result.get("reason")
    if decision not in {"ASK", "BUILD"}:
        errors.append("decision 必须是 ASK 或 BUILD")
    if not isinstance(reason, str) or not reason.strip():
        errors.append("reason 必须是非空文字")

    if decision == "ASK":
        questions = result.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append("ASK 必须包含非空 questions 列表")
        else:
            fields: list[str] = []
            for index, question in enumerate(questions):
                location = f"questions[{index}]"
                if not isinstance(question, dict):
                    errors.append(f"{location} 必须是对象")
                    continue
                field = question.get("field")
                text = question.get("question")
                if not isinstance(field, str) or not field.strip():
                    errors.append(f"{location}.field 必须是非空文字")
                else:
                    fields.append(field)
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"{location}.question 必须是非空文字")
            if len(fields) != len(set(fields)):
                errors.append("ASK 不应重复询问同一字段")

    if decision == "BUILD":
        guide = result.get("guide")
        if not isinstance(guide, dict):
            errors.append("BUILD 必须包含 guide 对象")
        else:
            if guide.get("pageElements") != brief.get("pageElements"):
                errors.append("BUILD.pageElements 必须与输入完全一致，不得虚构页面元素")
            html_ids, html_errors = collect_html_ids(HTML_FILE)
            errors.extend(html_errors)
            errors.extend(validate_guide_data(guide, html_ids))
    return errors


def evaluate_brief(
    brief: Any, client: DeepSeekClient | Any | None = None
) -> dict[str, Any]:
    missing = find_missing_brief_fields(brief)
    if missing:
        return make_local_ask(missing)

    active_client = client or DeepSeekClient()
    content = active_client.create_json(build_messages(brief))
    result = parse_model_json(content)
    errors = validate_ask_build_result(result, brief)
    if errors:
        raise ModelOutputError("模型输出未通过校验：\n- " + "\n- ".join(errors))
    result["source"] = "deepseek-api"
    result["model"] = active_client.model
    usage = getattr(active_client, "last_usage", {})
    if usage:
        result["usage"] = usage
    return result


def load_brief(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"找不到 Brief 文件：{path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Brief 不是合法 JSON：第 {error.lineno} 行，第 {error.colno} 列"
        ) from error


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 SaaSGuide ASK / BUILD 结果")
    parser.add_argument("brief", type=Path, help="UTF-8 JSON 格式的功能 Brief")
    args = parser.parse_args()

    try:
        result = evaluate_brief(load_brief(args.brief))
    except (ValueError, DeepSeekError, ModelOutputError) as error:
        print(f"处理失败：{error}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
