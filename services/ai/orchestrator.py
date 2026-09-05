"""One bounded Orchestrator Agent for evidence-grounded V2 risk assessment."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from deepseek_ask_build import DeepSeekClient, ModelOutputError, parse_model_json
from services.ai.skills import retrieve_candidate_evidence


ALLOWED_LEVELS = {"高风险", "中风险", "低风险"}
ALLOWED_PRIORITIES = {"立即处理", "本周处理", "持续观察"}

SYSTEM_PROMPT = """你是 SaaSGuide V2 的受控协调智能体。只输出一个合法 JSON 对象，不要输出 Markdown。

你收到的是确定性规则生成的候选风险、原始字段证据和程序检索出的知识引用。你不能编造事实、引用、真实客户或业务结果，也不能修改任务、风险状态、负责人和截止日期。

你的当前 Workflow：
1. risk-signal-scan 已由 Python 完成。
2. evidence-grounded-assessment 已由程序完成，只能使用 suppliedCitations 中的 citation_id。
3. 你负责 risk-action-planner：信息不足则返回 ASK；信息足够则返回精简 PLAN 草稿，行动不超过 3 条。
4. PLAN 仍需用户人工确认，不能表示行动已经执行。

ASK 格式：
{"decision":"ASK","reason":"...","questions":[{"field":"...","question":"..."}]}

PLAN 格式：
{"decision":"PLAN","summary":"...","suggestedLevel":"高风险|中风险|低风险","priority":"立即处理|本周处理|持续观察","rationale":["..."],"citationIds":["只能使用提供的 citation_id"],"actions":[{"step":1,"action":"...","ownerRole":"...","successSignal":"..."}],"cautions":["..."]}
"""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _missing_candidate_fields(candidate: Any) -> list[str]:
    if not isinstance(candidate, dict):
        return ["candidate"]
    missing = [field for field in ("candidate_id", "title", "task_id", "task_name", "risk_type", "severity") if not _text(candidate.get(field))]
    if not isinstance(candidate.get("trigger_rules"), list) or not candidate["trigger_rules"]:
        missing.append("trigger_rules")
    if not isinstance(candidate.get("evidence"), list) or not candidate["evidence"]:
        missing.append("evidence")
    return missing


def _local_ask(missing: list[str], run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "decision": "ASK",
        "reason": "候选风险缺少进入 AI 研判所需的可核对信息",
        "questions": [{"field": field, "question": f"请补充或重新生成 {field}。"} for field in missing],
        "source": "local-precheck",
        "model_status": "not_called",
        "trace": [{"skill": "risk-signal-scan", "status": "blocked", "detail": "candidate input incomplete"}],
    }


def build_messages(candidate: dict[str, Any], project: dict[str, Any], source: dict[str, Any], context_note: str, citations: list[dict[str, str]]) -> list[dict[str, str]]:
    payload = {
        "project": project,
        "source": {"source_id": source.get("source_id"), "source_name": source.get("source_name")},
        "candidate": candidate,
        "additionalContext": context_note.strip(),
        "suppliedCitations": citations,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "请按受控 Workflow 研判以下虚构项目候选风险：\n" + json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def validate_agent_result(result: dict[str, Any], citations: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    decision = result.get("decision")
    if decision not in {"ASK", "PLAN"}:
        return ["decision 必须是 ASK 或 PLAN"]
    if decision == "ASK":
        if not _text(result.get("reason")):
            errors.append("ASK.reason 必须是非空文字")
        questions = result.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append("ASK.questions 必须是非空列表")
        elif any(not isinstance(item, dict) or not _text(item.get("field")) or not _text(item.get("question")) for item in questions):
            errors.append("每个 ASK 问题必须包含 field 和 question")
        return errors

    if not citations:
        errors.append("没有知识引用时不能返回 PLAN")
    if not _text(result.get("summary")):
        errors.append("PLAN.summary 必须是非空文字")
    if result.get("suggestedLevel") not in ALLOWED_LEVELS:
        errors.append("PLAN.suggestedLevel 不在允许范围")
    if result.get("priority") not in ALLOWED_PRIORITIES:
        errors.append("PLAN.priority 不在允许范围")
    for field in ("rationale", "cautions"):
        value = result.get(field)
        if not isinstance(value, list) or not value or any(not _text(item) for item in value):
            errors.append(f"PLAN.{field} 必须是非空文字列表")
    allowed_citations = {item["citation_id"] for item in citations}
    citation_ids = result.get("citationIds")
    if not isinstance(citation_ids, list) or not citation_ids:
        errors.append("PLAN.citationIds 必须引用至少一条提供的依据")
    elif any(item not in allowed_citations for item in citation_ids):
        errors.append("PLAN 引用了未提供的文档")
    actions = result.get("actions")
    if not isinstance(actions, list) or not actions or len(actions) > 3:
        errors.append("PLAN.actions 必须包含 1 至 3 条行动")
    else:
        steps: list[int] = []
        for item in actions:
            if not isinstance(item, dict):
                errors.append("PLAN.actions 中的项目必须是对象")
                continue
            if type(item.get("step")) is int:
                steps.append(item["step"])
            if not all(_text(item.get(field)) for field in ("action", "ownerRole", "successSignal")):
                errors.append("每条行动必须包含 action、ownerRole 和 successSignal")
        if steps != list(range(1, len(actions) + 1)):
            errors.append("PLAN.actions 步骤必须从 1 连续编号")
    return errors


def orchestrate_risk_candidate(
    candidate: Any,
    project: Any,
    source: Any,
    context_note: str,
    knowledge_path: Path,
    client: DeepSeekClient | Any | None = None,
) -> dict[str, Any]:
    """Run deterministic skills, then let DeepSeek choose ASK or PLAN."""
    run_id = f"ai-run-{uuid4().hex[:12]}"
    missing = _missing_candidate_fields(candidate)
    if missing:
        return _local_ask(missing, run_id)
    if not isinstance(project, dict) or not isinstance(source, dict):
        return _local_ask(["project", "source"], run_id)

    citations = retrieve_candidate_evidence(candidate, knowledge_path)
    trace = [
        {"skill": "risk-signal-scan", "status": "completed", "detail": f"{len(candidate['trigger_rules'])} rule hit(s) supplied"},
        {"skill": "evidence-grounded-assessment", "status": "completed" if citations else "insufficient", "detail": f"{len(citations)} effective citation(s) retrieved"},
    ]
    active_client = client or DeepSeekClient()
    content = active_client.create_json(build_messages(candidate, project, source, str(context_note or "")[:1000], citations))
    result = parse_model_json(content)
    errors = validate_agent_result(result, citations)
    if errors:
        raise ModelOutputError("V2 Agent 输出未通过校验：\n- " + "\n- ".join(errors))
    result.update(
        {
            "run_id": run_id,
            "source": "deepseek-api",
            "model": active_client.model,
            "model_status": "called",
            "citations": citations,
            "trace": trace + [{"skill": "risk-action-planner", "status": "completed" if result["decision"] == "PLAN" else "needs_information", "detail": f"DeepSeek returned {result['decision']}"}],
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
    )
    usage = getattr(active_client, "last_usage", {})
    if usage:
        result["usage"] = usage
    return result
