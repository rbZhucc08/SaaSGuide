import copy
import json
import tempfile
import unittest
from pathlib import Path

from server import create_app
from services.risk_rules.deterministic_scan import (
    RiskScanError,
    candidate_id_for,
    evaluate_candidates,
    save_human_decision,
    scan_project,
)


PROJECT_DIR = Path(__file__).resolve().parent
TIMELINE_FILE = PROJECT_DIR / "data" / "evaluation" / "phase2_project_timeline.json"
EXPECTED_FILE = PROJECT_DIR / "data" / "evaluation" / "phase2_expected_results.json"


class DeterministicRiskRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(TIMELINE_FILE.read_text(encoding="utf-8"))
        self.expected = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))

    @staticmethod
    def decision_payload(decision: str = "watch", note: str = "") -> dict[str, str]:
        source_id = "source-test"
        candidate_key = "project-001:T-002:schedule_delay"
        return {
            "candidate_id": candidate_id_for(source_id, candidate_key),
            "candidate_key": candidate_key,
            "source_id": source_id,
            "decision": decision,
            "note": note,
        }

    def test_fixed_evaluation_has_expected_candidates_and_metrics(self) -> None:
        result = scan_project(self.document)
        evaluation = evaluate_candidates(result["candidates"], self.expected)
        self.assertEqual(6, result["summary"]["candidate_count"])
        self.assertEqual(5, evaluation["true_positive"])
        self.assertEqual(1, evaluation["false_positive"])
        self.assertEqual(1, evaluation["false_negative"])
        self.assertEqual(83.33, evaluation["precision_percent"])
        self.assertEqual(83.33, evaluation["recall_percent"])

    def test_overlapping_schedule_rules_are_deduplicated(self) -> None:
        result = scan_project(self.document)
        matches = [item for item in result["candidates"] if item["candidate_key"] == "project-001:T-002:schedule_delay"]
        self.assertEqual(1, len(matches))
        self.assertEqual({"overdue_incomplete", "overdue_low_progress"}, set(matches[0]["trigger_rules"]))

    def test_candidate_evidence_keeps_original_source_row(self) -> None:
        result = scan_project(self.document)
        candidate = next(item for item in result["candidates"] if item["candidate_key"] == "project-001:T-004:dependency_risk")
        self.assertTrue(candidate["evidence"])
        self.assertTrue(all(item["source_row"] == 5 for item in candidate["evidence"]))
        self.assertEqual(["T-003"], candidate["evidence"][0]["value"])

    def test_completed_task_does_not_create_overdue_candidate(self) -> None:
        result = scan_project(self.document)
        self.assertFalse(any(item["task_id"] == "T-001" for item in result["candidates"]))

    def test_due_soon_rule_includes_three_day_boundary(self) -> None:
        result = scan_project(self.document, "2026-09-13")
        self.assertTrue(any(item["candidate_key"] == "project-001:T-006:schedule_pressure" for item in result["candidates"]))

    def test_invalid_project_structure_stops_scan(self) -> None:
        with self.assertRaisesRegex(RiskScanError, "project_id"):
            scan_project({"project": {}, "tasks": []})

    def test_invalid_scan_date_stops_scan(self) -> None:
        with self.assertRaisesRegex(RiskScanError, "YYYY-MM-DD"):
            scan_project(self.document, "09/12/2026")

    def test_duplicate_task_id_stops_scan(self) -> None:
        document = copy.deepcopy(self.document)
        document["tasks"].append(copy.deepcopy(document["tasks"][0]))
        with self.assertRaisesRegex(RiskScanError, "重复"):
            scan_project(document)

    def test_all_human_decisions_can_be_appended(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "decisions.jsonl"
            for decision in ("confirm", "watch", "reject", "false_positive"):
                save_human_decision(
                    path,
                    self.decision_payload(decision, "固定测试"),
                    recorded_at="2026-09-12T10:00:00+08:00",
                )
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(4, len(records))
            self.assertEqual({"confirm", "watch", "reject", "false_positive"}, {item["decision"] for item in records})

    def test_invalid_human_decision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RiskScanError, "必须是"):
                save_human_decision(
                    Path(temporary) / "decisions.jsonl",
                    self.decision_payload("close"),
                )

    def test_overlong_human_note_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RiskScanError, "500"):
                save_human_decision(
                    Path(temporary) / "decisions.jsonl",
                    self.decision_payload("watch", "字" * 501),
                )

    def test_mismatched_candidate_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = self.decision_payload()
            payload["candidate_key"] = "project-001:T-003:schedule_delay"
            with self.assertRaisesRegex(RiskScanError, "不一致"):
                save_human_decision(Path(temporary) / "decisions.jsonl", payload)

    def test_unassessed_prediction_is_not_counted_as_false_positive(self) -> None:
        result = scan_project(self.document, "2026-09-13")
        evaluation = evaluate_candidates(result["candidates"], self.expected)
        self.assertIn("project-001:T-006:schedule_pressure", evaluation["unassessed_predicted_keys"])
        self.assertNotIn("project-001:T-006:schedule_pressure", evaluation["false_positive_keys"])


class RiskScanApiTests(unittest.TestCase):
    def make_app(self, root: Path):
        app = create_app(
            pending_import_dir=root / "pending",
            raw_data_dir=root / "raw",
            normalized_data_dir=root / "normalized",
            risk_decision_file=root / "generated" / "risk-decisions.jsonl",
        )
        app.config["TESTING"] = True
        return app

    def test_sample_endpoint_returns_candidates_and_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            response = self.make_app(Path(temporary)).test_client().post("/api/risk-scans/sample")
            self.assertEqual(200, response.status_code)
            data = response.get_json()
            self.assertTrue(data["sample_mode"])
            self.assertEqual(6, data["summary"]["candidate_count"])
            self.assertEqual(83.33, data["evaluation"]["precision_percent"])

    def test_latest_endpoint_scans_phase1_normalized_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            normalized = root / "normalized"
            normalized.mkdir()
            normalized.joinpath("import-test.json").write_text(TIMELINE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
            response = self.make_app(root).test_client().post("/api/risk-scans/latest", json={"as_of": "2026-09-12"})
            self.assertEqual(200, response.status_code)
            data = response.get_json()
            self.assertFalse(data["sample_mode"])
            self.assertIsNone(data["evaluation"])
            self.assertEqual(6, data["summary"]["candidate_count"])

    def test_latest_endpoint_explains_missing_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            response = self.make_app(Path(temporary)).test_client().post("/api/risk-scans/latest", json={})
            self.assertEqual(404, response.status_code)
            self.assertEqual("normalized_import_not_found", response.get_json()["code"])

    def test_decision_endpoint_persists_audit_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = self.make_app(root).test_client().post(
                "/api/risk-scans/decisions",
                json={
                    "candidate_id": candidate_id_for("source-test", "project-001:T-002:schedule_delay"),
                    "candidate_key": "project-001:T-002:schedule_delay",
                    "source_id": "source-test",
                    "decision": "confirm",
                    "note": "证据已核对",
                },
            )
            self.assertEqual(201, response.status_code)
            path = root / "generated" / "risk-decisions.jsonl"
            record = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual("confirm", record["decision"])
            self.assertEqual("证据已核对", record["note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
