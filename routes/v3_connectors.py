"""V3 read-only external connector endpoints."""

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
)


DEFAULT_MAPPING = {
    "project_id": "项目编号", "project_name": "项目名称", "task_id": "任务编号", "task_name": "任务名称",
    "owner": "负责人", "due_date": "截止日期", "status": "状态", "updated_at": "更新时间",
}


def create_connector_blueprint(*, output_dir: Path, client_factory: Callable[[], FeishuBitableClient] = FeishuBitableClient) -> Blueprint:
    blueprint = Blueprint("v3_connectors", __name__)

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
            result = sync_snapshot(client_factory(), mapping, output_dir / "connectors" / "feishu" / "records.json")
            audit = output_dir / "connectors" / "feishu" / "audit.jsonl"
            audit.parent.mkdir(parents=True, exist_ok=True)
            with audit.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({**result, "event": "feishu_read_sync"}, ensure_ascii=False) + "\n")
            return jsonify(result)
        except FeishuConnectorError as error:
            return jsonify({"error": str(error), "code": error.code, "writeback": "not_performed"}), error.status

    return blueprint
