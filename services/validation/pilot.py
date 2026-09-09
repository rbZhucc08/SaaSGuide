"""Validate and summarize de-identified evidence from a small external pilot."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "saasguide-pilot-v1"
SCENARIO_ID = "risk-to-action-review"
DECISIONS = {"accepted", "modified", "rejected"}
REASON_CATEGORIES = {
    "useful_as_written", "needs_context", "wrong_priority", "not_actionable",
    "unsupported_by_evidence", "outside_role", "other_coded_reason",
}
FORBIDDEN_IDENTITY_KEYS = {
    "name", "real_name", "email", "phone", "mobile", "company",
    "company_name", "organization", "address", "account_id",
}


class PilotValidationError(ValueError):
    """Raised when a pilot evidence file cannot support trustworthy analysis."""


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise PilotValidationError(f"{field} 必须是非负数字")
    return float(value)


def _find_identity_key(value: Any, path: str = "root") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_IDENTITY_KEYS:
                return f"{path}.{key}"
            found = _find_identity_key(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_identity_key(child, f"{path}[{index}]")
            if found:
                return found
    return None


def analyze_study(document: dict[str, Any]) -> dict[str, Any]:
    """Return descriptive pilot metrics without claiming causal business impact."""
    if not isinstance(document, dict):
        raise PilotValidationError("试点证据必须是 JSON 对象")
    identity_key = _find_identity_key(document)
    if identity_key:
        raise PilotValidationError(f"结构化证据包含禁止的身份字段：{identity_key}")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise PilotValidationError(f"schema_version 必须是 {SCHEMA_VERSION}")
    if document.get("scenario_id") != SCENARIO_ID:
        raise PilotValidationError(f"scenario_id 必须是 {SCENARIO_ID}")
    authorization = document.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("authorized") is not True:
        raise PilotValidationError("必须确认数据已获授权")
    if authorization.get("deidentified") is not True:
        raise PilotValidationError("必须确认结构化数据已去标识化")
    if authorization.get("confirmed_by_project_owner") is not True:
        raise PilotValidationError("必须由项目所有者确认授权范围")
    participants = document.get("participants")
    if not isinstance(participants, list) or not participants:
        raise PilotValidationError("至少需要一位真实参与者的记录")

    ids: set[str] = set()
    baseline_minutes: list[float] = []
    trial_minutes: list[float] = []
    counts = {decision: 0 for decision in sorted(DECISIONS)}
    for index, participant in enumerate(participants):
        prefix = f"participants[{index}]"
        if not isinstance(participant, dict):
            raise PilotValidationError(f"{prefix} 必须是对象")
        participant_id = participant.get("participant_id")
        if not isinstance(participant_id, str) or not participant_id.startswith("participant-"):
            raise PilotValidationError(f"{prefix}.participant_id 必须使用 participant- 开头的化名编号")
        if participant_id in ids:
            raise PilotValidationError("participant_id 不得重复")
        ids.add(participant_id)
        if participant.get("consent_confirmed") is not True:
            raise PilotValidationError(f"{prefix} 缺少参与同意确认")
        if not isinstance(participant.get("role_category"), str) or not participant["role_category"].strip():
            raise PilotValidationError(f"{prefix}.role_category 必须填写角色类别")
        baseline = participant.get("baseline")
        trial = participant.get("trial")
        if not isinstance(baseline, dict) or not isinstance(trial, dict):
            raise PilotValidationError(f"{prefix} 缺少 baseline 或 trial")
        baseline_minutes.append(_require_number(baseline.get("task_minutes"), f"{prefix}.baseline.task_minutes"))
        trial_minutes.append(_require_number(trial.get("task_minutes"), f"{prefix}.trial.task_minutes"))
        decisions = participant.get("recommendation_decisions")
        if not isinstance(decisions, list) or not decisions:
            raise PilotValidationError(f"{prefix} 至少需要一条建议处置记录")
        for item_index, item in enumerate(decisions):
            if not isinstance(item, dict) or item.get("decision") not in DECISIONS:
                raise PilotValidationError(f"{prefix}.recommendation_decisions[{item_index}] 的 decision 无效")
            if item.get("reason_category") not in REASON_CATEGORIES:
                raise PilotValidationError(f"{prefix}.recommendation_decisions[{item_index}] 的 reason_category 无效")
            counts[item["decision"]] += 1

    total = sum(counts.values())
    baseline_median = statistics.median(baseline_minutes)
    trial_median = statistics.median(trial_minutes)
    return {
        "status": "pilot_evidence_available",
        "schema_version": SCHEMA_VERSION,
        "scenario_id": SCENARIO_ID,
        "participant_count": len(participants),
        "recommendation_decisions": {**counts, "total": total},
        "acceptance_rate": round(counts["accepted"] / total, 4),
        "median_task_minutes": {
            "baseline": baseline_median,
            "trial": trial_median,
            "observed_difference": round(trial_median - baseline_median, 2),
        },
        "interpretation": "描述性小样本观察；不证明因果关系、总体效果、商业价值或生产可用性。",
    }


def status_from_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "external_evidence_required",
            "scenario_id": SCENARIO_ID,
            "participant_count": 0,
            "required": ["真实目标用户", "参与同意", "授权且去标识化的数据", "基线记录", "建议接受、修改和拒绝记录"],
            "message": "本地验证工具已就绪，尚无可分析的真实试点证据。",
        }
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        return analyze_study(document)
    except (OSError, json.JSONDecodeError, PilotValidationError) as error:
        return {
            "status": "evidence_invalid",
            "scenario_id": SCENARIO_ID,
            "participant_count": 0,
            "message": str(error),
        }
