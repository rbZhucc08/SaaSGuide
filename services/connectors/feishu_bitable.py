"""Read-only Feishu Base connector with pagination and incremental snapshots."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
SEARCH_PATH = "/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search"
REQUIRED_MAPPING = ("project_id", "project_name", "task_id", "task_name", "owner", "due_date", "status", "updated_at")


class FeishuConnectorError(RuntimeError):
    def __init__(self, message: str, code: str, status: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _field_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value).strip()
    if isinstance(value, list):
        parts = [_field_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "name", "value", "id"):
            if value.get(key) not in (None, ""):
                return _field_text(value[key])
    return ""


def normalize_record(record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    fields = record.get("fields")
    if not isinstance(fields, dict):
        raise FeishuConnectorError("飞书记录缺少 fields 对象", "invalid_record", 422)
    missing = [key for key in REQUIRED_MAPPING if not str(mapping.get(key, "")).strip()]
    if missing:
        raise FeishuConnectorError("字段映射缺少：" + "、".join(missing), "mapping_required", 400)
    normalized = {key: _field_text(fields.get(mapping[key])) for key in REQUIRED_MAPPING}
    normalized.update({
        "source_record_id": str(record.get("record_id") or ""),
        "source_last_modified_time": int(record.get("last_modified_time") or 0),
        "source": "feishu_bitable",
    })
    if not normalized["source_record_id"]:
        raise FeishuConnectorError("飞书记录缺少 record_id", "invalid_record", 422)
    return normalized


class FeishuBitableClient:
    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        app_token: str | None = None,
        table_id: str | None = None,
        opener: Callable[..., Any] = urllib.request.urlopen,
        timeout_seconds: int = 15,
        max_retries: int = 2,
    ) -> None:
        self.app_id = app_id if app_id is not None else os.getenv("FEISHU_APP_ID", "")
        self.app_secret = app_secret if app_secret is not None else os.getenv("FEISHU_APP_SECRET", "")
        self.app_token = app_token if app_token is not None else os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
        self.table_id = table_id if table_id is not None else os.getenv("FEISHU_BITABLE_TABLE_ID", "")
        self.opener = opener
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return all((self.app_id, self.app_secret, self.app_token, self.table_id))

    def _request_json(self, request: urllib.request.Request, *, retryable: bool) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise FeishuConnectorError("飞书返回的 JSON 不是对象", "invalid_response")
                return payload
            except urllib.error.HTTPError as error:
                if error.code in {401, 403}:
                    raise FeishuConnectorError("飞书授权或表格权限不足", "permission_denied", 403) from error
                if error.code == 429 and retryable and attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                if error.code >= 500 and retryable and attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                code = "rate_limited" if error.code == 429 else "provider_unavailable"
                raise FeishuConnectorError("飞书接口暂时不可用", code, 503) from error
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
                if retryable and attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise FeishuConnectorError("无法连接飞书开放平台", "provider_unavailable", 503) from error
        raise FeishuConnectorError("飞书接口重试耗尽", "provider_unavailable", 503)

    def tenant_token(self) -> str:
        if not self.configured:
            raise FeishuConnectorError("飞书连接器缺少本机环境变量", "credentials_missing", 409)
        body = json.dumps({"app_id": self.app_id, "app_secret": self.app_secret}).encode("utf-8")
        request = urllib.request.Request(TOKEN_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
        payload = self._request_json(request, retryable=False)
        if payload.get("code") != 0 or not payload.get("tenant_access_token"):
            raise FeishuConnectorError("飞书应用凭据验证失败", "authentication_failed", 403)
        return str(payload["tenant_access_token"])

    def records(self) -> list[dict[str, Any]]:
        token = self.tenant_token()
        page_token = ""
        records: list[dict[str, Any]] = []
        while True:
            query = urllib.parse.urlencode({"page_size": 500, **({"page_token": page_token} if page_token else {})})
            path = SEARCH_PATH.format(
                app_token=urllib.parse.quote(self.app_token, safe=""),
                table_id=urllib.parse.quote(self.table_id, safe=""),
            )
            request = urllib.request.Request(
                f"https://open.feishu.cn{path}?{query}",
                data=json.dumps({"automatic_fields": True}).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            payload = self._request_json(request, retryable=True)
            if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
                raise FeishuConnectorError(str(payload.get("msg") or "飞书记录查询失败"), "api_error")
            data = payload["data"]
            items = data.get("items", [])
            if not isinstance(items, list):
                raise FeishuConnectorError("飞书 records 响应缺少 items 列表", "invalid_response")
            records.extend(item for item in items if isinstance(item, dict))
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "")
            if not page_token:
                raise FeishuConnectorError("飞书分页响应缺少 page_token", "invalid_response")
        return records


def connector_status(client: FeishuBitableClient) -> dict[str, Any]:
    return {
        "connector": "feishu_bitable_read_only",
        "configured": client.configured,
        "mode": "read_only",
        "writeback_enabled": False,
        "live_validation": "available" if client.configured else "blocked_credentials_missing",
        "required_environment": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_BITABLE_APP_TOKEN", "FEISHU_BITABLE_TABLE_ID"],
        "credential_values_exposed": False,
    }


def sync_snapshot(client: FeishuBitableClient, mapping: dict[str, str], target: Path) -> dict[str, Any]:
    existing: dict[str, Any] = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
    prior = {item["source_record_id"]: item for item in existing.get("records", []) if isinstance(item, dict) and item.get("source_record_id")}
    fetched = [normalize_record(item, mapping) for item in client.records()]
    applied_count = 0
    for item in fetched:
        previous = prior.get(item["source_record_id"])
        if previous is None or int(item["source_last_modified_time"]) > int(previous.get("source_last_modified_time") or 0):
            prior[item["source_record_id"]] = item
            applied_count += 1
    records = sorted(prior.values(), key=lambda item: item["source_record_id"])
    cursor = max((int(item.get("source_last_modified_time") or 0) for item in records), default=0)
    snapshot = {
        "schema_version": "feishu-bitable-read-v1",
        "synced_at": _now(),
        "cursor": {"last_modified_time": cursor},
        "records": records,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return {
        "sync_id": f"feishu-sync-{uuid4().hex[:12]}",
        "fetched_count": len(fetched),
        "applied_count": applied_count,
        "stored_count": len(records),
        "cursor": snapshot["cursor"],
        "writeback": "not_performed",
    }
