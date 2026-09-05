"""Use DeepSeek to turn a SaaS feature brief into an ASK or BUILD result."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from validate_data import HTML_FILE, collect_html_ids, validate_guide_data


API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"

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
    """A safe, user-facing DeepSeek request error."""


class ModelOutputError(ValueError):
    """The model returned data that cannot enter the next project stage."""


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
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self.opener = opener
        self.last_usage: dict[str, int] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def create_json(self, messages: list[dict[str, str]]) -> str:
        if not self.is_configured:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY，未进行真实 API 调用")

        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": 2000,
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

        try:
            with self.opener(request, timeout=45) as response:
                envelope = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            messages_by_status = {
                400: "请求格式不正确",
                401: "API 密钥无效",
                402: "DeepSeek 账户余额不足",
                422: "请求参数不正确",
                429: "请求过快，请稍后重试",
                500: "DeepSeek 服务暂时出错",
                503: "DeepSeek 服务繁忙，请稍后重试",
            }
            detail = messages_by_status.get(error.code, "DeepSeek 请求失败")
            raise DeepSeekError(f"{detail}（HTTP {error.code}）") from error
        except URLError as error:
            raise DeepSeekError("无法连接 DeepSeek，请检查网络后重试") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeepSeekError("DeepSeek 返回了无法读取的响应") from error

        try:
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise DeepSeekError("DeepSeek 响应缺少模型输出内容") from error
        if not isinstance(content, str) or not content.strip():
            raise DeepSeekError("DeepSeek 返回了空内容，请调整提示词后重试")
        usage = envelope.get("usage", {})
        if isinstance(usage, dict):
            self.last_usage = {
                key: value
                for key, value in usage.items()
                if isinstance(key, str) and type(value) is int
            }
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
