import json
import tempfile
import unittest
from pathlib import Path

from server import create_app


ROOT = Path(__file__).resolve().parent


class EngineeringFoundationTests(unittest.TestCase):
    def test_v3_routes_are_registered_from_blueprint(self):
        app = create_app()
        names = {rule.endpoint for rule in app.url_map.iter_rules()}
        self.assertIn("v3_operations.agent_capabilities", names)
        self.assertIn("v3_operations.independent_evaluation_framework", names)

    def test_end_to_end_read_only_routes_return_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(output_dir=root, database_path=root / "demo.db")
            app.config["TESTING"] = True
            client = app.test_client()
            for route in ("/health", "/api/agent/capabilities", "/api/evaluation/framework"):
                with self.subTest(route=route):
                    response = client.get(route)
                    self.assertEqual(200, response.status_code)
                    self.assertIsInstance(response.get_json(), dict)
                    self.assertRegex(response.headers["X-Request-ID"], r"^http-[a-f0-9]{12}$")

    def test_dependencies_are_exactly_pinned(self):
        lines = [line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(lines)
        self.assertTrue(all("==" in line and not any(marker in line for marker in (">", "<", "~")) for line in lines))

    def test_ci_declares_windows_linux_and_two_python_versions(self):
        workflow = (ROOT / ".github" / "workflows" / "checks.yml").read_text(encoding="utf-8")
        for expected in ("windows-latest", "ubuntu-latest", '"3.11"', '"3.12"', "python scripts/run_checks.py"):
            self.assertIn(expected, workflow)
        self.assertNotIn("DEEPSEEK_API_KEY", workflow)

    def test_cross_platform_runner_discovers_all_tests(self):
        script = (ROOT / "scripts" / "run_checks.py").read_text(encoding="utf-8")
        self.assertIn('"discover"', script)
        self.assertIn('"test_*.py"', script)
        self.assertIn('"scripts/stdlib_coverage.py"', script)
        self.assertIn('"scripts/type_contract_check.py"', script)
        self.assertIn('"diff", "--check"', script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
