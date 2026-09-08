"""DeepSeek-backed risk analysis for the SaaSGuide dashboard."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from deepseek_ask_build import DeepSeekClient, ModelOutputError, parse_model_json


REQUIRED_RISK_FIELDS = {
    "id": "风险编号",
    "title": "风险标题",
    "description": "风险描述",
    "level": "当前风险等级",
    "impact": "影响范围",
    "status": "当前状态",
    "owner": "责任人",
    "due": "截止日期",
}

ALLOWED_LEVELS = {"高风险", "中风险", "低风险"}
ALLOWED_PRIORITIES = {"立即处理", "本周处理", "持续观察"}
RISK_PROMPT_VERSION = "legacy-risk-prompt-v3.1"
RISK_OUTPUT_PROTOCOL_VERSION = "legacy-risk-ask-plan-v1"

SYSTEM_PROMPT = """你是 SaaSGuide 的项目风险分析助手。只输出一个合法的 json 对象，不要输出 Markdown 或额外文字。

你只能根据输入中的风险资料提出建议，不得编造已发生的事实、真实客户信息或业务结果。你的输出是辅助判断，不能替代项目负责人的确认。

规则：
1. 如果风险描述不足以形成具体建议，返回 ASK，并提出最少且明确的问题。
2. 如果信息足够，返回 PLAN，给出风险摘要、建议等级、处理优先级、判断依据和可验证的行动计划。
3. 不要自动声称风险已经解决，不要替用户修改风险状态。
4. 行动计划必须具体，每一步都要有完成信号。

ASK 的 json 示例：
{
  "decision": "ASK",
  "reason": "缺少具体影响和截止时间",
  "questions": [
    {"field": "impact", "question": "如果问题继续存在，会影响哪个交付节点？"}
  ]
}

PLAN 的 json 示例：
{
  "decision": "PLAN",
  "summary": "接口延期可能阻塞核心功能验收。",
  "suggestedLevel": "高风险",
  "priority": "立即处理",
  "rationale": ["已经发生延期", "影响核心验收节点"],
  "actions": [
    {
      "step": 1,
      "action": "确认供应商可用联调时间并记录阻塞项。",
      "successSignal": "获得明确时间表和责任人。"
    }
  ],
  "cautions": ["建议等级需要项目负责人确认。"]
}
"""


def find_missing_risk_fields(risk: Any) -> list[tuple[str, str]]:
    if not isinstance(risk, dict):
        return [("risk", "完整风险信息")]
    missing: list[tuple[str, str]] = []
    for field, label in REQUIRED_RISK_FIELDS.items():
        value = risk.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append((field, label))
    return missing


def make_local_ask(missing: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "decision": "ASK",
        "reason": "缺少形成风险建议所需的信息",
        "questions": [
            {"field": field, "question": f"请补充{label}。"}
            for field, label in missing
        ],
        "source": "local-precheck",
        "model_status": "not_called",
        "provider": "deepseek",
        "prompt_version": RISK_PROMPT_VERSION,
        "protocol_version": RISK_OUTPUT_PROTOCOL_VERSION,
    }


def build_risk_messages(risk: dict[str, Any], context_note: str = "") -> list[dict[str, str]]:
    input_data = {
        "analysisDate": date.today().isoformat(),
        "risk": risk,
        "additionalContext": context_note.strip(),
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "请分析下面的虚构项目风险，并按约定输出 json：\n"
            + json.dumps(input_data, ensure_ascii=False, indent=2),
        },
    ]


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_text_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty_text(item) for item in value)


def validate_risk_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decision = result.get("decision")
    if decision not in {"ASK", "PLAN"}:
        return ["decision 必须是 ASK 或 PLAN"]

    if decision == "ASK":
        if set(result) != {"decision", "reason", "questions"}:
            errors.append("ASK 只能包含 decision、reason 和 questions")
        if not _nonempty_text(result.get("reason")):
            errors.append("ASK.reason 必须是非空文字")
        questions = result.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append("ASK.questions 必须是非空列表")
        else:
            fields: list[str] = []
            for index, question in enumerate(questions):
                location = f"questions[{index}]"
                if not isinstance(question, dict):
                    errors.append(f"{location} 必须是对象")
                    continue
                if set(question) != {"field", "question"}:
                    errors.append(f"{location} 只能包含 field 和 question")
                if not _nonempty_text(question.get("field")):
                    errors.append(f"{location}.field 必须是非空文字")
                else:
                    fields.append(question["field"])
                if not _nonempty_text(question.get("question")):
                    errors.append(f"{location}.question 必须是非空文字")
            if len(fields) != len(set(fields)):
                errors.append("ASK 不应重复询问同一字段")
        return errors

    plan_fields = {"decision", "summary", "suggestedLevel", "priority", "rationale", "actions", "cautions"}
    if set(result) != plan_fields:
        errors.append("PLAN 字段必须严格符合输出协议")
    if not _nonempty_text(result.get("summary")):
        errors.append("PLAN.summary 必须是非空文字")
    if result.get("suggestedLevel") not in ALLOWED_LEVELS:
        errors.append("PLAN.suggestedLevel 必须是高风险、中风险或低风险")
    if result.get("priority") not in ALLOWED_PRIORITIES:
        errors.append("PLAN.priority 必须是立即处理、本周处理或持续观察")
    if not _valid_text_list(result.get("rationale")):
        errors.append("PLAN.rationale 必须是非空文字列表")
    if not _valid_text_list(result.get("cautions")):
        errors.append("PLAN.cautions 必须是非空文字列表")

    actions = result.get("actions")
    if not isinstance(actions, list) or not actions:
        errors.append("PLAN.actions 必须是非空列表")
    else:
        steps: list[int] = []
        for index, action in enumerate(actions):
            location = f"actions[{index}]"
            if not isinstance(action, dict):
                errors.append(f"{location} 必须是对象")
                continue
            if set(action) != {"step", "action", "successSignal"}:
                errors.append(f"{location} 只能包含 step、action 和 successSignal")
            step = action.get("step")
            if type(step) is int:
                steps.append(step)
            else:
                errors.append(f"{location}.step 必须是整数")
            if not _nonempty_text(action.get("action")):
                errors.append(f"{location}.action 必须是非空文字")
            if not _nonempty_text(action.get("successSignal")):
                errors.append(f"{location}.successSignal 必须是非空文字")
        expected = list(range(1, len(actions) + 1))
        if steps != expected:
            errors.append(f"PLAN.actions 步骤顺序错误，当前为 {steps}，应为 {expected}")
    return errors


def analyze_risk(
    risk: Any,
    context_note: str = "",
    client: DeepSeekClient | Any | None = None,
) -> dict[str, Any]:
    missing = find_missing_risk_fields(risk)
    if missing:
        return make_local_ask(missing)

    active_client = client or DeepSeekClient()
    content = active_client.create_json(build_risk_messages(risk, context_note))
    result = parse_model_json(content)
    errors = validate_risk_result(result)
    if errors:
        raise ModelOutputError("风险分析结果未通过校验：\n- " + "\n- ".join(errors))
    result["source"] = "deepseek-api"
    result["model"] = active_client.model
    result["provider"] = getattr(active_client, "provider_name", "deepseek")
    result["prompt_version"] = RISK_PROMPT_VERSION
    result["protocol_version"] = RISK_OUTPUT_PROTOCOL_VERSION
    usage = getattr(active_client, "last_usage", {})
    if usage:
        result["usage"] = usage
    telemetry = getattr(active_client, "last_run", {})
    if telemetry:
        result["telemetry"] = telemetry
    return result
