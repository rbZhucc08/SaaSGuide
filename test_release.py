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
        for path, expected in (("/risk-radar.js", "application/javascript"), ("/shell.js", "application/javascript"), ("/v2-shell.css", "text/css"), ("/guide-data.json", "application/json")):
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
                self.assertIn('src="shell.js"', text)
                self.assertIn(f'class="is-active" href="{active_path}" aria-current="page"', text)
                for path in navigation:
                    self.assertIn(f'href="{path}"', text)
                self.assertNotIn("V2-P", text)
                self.assertNotIn("STEP ", text)
                self.assertNotIn("phase-note", text)

    def test_mobile_navigation_helper_only_adjusts_current_navigation_visibility(self):
        script = (Path(__file__).resolve().parent / "shell.js").read_text(encoding="utf-8")
        self.assertIn('querySelector(".is-active")', script)
        self.assertIn("window.innerWidth > 700", script)
        self.assertIn("navigation.scrollTo", script)
        self.assertNotIn("fetch(", script)

    def test_plan_draft_prefill_keeps_both_human_gates(self):
        root = Path(__file__).resolve().parent
        risk_script = (root / "risk-radar.js").read_text(encoding="utf-8")
        action_script = (root / "action-tracker.js").read_text(encoding="utf-8")
        self.assertIn("saasguide.actionDrafts", risk_script)
        self.assertIn("prefill.disabled = !card.dataset.riskDecisionId", risk_script)
        self.assertIn("human_confirmed: $(\"#confirmed\").checked", action_script)
        self.assertIn("risk_decision_id: activeDraft?.risk_decision_id", action_script)

    def test_ui_refinement_preserves_critical_dom_and_api_contracts(self):
        root = Path(__file__).resolve().parent
        contracts = {
            "data-sources.html": ("upload-form", "xlsx-file", "mapping-grid", "confirm-button"),
            "risk-radar.html": ("agent-status", "scan-sample", "candidate-list", "page-message"),
            "action-tracker.html": ("confirmed", "create", "actions"),
        }
        for filename, ids in contracts.items():
            text = (root / filename).read_text(encoding="utf-8")
            for dom_id in ids:
                self.assertIn(f'id="{dom_id}"', text)
        risk_script = (root / "risk-radar.js").read_text(encoding="utf-8")
        for endpoint in ("/api/risk-scans/sample", "/api/risk-scans/latest", "/api/agent/risk-assessment", "/api/risk-scans/decisions"):
            self.assertIn(endpoint, risk_script)

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

    def test_portfolio_release_has_external_reader_documents(self):
        root = Path(__file__).resolve().parent
        required = (
            "LICENSE", "SECURITY.md", "CHANGELOG.md", ".github/workflows/checks.yml",
            "docs/README.md", "docs/product/PRD.md", "docs/product/FEATURE_GUIDE.md",
            "docs/product/USER_GUIDE.md", "docs/architecture/SYSTEM_ARCHITECTURE.md",
            "docs/architecture/AI_AGENT_WORKFLOW.md", "docs/architecture/DATA_AND_TRUST_BOUNDARIES.md",
            "docs/portfolio/CASE_STUDY.md", "docs/portfolio/DEMO_GUIDE.md",
            "docs/portfolio/EVIDENCE_INDEX.md", "docs/portfolio/HR_PROJECT_EXPLAINER.md",
            "docs/portfolio/RELEASE_CHECKLIST.md", "SOURCE_CODE_STUDY_GUIDE.md",
            "docs/quality/TEST_STRATEGY.md", "docs/quality/EVALUATION_REPORT.md",
            "docs/quality/KNOWN_LIMITATIONS.md",
        )
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((root / relative).is_file(), relative)
        source_guide = (root / "SOURCE_CODE_STUDY_GUIDE.md").read_text(encoding="utf-8")
        self.assertNotIn("/D:/CodexProjects", source_guide)
        self.assertNotIn("当前 5 条模拟风险", source_guide)
        self.assertIn("HR_PROJECT_EXPLAINER.md", source_guide)

    def test_readme_reports_current_fixed_benchmark_without_claiming_business_accuracy(self):
        root = Path(__file__).resolve().parent
        readme = (root / "README.md").read_text(encoding="utf-8")
        benchmark = json.loads((root / "data/evaluation/company_scenario_expected.json").read_text(encoding="utf-8"))
        self.assertEqual(30, len(benchmark["cases"]))
        for text in ("TP=119", "FP=4", "FN=18", "Precision=96.75%", "Recall=86.86%"):
            self.assertIn(text, readme)
        self.assertIn("不是企业准确率", readme)
        self.assertIn("不是多 Agent 系统", readme)

    def test_github_workflow_reuses_cross_platform_check_runner(self):
        root = Path(__file__).resolve().parent
        workflow = (root / ".github/workflows/checks.yml").read_text(encoding="utf-8")
        self.assertIn("windows-latest", workflow)
        self.assertIn("ubuntu-latest", workflow)
        self.assertIn("python scripts/run_checks.py", workflow)
        self.assertNotIn("DEEPSEEK_API_KEY", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
