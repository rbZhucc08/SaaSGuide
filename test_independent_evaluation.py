import json
import tempfile
import unittest
from pathlib import Path

from services.evaluation.independent import (
    EvaluationError,
    adjudicate,
    agreement_report,
    component_metrics,
    framework_status,
    load_blind_package,
    validate_annotation_set,
    validate_blind_cases,
)
from server import create_app


PROJECT_DIR = Path(__file__).resolve().parent
DEVELOPMENT = PROJECT_DIR / "data" / "evaluation" / "v3" / "development_blind.json"
HOLDOUT = PROJECT_DIR / "data" / "evaluation" / "v3" / "holdout_blind.json"


def label(case_id, risk="positive", severity="high", decision="PLAN"):
    return {
        "case_id": case_id,
        "risk_label": risk,
        "severity": severity,
        "desired_decision": decision,
        "required_doc_ids": ["POL-1"],
        "citation_supported": "yes",
        "action_executable": "yes",
        "error_tags": ["none"],
        "rationale": "根据案例中的明确事实判断。",
    }


class IndependentEvaluationTests(unittest.TestCase):
    def test_bundled_blind_packages_have_no_answers_or_predictions(self):
        development = load_blind_package(DEVELOPMENT, "development")
        holdout = load_blind_package(HOLDOUT, "holdout")
        self.assertEqual(4, len(development["cases"]))
        self.assertEqual(4, len(holdout["cases"]))
        serialized = json.dumps([development, holdout])
        self.assertNotIn("ground_truth", serialized)
        self.assertNotIn("prediction", serialized)

    def test_blind_package_rejects_prediction_field(self):
        with self.assertRaisesRegex(EvaluationError, "系统预测字段"):
            validate_blind_cases([{"case_id": "X", "split": "development", "facts": ["a"], "prediction": True}])

    def test_annotation_requires_every_case_and_rationale(self):
        payload = {"annotator_id": "A", "labels": [label("A")]}
        self.assertEqual(payload, validate_annotation_set(payload, {"A"}))
        payload["labels"][0]["rationale"] = ""
        with self.assertRaisesRegex(EvaluationError, "判断依据"):
            validate_annotation_set(payload, {"A"})

    def test_two_distinct_annotators_report_disagreement_and_adjudicate(self):
        first = {"annotator_id": "A", "labels": [label("X")]}
        second_label = label("X", risk="negative", severity="not_applicable", decision="ASK")
        second = {"annotator_id": "B", "labels": [second_label]}
        report = agreement_report(first, second)
        self.assertTrue(report["requires_adjudication"])
        resolution = label("X", severity="medium")
        self.assertEqual([resolution], adjudicate(first, second, [resolution]))

    def test_same_annotator_is_not_independent(self):
        first = {"annotator_id": "A", "labels": [label("X")]}
        with self.assertRaisesRegex(EvaluationError, "不同标注者"):
            agreement_report(first, first)

    def test_component_metrics_are_separated(self):
        labels = [label("A"), label("B", risk="negative", severity="not_applicable", decision="ASK")]
        predictions = [
            {"case_id": "A", "rule_positive": True, "retrieved_doc_ids": ["POL-1"], "model_output_valid": True},
            {"case_id": "B", "rule_positive": True, "retrieved_doc_ids": [], "model_output_valid": False},
        ]
        metrics = component_metrics(predictions, labels)
        self.assertEqual({"tp": 1, "fp": 1, "fn": 0, "precision": 0.5, "recall": 1.0, "f1": 0.6667}, metrics["rules"])
        self.assertEqual(0.5, metrics["retrieval_recall"])
        self.assertEqual(0.5, metrics["model_structure_pass_rate"])

    def test_framework_status_truthfully_reports_zero_annotators(self):
        with tempfile.TemporaryDirectory() as temporary:
            status = framework_status(DEVELOPMENT, HOLDOUT, Path(temporary))
        self.assertEqual(0, status["annotator_count"])
        self.assertFalse(status["external_annotation_complete"])
        self.assertIn("外部标注待完成", status["status"])

    def test_framework_api_exposes_status_without_claiming_human_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(output_dir=root, database_path=root / "demo.db")
            app.config["TESTING"] = True
            response = app.test_client().get("/api/evaluation/framework")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.get_json()["annotator_count"])
        self.assertEqual("独立评测框架完成，外部标注待完成", response.get_json()["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
