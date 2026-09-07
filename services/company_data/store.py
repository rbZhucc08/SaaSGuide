"""Validated JSON store for editable simulated company projects and policies."""

from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class CompanyDataError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


_LOCK = threading.Lock()
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_PROJECT_FIELDS = ("project_id", "project_name", "department", "stage", "start_date", "end_date", "background", "outcome")
_TASK_FIELDS = ("task_id", "task_name", "owner", "start_date", "due_date", "status", "priority", "progress_percent")
_POLICY_FIELDS = ("document_id", "title", "version", "effective_date", "status", "content")


def _text(value: Any, label: str, maximum: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise CompanyDataError("invalid_field", f"{label}必须是文字")
    result = value.strip()
    if required and not result:
        raise CompanyDataError("missing_field", f"{label}不能为空")
    if len(result) > maximum:
        raise CompanyDataError("field_too_long", f"{label}不能超过 {maximum} 字")
    return result


def _identifier(value: Any, label: str) -> str:
    result = _text(value, label, 80)
    if not _ID_PATTERN.fullmatch(result):
        raise CompanyDataError("invalid_identifier", f"{label}只能包含字母、数字、点、下划线或连字符")
    return result


def _date(value: Any, label: str) -> str:
    result = _text(value, label, 10)
    try:
        date.fromisoformat(result)
    except ValueError as error:
        raise CompanyDataError("invalid_date", f"{label}必须是 YYYY-MM-DD") from error
    return result


def validate_task(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompanyDataError("invalid_task", f"第 {index} 条任务必须是对象")
    progress = value.get("progress_percent")
    if isinstance(progress, bool) or not isinstance(progress, (int, float)) or progress < 0 or progress > 100:
        raise CompanyDataError("invalid_progress", f"第 {index} 条任务完成度必须是 0 到 100")
    dependencies = value.get("dependency_ids", [])
    if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
        raise CompanyDataError("invalid_dependencies", f"第 {index} 条任务的前置任务必须是编号列表")
    task = {
        "task_id": _identifier(value.get("task_id"), f"第 {index} 条任务编号"),
        "task_name": _text(value.get("task_name"), f"第 {index} 条任务名称", 120),
        "owner": _text(value.get("owner"), f"第 {index} 条任务负责人", 60),
        "start_date": _date(value.get("start_date"), f"第 {index} 条任务开始日期"),
        "due_date": _date(value.get("due_date"), f"第 {index} 条任务截止日期"),
        "status": _text(value.get("status"), f"第 {index} 条任务状态", 30),
        "priority": _text(value.get("priority"), f"第 {index} 条任务优先级", 20),
        "dependency_ids": [_identifier(item, f"第 {index} 条任务前置编号") for item in dependencies],
        "progress_percent": int(progress),
        "effort_hours": int(value.get("effort_hours", 0) or 0),
    }
    if task["start_date"] > task["due_date"]:
        raise CompanyDataError("invalid_date_order", f"第 {index} 条任务截止日期不能早于开始日期")
    if task["effort_hours"] < 0 or task["effort_hours"] > 10000:
        raise CompanyDataError("invalid_effort", f"第 {index} 条任务工时无效")
    return task


def validate_project(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompanyDataError("invalid_project", "项目必须是对象")
    project = {
        "project_id": _identifier(value.get("project_id"), "项目编号"),
        "project_name": _text(value.get("project_name"), "项目名称", 120),
        "department": _text(value.get("department"), "所属部门", 60),
        "stage": _text(value.get("stage"), "项目阶段", 40),
        "start_date": _date(value.get("start_date"), "项目开始日期"),
        "end_date": _date(value.get("end_date"), "项目结束日期"),
        "background": _text(value.get("background", ""), "项目背景", 1000, required=False),
        "outcome": _text(value.get("outcome", ""), "项目经历或结果", 1000, required=False),
    }
    if project["start_date"] > project["end_date"]:
        raise CompanyDataError("invalid_project_dates", "项目结束日期不能早于开始日期")
    tasks = value.get("tasks")
    if not isinstance(tasks, list) or len(tasks) > 200:
        raise CompanyDataError("invalid_tasks", "项目任务必须是最多 200 条的列表")
    project["tasks"] = [validate_task(item, index) for index, item in enumerate(tasks, 1)]
    task_ids = [item["task_id"] for item in project["tasks"]]
    if len(task_ids) != len(set(task_ids)):
        raise CompanyDataError("duplicate_task_id", "同一项目内任务编号不能重复")
    known = set(task_ids)
    for item in project["tasks"]:
        if item["task_id"] in item["dependency_ids"] or any(dep not in known for dep in item["dependency_ids"]):
            raise CompanyDataError("invalid_dependency_reference", f"任务 {item['task_id']} 包含无效前置任务")
    return project


def validate_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompanyDataError("invalid_policy", "制度必须是对象")
    status = _text(value.get("status"), "制度状态", 20)
    if status not in {"effective", "superseded", "draft", "retired"}:
        raise CompanyDataError("invalid_policy_status", "制度状态必须是 effective、superseded、draft 或 retired")
    tags = value.get("tags", [])
    if not isinstance(tags, list) or len(tags) > 12:
        raise CompanyDataError("invalid_policy_tags", "制度标签必须是最多 12 项的列表")
    return {
        "document_id": _identifier(value.get("document_id"), "制度编号"),
        "title": _text(value.get("title"), "制度名称", 120),
        "version": _identifier(value.get("version"), "制度版本"),
        "effective_date": _date(value.get("effective_date"), "生效日期"),
        "status": status,
        "tags": [_text(item, "制度标签", 30) for item in tags],
        "content": _text(value.get("content"), "制度正文", 5000),
    }


def validate_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompanyDataError("invalid_company_data", "公司数据必须是对象")
    company = value.get("company") or {}
    if not isinstance(company, dict):
        raise CompanyDataError("invalid_company", "公司资料必须是对象")
    projects = value.get("projects", [])
    policies = value.get("policies", [])
    departments = value.get("departments", [])
    if not isinstance(projects, list) or len(projects) > 50:
        raise CompanyDataError("invalid_projects", "项目必须是最多 50 项的列表")
    if not isinstance(policies, list) or len(policies) > 200:
        raise CompanyDataError("invalid_policies", "制度必须是最多 200 项的列表")
    if not isinstance(departments, list) or len(departments) > 50:
        raise CompanyDataError("invalid_departments", "部门必须是最多 50 项的列表")
    result = {
        "schema_version": "1.0",
        "initialized_at": str(value.get("initialized_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
        "updated_at": str(value.get("updated_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
        "company": {
            "company_id": _identifier(company.get("company_id", "nebula-digital"), "公司编号"),
            "name": _text(company.get("name", "模拟公司"), "公司名称", 120),
            "industry": _text(company.get("industry", "软件服务"), "公司行业", 120),
            "description": _text(company.get("description", ""), "公司说明", 500, required=False),
            "simulated": True,
        },
        "departments": [_text(item, "部门名称", 60) for item in departments],
        "projects": [validate_project(item) for item in projects],
        "policies": [validate_policy(item) for item in policies],
    }
    project_ids = [item["project_id"] for item in result["projects"]]
    policy_ids = [(item["document_id"], item["version"]) for item in result["policies"]]
    if len(project_ids) != len(set(project_ids)):
        raise CompanyDataError("duplicate_project_id", "项目编号不能重复")
    if len(policy_ids) != len(set(policy_ids)):
        raise CompanyDataError("duplicate_policy_version", "同一制度版本不能重复")
    return result


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def initialize(runtime_path: Path, seed_path: Path) -> dict[str, Any]:
    with _LOCK:
        if runtime_path.exists():
            return validate_data(json.loads(runtime_path.read_text(encoding="utf-8")))
        data = validate_data(json.loads(seed_path.read_text(encoding="utf-8")))
        _write(runtime_path, data)
        return data


def read(runtime_path: Path, seed_path: Path) -> dict[str, Any]:
    return initialize(runtime_path, seed_path)


def reset(runtime_path: Path, seed_path: Path) -> dict[str, Any]:
    with _LOCK:
        data = validate_data(json.loads(seed_path.read_text(encoding="utf-8")))
        data["initialized_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        data["updated_at"] = data["initialized_at"]
        _write(runtime_path, data)
        return data


def clear(runtime_path: Path, seed_path: Path) -> dict[str, Any]:
    current = read(runtime_path, seed_path)
    with _LOCK:
        current["projects"] = []
        current["policies"] = []
        current["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        _write(runtime_path, current)
    return current


def _mutate(runtime_path: Path, seed_path: Path, collection: str, value: dict[str, Any] | None, identity: tuple[str, ...], *, operation: str) -> dict[str, Any]:
    current = read(runtime_path, seed_path)
    items = current[collection]
    keys = tuple(str((value or {}).get(key, "")) for key in identity)
    index = next((idx for idx, item in enumerate(items) if tuple(str(item.get(key, "")) for key in identity) == keys), None)
    if operation == "create":
        if index is not None:
            raise CompanyDataError("record_conflict", "相同编号或版本的数据已存在", 409)
        items.append(value)
    elif index is None:
        raise CompanyDataError("record_not_found", "要修改的数据不存在", 404)
    elif operation == "update":
        items[index] = value
    else:
        items.pop(index)
    current["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    validate_data(current)
    with _LOCK:
        _write(runtime_path, current)
    return deepcopy(value) if value is not None else {"deleted": True}


def create_project(runtime_path: Path, seed_path: Path, value: Any) -> dict[str, Any]:
    project = validate_project(value)
    return _mutate(runtime_path, seed_path, "projects", project, ("project_id",), operation="create")


def update_project(runtime_path: Path, seed_path: Path, project_id: str, value: Any) -> dict[str, Any]:
    project = validate_project(value)
    if project["project_id"] != project_id:
        raise CompanyDataError("immutable_identifier", "项目编号不能在编辑时改变")
    return _mutate(runtime_path, seed_path, "projects", project, ("project_id",), operation="update")


def delete_project(runtime_path: Path, seed_path: Path, project_id: str) -> dict[str, Any]:
    return _mutate(runtime_path, seed_path, "projects", {"project_id": project_id}, ("project_id",), operation="delete")


def create_policy(runtime_path: Path, seed_path: Path, value: Any) -> dict[str, Any]:
    policy = validate_policy(value)
    return _mutate(runtime_path, seed_path, "policies", policy, ("document_id", "version"), operation="create")


def update_policy(runtime_path: Path, seed_path: Path, document_id: str, version: str, value: Any) -> dict[str, Any]:
    policy = validate_policy(value)
    if (policy["document_id"], policy["version"]) != (document_id, version):
        raise CompanyDataError("immutable_identifier", "制度编号和版本不能在编辑时改变")
    return _mutate(runtime_path, seed_path, "policies", policy, ("document_id", "version"), operation="update")


def delete_policy(runtime_path: Path, seed_path: Path, document_id: str, version: str) -> dict[str, Any]:
    return _mutate(runtime_path, seed_path, "policies", {"document_id": document_id, "version": version}, ("document_id", "version"), operation="delete")


def project_document(data: dict[str, Any], project_id: str, as_of: str | None = None) -> dict[str, Any]:
    project = next((item for item in data["projects"] if item["project_id"] == project_id), None)
    if project is None:
        raise CompanyDataError("project_not_found", "所选项目不存在", 404)
    stamp = data.get("updated_at") or data.get("initialized_at")
    tasks = [{**item, "source_row": index + 2} for index, item in enumerate(project["tasks"])]
    return {
        "schema_version": "2.0-company-data",
        "as_of": as_of or date.today().isoformat(),
        "source": {"source_id": f"company-{project_id}", "source_type": "editable_json", "source_name": f"{data['company']['name']} · 当前项目档案", "source_version": str(stamp), "sha256": "local-editable-data", "imported_at": stamp},
        "project": {"project_id": project["project_id"], "project_name": project["project_name"]},
        "tasks": tasks,
        "dependencies": [],
        "updates": [],
        "summary": {"task_count": len(tasks), "dependency_count": sum(len(item["dependency_ids"]) for item in tasks), "update_count": 0, "error_count": 0},
    }


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"
