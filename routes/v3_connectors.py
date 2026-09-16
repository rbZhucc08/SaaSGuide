"""V3 external connector endpoints: read-only sync plus human-gated writeback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request

from services.connectors.feishu_bitable import (
    FeishuBitableClient,
    FeishuConnectorError,
    connector_status,
    sync_snapshot,
    writeback_actions,
)


DEFAULT_MAPPING = {
    "project_id": "项目编号", "project_name": "项目名称", "task_id": "任务编号", "task_name": "任务名称",
    "owner": "负责人", "due_date": "截止日期", "status": "状态", "updated_at": "更新时间",
}


def _load_written_action_ids(target: Path) -> list[str]:
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    identifiers = payload.get("written_action_ids", []) if isinstance(payload, dict) else []
    return [str(item) for item in identifiers] if isinstance(identifiers, list) else []


# 本地行动只有"已确认并保存"的状态才允许离开系统。
PUSHABLE_ACTION_STATUSES = {"open", "in_progress"}


def _pushable_actions(database_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把本地已确认行动转换成写回所需的字段形状。

    未通过人工确认闸门的行动不会被转换，也不会离开本机。
    """
    if database_path is None or not Path(database_path).exists():
        return [], []
    from database.store import dashboard as action_dashboard

    rows = action_dashboard(Path(database_path))["actions"]
    pushable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in rows:
        if item.get("status") not in PUSHABLE_ACTION_STATUSES:
            skipped.append({"action_id": item.get("action_id"), "reason": f"状态为 {item.get('status')}，未通过人工确认闸门"})
            continue
        required = ("title", "owner_role", "completion_signal", "task_id", "policy_reference")
        missing = [key for key in required if not str(item.get(key) or "").strip()]
        if missing:
            skipped.append({"action_id": item.get("action_id"), "reason": "缺少字段：" + "、".join(missing)})
            continue
        pushable.append({
            "action_id": str(item["action_id"]),
            "task_id": str(item["task_id"]).strip(),
            "content": str(item["title"]),
            "policy_reference": str(item["policy_reference"]).strip(),
            "suggested_owner": str(item["owner_role"]),
            "completion_signal": str(item["completion_signal"]),
            "confirmation_status": "已确认",
        })
    return pushable, skipped


def create_connector_blueprint(
    *,
    output_dir: Path,
    database_path: Path | None = None,
    client_factory: Callable[[], FeishuBitableClient] = FeishuBitableClient,
) -> Blueprint:
    blueprint = Blueprint("v3_connectors", __name__)
    connector_dir = output_dir / "connectors" / "feishu"
    push_log = connector_dir / "writeback.json"

    @blueprint.get("/api/connectors/feishu/status")
    def feishu_status() -> Any:
        return jsonify(connector_status(client_factory()))

    @blueprint.post("/api/connectors/feishu/sync")
    def feishu_sync() -> Any:
        payload = request.get_json(silent=True) or {}
        mapping = payload.get("mapping", DEFAULT_MAPPING)
        if not isinstance(mapping, dict):
            return jsonify({"error": "mapping 必须是对象", "code": "mapping_required"}), 400
        try:
            result = sync_snapshot(client_factory(), mapping, connector_dir / "records.json")
            audit = connector_dir / "audit.jsonl"
            audit.parent.mkdir(parents=True, exist_ok=True)
            with audit.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({**result, "event": "feishu_read_sync"}, ensure_ascii=False) + "\n")
            return jsonify(result)
        except FeishuConnectorError as error:
            return jsonify({"error": str(error), "code": error.code, "writeback": "not_performed"}), error.status

    @blueprint.post("/api/connectors/feishu/push-actions")
    def feishu_push_actions() -> Any:
        """Write human-confirmed actions into the dedicated writeback table.

        The customer's source table is never modified: writeback targets a separate
        action table so a wrong model suggestion cannot overwrite business data.
        """
        payload = request.get_json(silent=True) or {}
        try:
            result = writeback_actions(
                client_factory(),
                payload.get("actions"),
                already_written=_load_written_action_ids(push_log),
            )
        except FeishuConnectorError as error:
            return jsonify({"error": str(error), "code": error.code, "source_table_modified": False}), error.status
        connector_dir.mkdir(parents=True, exist_ok=True)
        prior = _load_written_action_ids(push_log)
        merged = sorted({*prior, *[str(item) for item in result["written_action_ids"]]})
        push_log.write_text(json.dumps({"written_action_ids": merged, "updated_at": result["writeback_id"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (connector_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**result, "event": "feishu_writeback"}, ensure_ascii=False) + "\n")
        return jsonify(result)

    @blueprint.post("/api/connectors/feishu/push-local-actions")
    def feishu_push_local_actions() -> Any:
        """把本地已人工确认的行动推送到飞书的独立行动表。

        只有通过了确认闸门（状态为 open / in_progress）的行动才会被推送；
        未确认、已取消或已完成但未复核的行动会被明确列出并跳过。
        """
        try:
            pushable, skipped = _pushable_actions(database_path)
        except Exception as error:  # 本地库不可读时不静默失败
            return jsonify({"error": f"本地行动数据无法读取：{error}", "code": "action_store_unavailable"}), 503
        if not pushable:
            return jsonify({
                "error": "没有通过人工确认闸门、可以推送的行动",
                "code": "no_pushable_actions",
                "skipped": skipped,
                "source_table_modified": False,
            }), 409
        try:
            result = writeback_actions(
                client_factory(),
                pushable,
                already_written=_load_written_action_ids(push_log),
            )
        except FeishuConnectorError as error:
            return jsonify({"error": str(error), "code": error.code, "source_table_modified": False}), error.status
        result["skipped_local_actions"] = skipped
        connector_dir.mkdir(parents=True, exist_ok=True)
        prior = _load_written_action_ids(push_log)
        merged = sorted({*prior, *[str(item) for item in result["written_action_ids"]]})
        push_log.write_text(json.dumps({"written_action_ids": merged, "updated_at": result["writeback_id"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (connector_dir / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**result, "event": "feishu_writeback"}, ensure_ascii=False) + "\n")
        return jsonify(result)

    return blueprint
