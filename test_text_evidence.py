"""V2-P3 text evidence tests."""

import tempfile
import unittest
from pathlib import Path

from services.ingestion.text_evidence import TextEvidenceError, parse_evidence, save_review


ROOT = Path(__file__).resolve().parent


class TextEvidenceTests(unittest.TestCase):
    def test_docx_fixture_preserves_locations_and_injection(self):
        path = ROOT / "data" / "documents" / "phase3_project_weekly_update.docx"
        result = parse_evidence(path.read_bytes(), path.name)
        self.assertEqual(".docx", result["source"]["extension"])
        self.assertGreaterEqual(result["summary"]["explicit_fact_count"], 3)
        self.assertGreaterEqual(result["summary"]["needs_confirmation_count"], 2)
        self.assertEqual(1, result["summary"]["suspicious_text_count"])
        suspicious = next(c for c in result["candidates"] if c["category"] == "suspicious_instruction_text")
        self.assertIn("忽略系统规则", suspicious["quote"])
        self.assertRegex(suspicious["source_location"], r"^(段落|表格)")
        self.assertEqual("not_called", result["model_status"])

    def test_utf8_and_gbk_text_are_supported(self):
        source = "待确认：责任人是否为陈宁"
        for encoding in ("utf-8-sig", "gbk"):
            result = parse_evidence(source.encode(encoding), "note.txt")
            self.assertEqual(1, result["summary"]["needs_confirmation_count"])

    def test_unsupported_extension_is_rejected(self):
        with self.assertRaises(TextEvidenceError) as raised:
            parse_evidence(b"data", "note.pdf")
        self.assertEqual("extension_not_allowed", raised.exception.code)

    def test_human_review_is_audited_without_writeback(self):
        preview = parse_evidence("待确认：截止日期".encode(), "note.md")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "reviews.jsonl"
            record = save_review(target, preview, {
                "reviewer": "测试核对人",
                "decisions": [{"candidate_id": preview["candidates"][0]["candidate_id"], "decision": "accept", "note": "已核对"}],
            })
            self.assertEqual("evidence_only_no_task_or_risk_writeback", record["effect"])
            self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
