import json
import tempfile
import unittest
from pathlib import Path

from server import create_app


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app(evaluator=lambda value: {}, risk_evaluator=lambda value, note: {})
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_health_is_truthful(self):
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("simulated-data-only", response.get_json()["scope"])
        response.close()

    def test_security_headers_on_html_and_api(self):
        for path in ("/", "/health"):
            response = self.client.get(path)
            self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
            self.assertEqual("DENY", response.headers["X-Frame-Options"])
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertIn("microphone=()", response.headers["Permissions-Policy"])
            response.close()

    def test_removed_v2_overview_returns_404(self):
        response = self.client.get("/v2")
        self.assertEqual(404, response.status_code)
        response.close()

    def test_root_is_v2_workbench_without_fixed_v1_risks(self):
        response = self.client.get("/")
        text = response.get_data(as_text=True)
        response.close()
        self.assertIn("项目风险工作台", text)
        self.assertNotIn("第三方 API 联调延迟", text)
        self.assertNotIn("V2 总览", text)
        for path in (
            "/data-sources",
            "/risk-radar",
            "/evidence-intake",
            "/knowledge-base",
            "/action-tracker",
            "/reports",
            "/input-lab",
        ):
            self.assertIn(path, text)

    def test_dashboard_empty_state_does_not_read_fixed_risk_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            knowledge = root / "knowledge.json"
            knowledge.write_text("[]", encoding="utf-8")
            app = create_app(
                normalized_data_dir=root / "normalized",
                risk_decision_file=root / "risk-decisions.jsonl",
                evidence_review_file=root / "evidence-reviews.jsonl",
                database_path=root / "missing.db",
                knowledge_file=knowledge,
            )
            app.config["TESTING"] = True
            data = app.test_client().get("/api/dashboard").get_json()
            self.assertEqual({"imports": 0, "projects": 0, "tasks": 0, "risk_decisions": 0, "evidence_reviews": 0, "knowledge_versions": 0}, data["summary"])
            self.assertEqual([], data["recent_activity"])
            self.assertFalse((root / "missing.db").exists())

    def test_dashboard_counts_confirmed_imports_not_evaluation_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            normalized = root / "normalized"
            normalized.mkdir()
            payload = {"import_id": "import-user", "source": {"source_name": "user.xlsx", "imported_at": "2026-09-05T10:00:00+08:00"}, "project": {"project_id": "p1", "project_name": "用户项目"}, "summary": {"task_count": 3}}
            (normalized / "import-user.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            knowledge = root / "knowledge.json"
            knowledge.write_text("[]", encoding="utf-8")
            app = create_app(normalized_data_dir=normalized, risk_decision_file=root / "none.jsonl", evidence_review_file=root / "none2.jsonl", database_path=root / "none.db", knowledge_file=knowledge)
            app.config["TESTING"] = True
            data = app.test_client().get("/api/dashboard").get_json()
            self.assertEqual(1, data["summary"]["imports"])
            self.assertEqual(3, data["summary"]["tasks"])
            self.assertEqual("user.xlsx", data["recent_activity"][0]["title"].removeprefix("已确认导入 "))


if __name__ == "__main__":
    unittest.main(verbosity=2)
