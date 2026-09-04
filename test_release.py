import unittest

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
        for path in ("/v2", "/health"):
            response = self.client.get(path)
            self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
            self.assertEqual("DENY", response.headers["X-Frame-Options"])
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertIn("microphone=()", response.headers["Permissions-Policy"])
            response.close()

    def test_v2_overview_links_all_stages(self):
        response = self.client.get("/v2")
        text = response.get_data(as_text=True)
        response.close()
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
