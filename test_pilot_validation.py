"""Tests for phase-eleven external pilot evidence safeguards."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from server import create_app
from services.validation.pilot import PilotValidationError, analyze_study, status_from_file


def valid_study() -> dict:
    return {
        "schema_version": "saasguide-pilot-v1",
        "study_id": "pilot-local-001",
        "scenario_id": "risk-to-action-review",
        "authorization": {"authorized": True, "deidentified": True, "confirmed_by_project_owner": True},
        "participants": [{
            "participant_id": "participant-001",
            "consent_confirmed": True,
            "role_category": "项目协同",
            "baseline": {"task_minutes": 18},
            "trial": {"task_minutes": 13},
            "recommendation_decisions": [
                {"recommendation_id": "rec-001", "decision": "accepted", "reason_category": "useful_as_written"},
                {"recommendation_id": "rec-002", "decision": "modified", "reason_category": "needs_context"},
                {"recommendation_id": "rec-003", "decision": "rejected", "reason_category": "wrong_priority"},
            ],
        }],
    }


class PilotValidationTests(unittest.TestCase):
    def test_missing_file_stays_external_evidence_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = status_from_file(Path(temporary) / "missing.json")
        self.assertEqual("external_evidence_required", result["status"])
        self.assertEqual(0, result["participant_count"])

    def test_valid_study_returns_descriptive_metrics(self):
        result = analyze_study(valid_study())
        self.assertEqual("pilot_evidence_available", result["status"])
        self.assertEqual({"accepted": 1, "modified": 1, "rejected": 1, "total": 3}, result["recommendation_decisions"])
        self.assertEqual(0.3333, result["acceptance_rate"])
        self.assertIn("不证明因果关系", result["interpretation"])

    def test_identity_fields_are_rejected(self):
        document = valid_study()
        document["participants"][0]["email"] = "redacted"
        with self.assertRaisesRegex(PilotValidationError, "禁止的身份字段"):
            analyze_study(document)

    def test_missing_authorization_is_rejected(self):
        document = valid_study()
        document["authorization"]["authorized"] = False
        with self.assertRaisesRegex(PilotValidationError, "已获授权"):
            analyze_study(document)

    def test_status_endpoint_and_page_expose_pending_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = create_app(output_dir=Path(temporary))
            app.config["TESTING"] = True
            client = app.test_client()
            status = client.get("/api/validation/status")
            page = client.get("/validation")
            status_code = status.status_code
            status_data = status.get_json()
            page_code = page.status_code
            page_text = page.get_data(as_text=True)
            status.close()
            page.close()
        self.assertEqual(200, status_code)
        self.assertEqual("external_evidence_required", status_data["status"])
        self.assertEqual(200, page_code)
        self.assertIn("没有真实参与者和授权数据时", page_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
