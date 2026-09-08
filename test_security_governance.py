"""V3 phase 8 security and data-governance tests."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from server import create_app
from services.ingestion.text_evidence import parse_evidence
from services.security.governance import (
    LocalRateLimiter,
    SecurityInputError,
    assess_sensitive_text,
    inspect_office_archive,
    readiness_status,
)


class SecurityGovernanceTests(unittest.TestCase):
    def test_sensitive_scan_returns_categories_without_values(self) -> None:
        result = assess_sensitive_text(["联系 alice@example.com，手机 13812345678，secret=abcdefghijklmnop"])
        self.assertTrue(result["sensitive_data_detected"])
        self.assertEqual({"api_token_like", "china_mobile", "email"}, {item["category"] for item in result["findings"]})
        self.assertNotIn("alice@example.com", str(result))
        self.assertFalse(result["real_data_allowed"])

    def test_text_evidence_includes_security_warning(self) -> None:
        result = parse_evidence("负责人邮箱 alice@example.com".encode(), "note.txt")
        self.assertTrue(result["security"]["sensitive_data_detected"])
        self.assertNotIn("alice@example.com", str(result["security"]))

    def test_archive_expansion_limit_is_enforced(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("large.xml", b"x" * (25 * 1024 * 1024 + 1))
        with self.assertRaises(SecurityInputError) as raised:
            inspect_office_archive(buffer.getvalue(), "large.docx")
        self.assertEqual("archive_expansion_limit", raised.exception.code)

    def test_local_rate_limiter_resets_after_window(self) -> None:
        now = [0.0]
        limiter = LocalRateLimiter(limit=2, window_seconds=10, clock=lambda: now[0])
        self.assertTrue(limiter.allow("local")[0])
        self.assertTrue(limiter.allow("local")[0])
        self.assertFalse(limiter.allow("local")[0])
        now[0] = 10.0
        self.assertTrue(limiter.allow("local")[0])

    def test_readiness_truthfully_blocks_real_data(self) -> None:
        status = readiness_status()
        self.assertEqual("blocked_for_real_data", status["status"])
        self.assertFalse(status["real_data_allowed"])
        self.assertIn("authentication", status["blocking_controls"])
        self.assertIn("true_tenant_isolation", status["blocking_controls"])

    def test_security_readiness_endpoint_and_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(output_dir=root, database_path=root / "demo.db")
            app.config["TESTING"] = True
            response = app.test_client().get("/api/security/readiness")
            self.assertEqual(200, response.status_code)
            self.assertEqual("blocked_for_real_data", response.get_json()["status"])
            self.assertEqual("DENY", response.headers["X-Frame-Options"])

    def test_data_source_page_displays_real_data_gate(self) -> None:
        html = Path("data-sources.html").read_text(encoding="utf-8")
        script = Path("data-sources.js").read_text(encoding="utf-8")
        self.assertIn("真实数据当前被安全闸门阻断", html)
        self.assertIn("/api/security/readiness", script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
