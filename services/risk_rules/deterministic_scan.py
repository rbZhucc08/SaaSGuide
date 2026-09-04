"""Generate evidence-backed risk candidates using deterministic rules only."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


FINAL_STATUSES = {"已完成", "已取消"}
ALLOWED_DECISIONS = {"confirm", "watch", "reject", "false_positive"}
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

RULES = {
    "overdue_incomplete": "截止日期早于扫描日，且任务未完成或取消",
    "overdue_low_progress": "任务已逾期，完成度仍低于 80%",
    "blocked_task": "任务状态明确标记为阻塞",
    "due_soon_low_progress": "任务将在 3 天内到期，完成度低于 50%",
    "direct_blocked_dependency": "任务的直接前置任务处于阻塞状态",
}


class RiskScanError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _parse_date(value: Any, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as error:
        raise RiskScanError("invalid_scan_date", f"{label}必须是 YYYY-MM-DD 日期") from error


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def candidate_id_for(source_id: str, candidate_key: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{candidate_key}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-{digest}"


def _evidence(field: str, label: str, value: Any, task: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": field,
        "label": label,
        "value": value,
        "source_row": task.get("source_row"),
    }


def _upsert_candidate(
    candidates: dict[str, dict[str, Any]],
    *,
    source_id: str,
    project_id: str,
    project_name: str,
    task: dict[str, Any],
    risk_type: str,
    title: str,
    severity: str,
    rule_id: str,
    evidence: list[dict[str, Any]],
) -> None:
    candidate_key = f"{project_id}:{task['task_id']}:{risk_type}"
    candidate = candidates.get(candidate_key)
    if candidate is None:
        candidate = {
            "candidate_id": candidate_id_for(source_id, candidate_key),
            "candidate_key": candidate_key,
            "project_id": project_id,
            "project_name": project_name,
            "task_id": task["task_id"],
            "task_name": task.get("task_name", ""),
            "owner": task.get("owner", ""),
            "risk_type": risk_type,
            "title": title,
            "severity": severity,
            "status": "candidate",
            "confidence": "deterministic_rule_match",
            "trigger_rules": [],
            "evidence": [],
        }
        candidates[candidate_key] = candidate
    elif SEVERITY_ORDER[severity] > SEVERITY_ORDER[candidate["severity"]]:
        candidate["severity"] = severity

    if rule_id not in candidate["trigger_rules"]:
        candidate["trigger_rules"].append(rule_id)
    existing = {
        (item["field"], json.dumps(item["value"], ensure_ascii=False, sort_keys=True), item.get("source_row"))
        for item in candidate["evidence"]
    }
    for item in evidence:
        identity = (item["field"], json.dumps(item["value"], ensure_ascii=False, sort_keys=True), item.get("source_row"))
        if identity not in existing:
            candidate["evidence"].append(item)
            existing.add(identity)


def scan_project(document: dict[str, Any], as_of: str | date | None = None) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise RiskScanError("invalid_project_data", "统一项目数据必须是 JSON 对象")
    project = document.get("project")
    tasks = document.get("tasks")
    source = document.get("source")
    if not isinstance(project, dict) or not project.get("project_id") or not project.get("project_name"):
        raise RiskScanError("invalid_project_data", "统一项目数据缺少 project_id 或 project_name")
    if not isinstance(tasks, list) or not tasks:
        raise RiskScanError("invalid_project_data", "统一项目数据必须包含非空 tasks 列表")
    if not isinstance(source, dict):
        source = {}

    scan_date = _parse_date(as_of or document.get("as_of") or date.today(), "扫描日期")
    project_id = str(project["project_id"])
    project_name = str(project["project_name"])
    source_id = str(source.get("source_id") or source.get("sha256") or "source-unknown")
    task_by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict) or not task.get("task_id") or not task.get("due_date"):
            raise RiskScanError("invalid_project_data", "每条任务必须包含 task_id 和 due_date")
        task_id = str(task["task_id"])
        if task_id in task_by_id:
            raise RiskScanError("duplicate_task_id", f"任务编号“{task_id}”重复")
        _parse_date(task["due_date"], f"任务 {task_id} 的截止日期")
        task_by_id[task_id] = task

    candidates: dict[str, dict[str, Any]] = {}
    for task in tasks:
        status = str(task.get("status") or "")
        if status in FINAL_STATUSES:
            continue
        due_date = _parse_date(task["due_date"], f"任务 {task['task_id']} 的截止日期")
        days_to_due = (due_date - scan_date).days
        progress = _number(task.get("progress_percent"))

        if days_to_due < 0:
            common_evidence = [
                _evidence("due_date", "截止日期", due_date.isoformat(), task),
                _evidence("status", "状态", status, task),
                _evidence("days_overdue", "逾期天数", abs(days_to_due), task),
            ]
            _upsert_candidate(
                candidates,
                source_id=source_id,
                project_id=project_id,
                project_name=project_name,
                task=task,
                risk_type="schedule_delay",
                title=f"{task.get('task_name', task['task_id'])} 已逾期",
                severity="high",
                rule_id="overdue_incomplete",
                evidence=common_evidence,
            )
            if progress < 80:
                _upsert_candidate(
                    candidates,
                    source_id=source_id,
                    project_id=project_id,
                    project_name=project_name,
                    task=task,
                    risk_type="schedule_delay",
                    title=f"{task.get('task_name', task['task_id'])} 已逾期",
                    severity="high",
                    rule_id="overdue_low_progress",
                    evidence=[_evidence("progress_percent", "完成百分比", progress, task)],
                )

        if status == "阻塞":
            _upsert_candidate(
                candidates,
                source_id=source_id,
                project_id=project_id,
                project_name=project_name,
                task=task,
                risk_type="delivery_blocked",
                title=f"{task.get('task_name', task['task_id'])} 处于阻塞状态",
                severity="high",
                rule_id="blocked_task",
                evidence=[_evidence("status", "状态", status, task)],
            )

        if 0 <= days_to_due <= 3 and progress < 50:
            _upsert_candidate(
                candidates,
                source_id=source_id,
                project_id=project_id,
                project_name=project_name,
                task=task,
                risk_type="schedule_pressure",
                title=f"{task.get('task_name', task['task_id'])} 临近截止且进度偏低",
                severity="medium",
                rule_id="due_soon_low_progress",
                evidence=[
                    _evidence("due_date", "截止日期", due_date.isoformat(), task),
                    _evidence("days_to_due", "距离截止天数", days_to_due, task),
                    _evidence("progress_percent", "完成百分比", progress, task),
                ],
            )

        dependency_ids = task.get("dependency_ids") or []
        if not isinstance(dependency_ids, list):
            raise RiskScanError("invalid_project_data", f"任务 {task['task_id']} 的 dependency_ids 必须是列表")
        blocked_dependencies = [
            dependency_id
            for dependency_id in dependency_ids
            if dependency_id in task_by_id and task_by_id[dependency_id].get("status") == "阻塞"
        ]
        if blocked_dependencies:
            _upsert_candidate(
                candidates,
                source_id=source_id,
                project_id=project_id,
                project_name=project_name,
                task=task,
                risk_type="dependency_risk",
                title=f"{task.get('task_name', task['task_id'])} 受阻塞依赖影响",
                severity="high",
                rule_id="direct_blocked_dependency",
                evidence=[
                    _evidence("dependency_ids", "阻塞的直接前置任务", blocked_dependencies, task)
                ],
            )

    ordered = sorted(
        candidates.values(),
        key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["task_id"], item["risk_type"]),
    )
    return {
        "scan_version": "v2-p2-rules-v1",
        "as_of": scan_date.isoformat(),
        "source": {
            "source_id": source_id,
            "source_name": source.get("source_name", "unknown"),
            "sha256": source.get("sha256"),
        },
        "project": {"project_id": project_id, "project_name": project_name},
        "rules": [{"rule_id": rule_id, "description": description} for rule_id, description in RULES.items()],
        "candidates": ordered,
        "summary": {
            "candidate_count": len(ordered),
            "high_count": sum(item["severity"] == "high" for item in ordered),
            "medium_count": sum(item["severity"] == "medium" for item in ordered),
            "rule_hit_count": sum(len(item["trigger_rules"]) for item in ordered),
        },
    }


def evaluate_candidates(candidates: list[dict[str, Any]], expected: dict[str, Any]) -> dict[str, Any]:
    predicted = {item["candidate_key"] for item in candidates}
    positives = set(expected.get("positive_candidate_keys") or [])
    known_negatives = set(expected.get("negative_candidate_keys") or [])
    true_positive_keys = sorted(predicted & positives)
    false_positive_keys = sorted(predicted & known_negatives)
    false_negative_keys = sorted(positives - predicted)
    true_negative_keys = sorted(known_negatives - predicted)
    unassessed_predicted_keys = sorted(predicted - positives - known_negatives)
    tp, fp, fn, tn = map(len, (true_positive_keys, false_positive_keys, false_negative_keys, true_negative_keys))
    precision = tp / (tp + fp) * 100 if tp + fp else 0.0
    recall = tp / (tp + fn) * 100 if tp + fn else 0.0
    false_positive_rate = fp / (fp + tn) * 100 if fp + tn else 0.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision_percent": round(precision, 2),
        "recall_percent": round(recall, 2),
        "false_positive_rate_percent": round(false_positive_rate, 2),
        "true_positive_keys": true_positive_keys,
        "false_positive_keys": false_positive_keys,
        "false_negative_keys": false_negative_keys,
        "true_negative_keys": true_negative_keys,
        "unassessed_predicted_keys": unassessed_predicted_keys,
        "scope_note": "指标只适用于固定模拟评测集，不能推导真实企业表现。",
    }


def save_human_decision(
    decision_path: Path,
    payload: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    candidate_id = str(payload.get("candidate_id") or "")
    candidate_key = str(payload.get("candidate_key") or "")
    source_id = str(payload.get("source_id") or "")
    decision = str(payload.get("decision") or "")
    note = payload.get("note", "")
    if not re.fullmatch(r"candidate-[0-9a-f]{16}", candidate_id):
        raise RiskScanError("invalid_candidate_id", "候选风险 ID 无效")
    if not candidate_key or len(candidate_key) > 200 or not source_id or len(source_id) > 120:
        raise RiskScanError("invalid_candidate_reference", "候选风险缺少有效的来源或去重键")
    if candidate_id != candidate_id_for(source_id, candidate_key):
        raise RiskScanError("candidate_reference_mismatch", "候选风险 ID 与来源记录不一致")
    if decision not in ALLOWED_DECISIONS:
        raise RiskScanError("invalid_decision", "人工选择必须是确认、观察、驳回或标记误报")
    if not isinstance(note, str) or len(note.strip()) > 500:
        raise RiskScanError("invalid_decision_note", "人工说明必须是不超过 500 字的文字")
    record = {
        "candidate_id": candidate_id,
        "candidate_key": candidate_key,
        "decision": decision,
        "note": note.strip(),
        "source_id": source_id,
        "recorded_at": recorded_at or datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    with decision_path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
