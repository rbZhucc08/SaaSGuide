"""V3 Feishu writeback contract tests: the human confirmation gate is enforced in code."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from routes.v3_connectors import _pushable_actions, create_connector_blueprint
from services.connectors.feishu_bitable import (
    FeishuBitableClient,
    FeishuConnectorError,
    connector_status,
    validate_actions,
    writeback_actions,
)


CONFIRMED_ACTION = {
    "action_id": "A-1",
    "task_id": "T-1",
    "content": "与客户确认交付范围并更新任务状态",
    "policy_reference": "《交付管理制度》第 4.2 条",
    "suggested_owner": "交付负责人",
    "completion_signal": "任务状态更新为进行中且备注填写完成",
    "confirmation_status": "已确认",
}


def _action(action_id: str = "A-1", status: str = "已确认") -> dict[str, str]:
    return {**CONFIRMED_ACTION, "action_id": action_id, "confirmation_status": status}


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.payload).encode()


class WritebackOpener:
    """Records every outbound request so tests can assert what was actually sent."""

    def __init__(self): self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if "tenant_access_token" in request.full_url:
            return FakeResponse({"code": 0, "tenant_access_token": "test-token"})
        body = json.loads(request.data.decode("utf-8"))
        created = [
            {"record_id": f"rec-write-{index}", "fields": item["fields"]}
            for index, item in enumerate(body.get("records", []), start=1)
        ]
        return FakeResponse({"code": 0, "data": {"records": created}})

    @property
    def write_requests(self):
        return [item for item in self.requests if "/records/batch_create" in item[0].full_url]


def _client(opener, **overrides):
    values = {
        "app_id": "id", "app_secret": "test-key", "app_token": "app", "table_id": "table",
        "writeback_table_id": "action-table", "writeback_enabled": True,
    }
    values.update(overrides)
    return FeishuBitableClient(opener=opener, **values)


class ValidationGateTests(unittest.TestCase):
    def test_unconfirmed_action_is_refused(self):
        with self.assertRaises(FeishuConnectorError) as context:
            validate_actions([_action(status="待确认")])
        self.assertEqual("action_not_confirmed", context.exception.code)
        self.assertEqual(409, context.exception.status)

    def test_missing_confirmation_field_is_refused(self):
        action = _action()
        action.pop("confirmation_status")
        with self.assertRaises(FeishuConnectorError) as context:
            validate_actions([action])
        self.assertEqual("action_not_confirmed", context.exception.code)

    def test_missing_business_field_is_refused(self):
        action = _action()
        action.pop("completion_signal")
        with self.assertRaises(FeishuConnectorError) as context:
            validate_actions([action])
        self.assertEqual("invalid_actions", context.exception.code)
        self.assertEqual(422, context.exception.status)

    def test_duplicate_action_ids_in_one_batch_are_refused(self):
        with self.assertRaises(FeishuConnectorError) as context:
            validate_actions([_action("A-1"), _action("A-1")])
        self.assertEqual("invalid_actions", context.exception.code)

    def test_empty_and_non_list_inputs_are_refused(self):
        for payload in (None, [], {}, "A-1"):
            with self.assertRaises(FeishuConnectorError):
                validate_actions(payload)

    def test_batch_larger_than_limit_is_refused(self):
        with self.assertRaises(FeishuConnectorError) as context:
            validate_actions([_action(f"A-{index}") for index in range(501)])
        self.assertEqual("batch_too_large", context.exception.code)

    def test_confirmed_action_passes_and_is_normalized(self):
        confirmed = validate_actions([_action()])
        self.assertEqual(1, len(confirmed))
        self.assertEqual("A-1", confirmed[0]["action_id"])


class WritebackTests(unittest.TestCase):
    def test_confirmed_action_is_written_to_the_action_table(self):
        opener = WritebackOpener()
        result = writeback_actions(_client(opener), [_action()])
        self.assertEqual(1, result["written_count"])
        self.assertEqual(["A-1"], result["written_action_ids"])
        self.assertEqual("dedicated_action_table", result["target"])
        self.assertFalse(result["source_table_modified"])
        self.assertEqual(1, len(opener.write_requests))
        request = opener.write_requests[0][0]
        self.assertEqual("POST", request.method)
        self.assertIn("/tables/action-table/records/batch_create", request.full_url)

    def test_writeback_never_targets_the_source_table_when_configured_separately(self):
        opener = WritebackOpener()
        client = _client(opener, writeback_app_token="action-app", writeback_table_id="action-table")
        writeback_actions(client, [_action()])
        self.assertIn("/apps/action-app/tables/action-table/records/batch_create", opener.write_requests[0][0].full_url)
        self.assertNotIn("/tables/table/", opener.write_requests[0][0].full_url)

    def test_second_push_of_the_same_action_is_skipped(self):
        opener = WritebackOpener()
        result = writeback_actions(_client(opener), [_action()], already_written=["A-1"])
        self.assertEqual(0, result["written_count"])
        self.assertEqual(1, result["skipped_count"])
        self.assertEqual(["A-1"], result["skipped_action_ids"])
        self.assertEqual([], opener.write_requests)

    def test_only_new_actions_are_written_and_prior_ones_are_skipped(self):
        opener = WritebackOpener()
        result = writeback_actions(_client(opener), [_action("A-1"), _action("A-2")], already_written=["A-1"])
        self.assertEqual(1, result["written_count"])
        self.assertEqual(["A-2"], result["written_action_ids"])
        self.assertEqual(["A-1"], result["skipped_action_ids"])

    def test_writeback_requires_its_own_credentials(self):
        opener = WritebackOpener()
        client = _client(opener, app_id="", writeback_app_token="action-app", writeback_table_id="action-table")
        with self.assertRaises(FeishuConnectorError) as context:
            writeback_actions(client, [_action()])
        self.assertEqual("writeback_credentials_missing", context.exception.code)

    def test_writeback_requires_explicit_action_table_id(self):
        opener = WritebackOpener()
        client = _client(opener, writeback_table_id="")
        with self.assertRaises(FeishuConnectorError) as context:
            writeback_actions(client, [_action()])
        self.assertEqual("writeback_credentials_missing", context.exception.code)
        self.assertEqual([], opener.requests)

    def test_writeback_refuses_source_table_as_target(self):
        opener = WritebackOpener()
        client = _client(opener, writeback_app_token="app", writeback_table_id="table")
        with self.assertRaises(FeishuConnectorError) as context:
            writeback_actions(client, [_action()])
        self.assertEqual("writeback_source_table_forbidden", context.exception.code)
        self.assertEqual([], opener.requests)

    def test_writeback_stays_off_until_explicitly_opted_in(self):
        """Configuring a read table must never be enough to start writing into it."""
        opener = WritebackOpener()
        client = FeishuBitableClient(app_id="id", app_secret="", app_token="app", table_id="table", opener=opener)
        self.assertFalse(client.writeback_configured)
        self.assertFalse(connector_status(client)["writeback_enabled"])
        with self.assertRaises(FeishuConnectorError) as context:
            writeback_actions(client, [_action()])
        self.assertEqual("writeback_credentials_missing", context.exception.code)
        self.assertEqual([], opener.requests)

    def test_writeback_opt_in_flag_alone_is_insufficient_without_credentials(self):
        opener = WritebackOpener()
        client = FeishuBitableClient(app_id="", app_secret="", app_token="", table_id="", writeback_enabled=True, opener=opener)
        self.assertFalse(client.writeback_configured)

    def test_unconfirmed_action_never_reaches_the_network(self):
        opener = WritebackOpener()
        with self.assertRaises(FeishuConnectorError):
            writeback_actions(_client(opener), [_action(status="已驳回")])
        self.assertEqual([], opener.requests)

    def test_status_marks_writeback_as_confirmation_gated(self):
        client = _client(WritebackOpener(), writeback_app_token="action-app", writeback_table_id="action-table")
        status = connector_status(client)
        self.assertTrue(status["writeback_enabled"])
        self.assertTrue(status["writeback_requires_confirmation"])
        self.assertEqual("dedicated_action_table", status["writeback_target"])
        self.assertNotIn("test-key", str(status))


class LocalActionGateTests(unittest.TestCase):
    def _rows(self, **overrides):
        row = {
            "action_id": "action-1",
            "status": "open",
            "title": "核对交付范围",
            "owner_role": "交付负责人",
            "completion_signal": "范围已书面确认",
            "task_id": "T-1",
            "policy_reference": "《交付制度》第 4.2 条",
        }
        row.update(overrides)
        return {"actions": [row]}

    def test_local_action_requires_task_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "app.db"
            database.touch()
            with patch("database.store.dashboard", return_value=self._rows(task_id="")):
                pushable, skipped = _pushable_actions(database)
        self.assertEqual([], pushable)
        self.assertIn("task_id", skipped[0]["reason"])

    def test_local_action_requires_real_policy_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "app.db"
            database.touch()
            with patch("database.store.dashboard", return_value=self._rows(policy_reference="")):
                pushable, skipped = _pushable_actions(database)
        self.assertEqual([], pushable)
        self.assertIn("policy_reference", skipped[0]["reason"])

    def test_local_action_preserves_verified_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "app.db"
            database.touch()
            with patch("database.store.dashboard", return_value=self._rows()):
                pushable, skipped = _pushable_actions(database)
        self.assertEqual([], skipped)
        self.assertEqual("T-1", pushable[0]["task_id"])
        self.assertEqual("《交付制度》第 4.2 条", pushable[0]["policy_reference"])


class WritebackRouteTests(unittest.TestCase):
    def _app(self, temporary, opener, **overrides):
        app = Flask(__name__)
        app.register_blueprint(create_connector_blueprint(
            output_dir=Path(temporary),
            client_factory=lambda: _client(opener, **overrides),
        ))
        return app.test_client()

    def test_route_writes_confirmed_action_and_records_audit(self):
        opener = WritebackOpener()
        with tempfile.TemporaryDirectory() as temporary:
            client = self._app(temporary, opener)
            response = client.post("/api/connectors/feishu/push-actions", json={"actions": [_action()]})
            self.assertEqual(200, response.status_code)
            self.assertEqual(1, response.get_json()["written_count"])
            audit = Path(temporary) / "connectors" / "feishu" / "audit.jsonl"
            self.assertIn("feishu_writeback", audit.read_text(encoding="utf-8"))
            log = json.loads((Path(temporary) / "connectors" / "feishu" / "writeback.json").read_text(encoding="utf-8"))
            self.assertEqual(["A-1"], log["written_action_ids"])

    def test_route_is_idempotent_across_requests(self):
        opener = WritebackOpener()
        with tempfile.TemporaryDirectory() as temporary:
            client = self._app(temporary, opener)
            first = client.post("/api/connectors/feishu/push-actions", json={"actions": [_action()]})
            second = client.post("/api/connectors/feishu/push-actions", json={"actions": [_action()]})
            self.assertEqual(1, first.get_json()["written_count"])
            self.assertEqual(0, second.get_json()["written_count"])
            self.assertEqual(1, second.get_json()["skipped_count"])
            self.assertEqual(1, len(opener.write_requests))

    def test_route_refuses_unconfirmed_action(self):
        opener = WritebackOpener()
        with tempfile.TemporaryDirectory() as temporary:
            client = self._app(temporary, opener)
            response = client.post("/api/connectors/feishu/push-actions", json={"actions": [_action(status="待确认")]})
            self.assertEqual(409, response.status_code)
            self.assertEqual("action_not_confirmed", response.get_json()["code"])
            self.assertFalse(response.get_json()["source_table_modified"])
            self.assertEqual([], opener.write_requests)

    def test_route_blocks_missing_writeback_credentials(self):
        opener = WritebackOpener()
        with tempfile.TemporaryDirectory() as temporary:
            client = self._app(temporary, opener, app_id="")
            response = client.post("/api/connectors/feishu/push-actions", json={"actions": [_action()]})
            self.assertEqual(409, response.status_code)
            self.assertEqual("writeback_credentials_missing", response.get_json()["code"])

    def test_route_rejects_malformed_payload_without_writing(self):
        opener = WritebackOpener()
        with tempfile.TemporaryDirectory() as temporary:
            client = self._app(temporary, opener)
            self.assertEqual(400, client.post("/api/connectors/feishu/push-actions", json={}).status_code)
            self.assertEqual(400, client.post("/api/connectors/feishu/push-actions", json={"actions": "A-1"}).status_code)
            self.assertEqual([], opener.write_requests)


if __name__ == "__main__":
    unittest.main(verbosity=2)
