import json
import tempfile
import unittest
from pathlib import Path

from deepseek_ask_build import DeepSeekError, ModelOutputError
from server import create_app
from services.ai.orchestrator import orchestrate_risk_candidate
from services.ai.skills import catalog
from services.risk_rules.deterministic_scan import scan_project


PROJECT_DIR = Path(__file__).resolve().parent


class FakeClient:
    model = "deepseek-test"
    last_usage = {"total_tokens": 42}

    def __init__(self, result):
        self.result = result
        self.called = False

    def create_json(self, _messages):
        self.called = True
        return json.dumps(self.result, ensure_ascii=False)


def candidate_context():
    document = json.loads((PROJECT_DIR / "data" / "evaluation" / "phase2_project_timeline.json").read_text(encoding="utf-8"))
    scan = scan_project(document)
    return scan["candidates"][0], scan["project"], scan["source"]


def valid_plan(citation_id="delay-process@1.1"):
    return {
        "decision": "PLAN",
        "summary": "延期信号可能影响下游里程碑。",
        "suggestedLevel": "高风险",
        "priority": "立即处理",
        "rationale": ["确定性规则已发现逾期信号。"],
        "citationIds": [citation_id],
        "actions": [{"step": 1, "action": "核对依赖关系。", "ownerRole": "项目经理", "successSignal": "形成带责任人的依赖核对记录。"}],
        "cautions": ["建议仍需人工确认。"],
    }


class AiOrchestratorTests(unittest.TestCase):
    def test_runtime_catalog_contains_five_real_contracts(self):
        skills = catalog()
        self.assertEqual(
            ["project-data-intake", "risk-signal-scan", "evidence-grounded-assessment", "risk-action-planner", "weekly-risk-report"],
            [item["name"] for item in skills],
        )
        self.assertTrue(all(item["tool"] and item["failure"] for item in skills))

    def test_incomplete_candidate_returns_local_ask_without_model(self):
        client = FakeClient(valid_plan())
        result = orchestrate_risk_candidate({}, {}, {}, "", PROJECT_DIR / "knowledge" / "documents" / "policies.json", client=client)
        self.assertEqual("ASK", result["decision"])
        self.assertEqual("not_called", result["model_status"])
        self.assertFalse(client.called)

    def test_plan_uses_retrieved_citation_and_reports_skill_trace(self):
        candidate, project, source = candidate_context()
        client = FakeClient(valid_plan())
        result = orchestrate_risk_candidate(candidate, project, source, "补充背景", PROJECT_DIR / "knowledge" / "documents" / "policies.json", client=client)
        self.assertEqual("PLAN", result["decision"])
        self.assertEqual("called", result["model_status"])
        self.assertEqual("deepseek-api", result["source"])
        self.assertEqual(42, result["usage"]["total_tokens"])
        self.assertIn("delay-process@1.1", [item["citation_id"] for item in result["citations"]])
        self.assertEqual(
            ["risk-signal-scan", "evidence-grounded-assessment", "risk-action-planner"],
            [item["skill"] for item in result["trace"]],
        )

    def test_fabricated_citation_is_blocked(self):
        candidate, project, source = candidate_context()
        with self.assertRaises(ModelOutputError):
            orchestrate_risk_candidate(candidate, project, source, "", PROJECT_DIR / "knowledge" / "documents" / "policies.json", client=FakeClient(valid_plan("invented@9.9")))

    def test_more_than_three_actions_is_blocked(self):
        candidate, project, source = candidate_context()
        plan = valid_plan()
        plan["actions"] = [
            {"step": step, "action": f"行动 {step}", "ownerRole": "项目经理", "successSignal": f"证据 {step}"}
            for step in range(1, 5)
        ]
        with self.assertRaises(ModelOutputError):
            orchestrate_risk_candidate(candidate, project, source, "", PROJECT_DIR / "knowledge" / "documents" / "policies.json", client=FakeClient(plan))

    def test_agent_api_returns_injected_result(self):
        expected = {"run_id": "ai-run-test", "decision": "ASK", "model_status": "not_called", "trace": []}
        app = create_app(
            evaluator=lambda value: {},
            risk_evaluator=lambda value, note: {},
            ai_orchestrator=lambda candidate, project, source, note, knowledge: expected,
        )
        app.config["TESTING"] = True
        response = app.test_client().post("/api/agent/risk-assessment", json={"candidate": {}, "project": {}, "source": {}})
        self.assertEqual(200, response.status_code)
        self.assertEqual(expected, response.get_json())

    def test_agent_api_maps_provider_failure_without_exposing_key(self):
        def fail(*_args):
            raise DeepSeekError("API 密钥无效")

        app = create_app(evaluator=lambda value: {}, risk_evaluator=lambda value, note: {}, ai_orchestrator=fail)
        app.config["TESTING"] = True
        response = app.test_client().post("/api/agent/risk-assessment", json={"candidate": {}, "project": {}, "source": {}})
        self.assertEqual(502, response.status_code)
        self.assertEqual("agent_unavailable", response.get_json()["code"])
        self.assertNotIn("DEEPSEEK_API_KEY", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
