"""V3 phase 9 Feishu Base connector contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from flask import Flask
from routes.v3_connectors import create_connector_blueprint
from services.connectors.feishu_bitable import FeishuBitableClient, connector_status, normalize_record, sync_snapshot


MAPPING = {"project_id":"项目编号","project_name":"项目名称","task_id":"任务编号","task_name":"任务名称","owner":"负责人","due_date":"截止日期","status":"状态","updated_at":"更新时间"}


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.payload).encode()


class FakeOpener:
    def __init__(self): self.requests = []
    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if "tenant_access_token" in request.full_url:
            return FakeResponse({"code":0,"tenant_access_token":"test-token"})
        page = len([item for item in self.requests if "/records/search" in item[0].full_url])
        record = {"record_id":f"rec-{page}","last_modified_time":1000+page,"fields":{"项目编号":"P-1","项目名称":"飞书接入","任务编号":f"T-{page}","任务名称":"只读同步","负责人":[{"name":"测试负责人"}],"截止日期":"2026-09-30","状态":"进行中","更新时间":"2026-09-09"}}
        return FakeResponse({"code":0,"data":{"items":[record],"has_more":page == 1,"page_token":"next" if page == 1 else ""}})


class FeishuConnectorTests(unittest.TestCase):
    def test_status_never_exposes_credentials(self):
        client = FeishuBitableClient(app_id="id-value", app_secret="secret-value", app_token="app-value", table_id="table-value")
        status = connector_status(client)
        self.assertTrue(status["configured"])
        self.assertNotIn("secret-value", str(status))
        self.assertFalse(status["writeback_enabled"])

    def test_missing_credentials_are_explicitly_blocked(self):
        status = connector_status(FeishuBitableClient(app_id="", app_secret="", app_token="", table_id=""))
        self.assertEqual("blocked_credentials_missing", status["live_validation"])

    def test_records_follow_page_token_and_request_automatic_fields(self):
        opener = FakeOpener()
        client = FeishuBitableClient(app_id="id", app_secret="test-key", app_token="app", table_id="table", opener=opener)
        records = client.records()
        self.assertEqual(2, len(records))
        search_requests = [item[0] for item in opener.requests if "/records/search" in item[0].full_url]
        self.assertIn("page_token=next", search_requests[1].full_url)
        self.assertTrue(json.loads(search_requests[0].data)["automatic_fields"])
        self.assertEqual("POST", search_requests[0].method)

    def test_normalization_handles_person_field_without_extra_permissions(self):
        result = normalize_record({"record_id":"rec-1","last_modified_time":123,"fields":{name:name for name in MAPPING.values()} | {"负责人":[{"name":"李敏"}]}}, MAPPING)
        self.assertEqual("李敏", result["owner"])
        self.assertEqual("rec-1", result["source_record_id"])

    def test_snapshot_is_idempotent_by_record_id_and_keeps_cursor(self):
        opener = FakeOpener()
        client = FeishuBitableClient(app_id="id", app_secret="test-key", app_token="app", table_id="table", opener=opener)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "records.json"
            first = sync_snapshot(client, MAPPING, target)
            self.assertEqual(2, first["stored_count"])
            self.assertEqual(2, first["applied_count"])
            second_client = FeishuBitableClient(app_id="id", app_secret="test-key", app_token="app", table_id="table", opener=FakeOpener())
            second = sync_snapshot(second_client, MAPPING, target)
            self.assertEqual(2, second["stored_count"])
            self.assertEqual(0, second["applied_count"])
            self.assertEqual(1002, second["cursor"]["last_modified_time"])
            self.assertEqual("not_performed", second["writeback"])

    def test_connector_routes_block_missing_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Flask(__name__)
            app.register_blueprint(create_connector_blueprint(
                output_dir=Path(temporary),
                client_factory=lambda: FeishuBitableClient(app_id="", app_secret="", app_token="", table_id=""),
            ))
            client = app.test_client()
            self.assertFalse(client.get("/api/connectors/feishu/status").get_json()["configured"])
            response = client.post("/api/connectors/feishu/sync", json={})
            self.assertEqual(409, response.status_code)
            self.assertEqual("credentials_missing", response.get_json()["code"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
