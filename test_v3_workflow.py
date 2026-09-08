from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server import create_app


class V3WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        app = create_app(
            output_dir=root,
            risk_decision_file=root / "risk-decisions.jsonl",
            evidence_review_file=root / "evidence-reviews.jsonl",
            database_path=root / "saasguide.db",
            evaluator=lambda value: {},
            risk_evaluator=lambda value, note: {},
        )
        app.config["TESTING"] = True
        self.client = app.test_client()

    def _confirmed_candidate(self):
        scan = self.client.post("/api/risk-scans/sample").get_json()
        candidate = scan["candidates"][0]
        payload = {
            **{key: candidate[key] for key in ("candidate_id", "candidate_key", "task_id", "title", "severity", "risk_type")},
            "source_id": scan["source"]["source_id"],
            "scan_id": scan["scan_id"],
            "project_id": scan["project"]["project_id"],
            "project_name": scan["project"]["project_name"],
            "evidence": candidate["evidence"],
            "decision": "confirm",
            "actor": "流程测试员",
            "note": "浏览器链路测试",
        }
        response = self.client.post("/api/risk-scans/decisions", json=payload)
        self.assertEqual(201, response.status_code)
        return scan, candidate, response.get_json()["record"]

    def test_risk_confirmation_action_and_report_share_ids(self):
        scan, candidate, decision = self._confirmed_candidate()
        action_payload = {
            "candidate_id": candidate["candidate_id"],
            "candidate_title": candidate["title"],
            "project_id": scan["project"]["project_id"],
            "risk_decision_id": decision["decision_id"],
            "plan_run_id": "ai-run-test-plan",
            "plan_step": 1,
            "title": "核对阻塞任务并记录结论",
            "owner_role": "项目负责人",
            "due_date": "2026-09-10",
            "completion_signal": "形成带责任人的核对记录",
            "actor": "流程测试员",
            "human_confirmed": True,
        }
        rejected = self.client.post("/api/actions", json={**action_payload, "human_confirmed": False})
        self.assertEqual(400, rejected.status_code)
        created = self.client.post("/api/actions", json=action_payload)
        self.assertEqual(201, created.status_code)
        action = created.get_json()["action"]
        self.assertEqual(decision["decision_id"], action["risk_decision_id"])
        self.assertEqual("ai-run-test-plan", action["plan_run_id"])
        for status in ("in_progress", "completed", "open", "cancelled"):
            response = self.client.post(f"/api/actions/{action['action_id']}/transition", json={"status": status, "actor": "流程测试员"})
            self.assertEqual(200, response.status_code)
        illegal = self.client.post(f"/api/actions/{action['action_id']}/transition", json={"status": "completed", "actor": "流程测试员"})
        self.assertEqual(400, illegal.status_code)
        report = self.client.get("/api/reports/weekly?as_of=2026-09-11").get_json()
        self.assertIn(candidate["candidate_id"], report["traceability"]["candidate_ids"])
        self.assertIn(action["action_id"], report["traceability"]["action_ids"])
        self.assertEqual(candidate["candidate_id"], report["actions"][0]["candidate_id"])

    def test_latest_non_confirm_decision_blocks_action(self):
        scan, candidate, decision = self._confirmed_candidate()
        later = {
            "candidate_id": candidate["candidate_id"],
            "candidate_key": candidate["candidate_key"],
            "source_id": scan["source"]["source_id"],
            "scan_id": scan["scan_id"],
            "project_id": scan["project"]["project_id"],
            "title": candidate["title"],
            "decision": "reject",
            "actor": "流程测试员",
        }
        self.assertEqual(201, self.client.post("/api/risk-scans/decisions", json=later).status_code)
        action = self.client.post("/api/actions", json={
            "candidate_id": candidate["candidate_id"], "risk_decision_id": decision["decision_id"],
            "title": "不应保存", "owner_role": "项目负责人", "due_date": "2026-09-10",
            "completion_signal": "不应出现", "actor": "流程测试员", "human_confirmed": True,
        })
        self.assertEqual(400, action.status_code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
