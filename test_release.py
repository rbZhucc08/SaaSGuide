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

    def test_public_assets_have_nosniff_safe_content_types(self):
        for path, expected in (("/risk-radar.js", "application/javascript"), ("/v2-shell.css", "text/css"), ("/guide-data.json", "application/json")):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(200, response.status_code)
                self.assertTrue(response.content_type.startswith(expected), response.content_type)
                response.close()

    def test_risk_radar_exposes_bounded_ai_assessment(self):
        response = self.client.get("/risk-radar")
        text = response.get_data(as_text=True)
        response.close()
        self.assertIn("agent-status", text)
        script_response = self.client.get("/risk-radar.js")
        script = script_response.get_data(as_text=True)
        script_response.close()
        self.assertIn("/api/agent/risk-assessment", script)
        self.assertIn("查看 Skill 运行轨迹", script)

    def test_agent_capabilities_do_not_expose_secret(self):
        response = self.client.get("/api/agent/capabilities")
        self.assertEqual(200, response.status_code)
        data = response.get_json()
        response.close()
        self.assertEqual("saasguide-v2-orchestrator", data["agent"])
        self.assertEqual(5, len(data["skills"]))
        self.assertNotIn("api_key", data)

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

    def test_feature_pages_share_product_shell_and_complete_navigation(self):
        pages = (
            ("/data-sources", "/data-sources"),
            ("/risk-radar", "/risk-radar"),
            ("/evidence-intake", "/evidence-intake"),
            ("/knowledge-base", "/knowledge-base"),
            ("/action-tracker", "/action-tracker"),
            ("/reports", "/reports"),
            ("/input-lab", "/input-lab"),
        )
        navigation = (
            "/data-sources",
            "/risk-radar",
            "/evidence-intake",
            "/knowledge-base",
            "/action-tracker",
            "/reports",
            "/input-lab",
        )
        for route, active_path in pages:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(200, response.status_code)
                text = response.get_data(as_text=True)
                response.close()
                self.assertIn('href="v2-shell.css"', text)
                self.assertIn('class="nav-list"', text)
                self.assertIn(f'class="is-active" href="{active_path}" aria-current="page"', text)
                for path in navigation:
                    self.assertIn(f'href="{path}"', text)
                self.assertNotIn("V2-P", text)
                self.assertNotIn("STEP ", text)
                self.assertNotIn("phase-note", text)

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
