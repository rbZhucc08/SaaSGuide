import json
import os
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from deepseek_ask_build import API_URL, DeepSeekClient, DeepSeekError, ModelOutputError
from server import create_app
from services.ai.orchestrator import orchestrate_risk_candidate
from services.ai.provider import BatchBudget, BudgetExceededError, BudgetPolicy
from services.risk_rules.deterministic_scan import scan_project


PROJECT_DIR = Path(__file__).resolve().parent


class FakeResponse:
    def __init__(self, content, usage=None):
        self.content = content
        self.usage = usage or {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        envelope = {"choices": [{"message": {"content": self.content}}], "usage": self.usage}
        return json.dumps(envelope).encode("utf-8")


def candidate_context():
    document = json.loads((PROJECT_DIR / "data" / "evaluation" / "phase2_project_timeline.json").read_text(encoding="utf-8"))
    scan = scan_project(document)
    return scan["candidates"][0], scan["project"], scan["source"]


class FakeJsonClient:
    provider_name = "deepseek"
    model = "deepseek-test"
    last_usage = {}
    last_run = {"run_id": "model-run-redacted", "latency_ms": 12, "retry_count": 0, "cost": None}

    def __init__(self, result):
        self.result = result

    def create_json(self, _messages):
        return json.dumps(self.result, ensure_ascii=False)


class ModelReliabilityTests(unittest.TestCase):
    def test_valid_ask_uses_strict_protocol_and_versions(self):
        candidate, project, source = candidate_context()
        result = orchestrate_risk_candidate(
            candidate,
            project,
            source,
            "",
            PROJECT_DIR / "knowledge" / "documents" / "policies.json",
            client=FakeJsonClient({"decision": "ASK", "reason": "缺少恢复日期", "questions": [{"field": "recovery_date", "question": "预计何时恢复？"}]}),
        )
        self.assertEqual("ASK", result["decision"])
        self.assertEqual("deepseek-api", result["source"])
        self.assertEqual("risk-planner-prompt-v3.1", result["prompt_version"])
        self.assertEqual("risk-ask-plan-v1", result["protocol_version"])

    def test_strict_protocol_rejects_extra_model_field(self):
        candidate, project, source = candidate_context()
        with self.assertRaisesRegex(ModelOutputError, "协议外字段"):
            orchestrate_risk_candidate(
                candidate,
                project,
                source,
                "",
                PROJECT_DIR / "knowledge" / "documents" / "policies.json",
                client=FakeJsonClient({"decision": "ASK", "reason": "需要信息", "questions": [{"field": "x", "question": "请补充"}], "autoExecute": True}),
            )

    def test_success_records_redacted_telemetry_and_usage(self):
        content = json.dumps({"decision": "ASK", "reason": "需要信息", "questions": [{"field": "x", "question": "请补充"}]})
        client = DeepSeekClient(api_key="secret-test-key", opener=lambda *_args, **_kwargs: FakeResponse(content), max_retries=0)
        client.create_json([{"role": "user", "content": "test"}])
        self.assertEqual(30, client.last_usage["total_tokens"])
        self.assertTrue(client.last_run["run_id"].startswith("model-run-"))
        self.assertNotIn("secret-test-key", json.dumps(client.last_run))
        self.assertEqual(0, client.last_run["retry_count"])
        self.assertIsNone(client.last_run["cost"])

    def test_timeout_retries_are_finite_and_classified(self):
        attempts = []
        delays = []

        def opener(*_args, **_kwargs):
            attempts.append(1)
            raise TimeoutError("slow")

        client = DeepSeekClient(api_key="test", opener=opener, max_retries=2, backoff_seconds=0.01, sleeper=delays.append)
        with self.assertRaises(DeepSeekError) as raised:
            client.create_json([{"role": "user", "content": "test"}])
        self.assertEqual("timeout", raised.exception.code)
        self.assertEqual(3, len(attempts))
        self.assertEqual([0.01, 0.02], delays)
        self.assertEqual(2, raised.exception.run["retry_count"])

    def test_rate_limit_retries_then_stops(self):
        attempts = []

        def opener(*_args, **_kwargs):
            attempts.append(1)
            raise HTTPError(API_URL, 429, "rate", None, None)

        client = DeepSeekClient(api_key="test", opener=opener, max_retries=1, sleeper=lambda _delay: None)
        with self.assertRaises(DeepSeekError) as raised:
            client.create_json([{"role": "user", "content": "test"}])
        self.assertEqual("rate_limited", raised.exception.code)
        self.assertEqual(2, len(attempts))

    def test_single_call_over_budget_stops_before_network(self):
        called = []
        policy = BudgetPolicy(max_input_tokens=2, max_output_tokens=2, max_total_tokens=4)
        client = DeepSeekClient(api_key="test", opener=lambda *_a, **_k: called.append(1), budget_policy=policy)
        with self.assertRaises(DeepSeekError) as raised:
            client.create_json([{"role": "user", "content": "far too long for this budget"}])
        self.assertEqual("over_budget", raised.exception.code)
        self.assertEqual([], called)

    def test_batch_budget_blocks_excess_calls(self):
        policy = BudgetPolicy(max_batch_calls=1, max_batch_total_tokens=100)
        batch = BatchBudget(policy)
        batch.reserve(10, 10)
        with self.assertRaises(BudgetExceededError):
            batch.reserve(10, 10)

    def test_provider_unavailable_is_classified_without_network(self):
        with patch.dict(os.environ, {}, clear=True):
            client = DeepSeekClient(api_key="")
            with self.assertRaises(DeepSeekError) as raised:
                client.create_json([{"role": "user", "content": "test"}])
        self.assertEqual("provider_unavailable", raised.exception.code)
        self.assertEqual(0, raised.exception.run["attempts"])

    def test_capabilities_expose_runtime_limits_and_fallback(self):
        app = create_app()
        app.config["TESTING"] = True
        data = app.test_client().get("/api/agent/capabilities").get_json()
        self.assertEqual("deepseek-json-v1", data["client_protocol_version"])
        self.assertEqual(10_000, data["budget"]["max_total_tokens"])
        self.assertIn("规则扫描和人工处理", data["model_status_reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
