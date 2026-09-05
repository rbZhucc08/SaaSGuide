"""Offline tests for SaaSGuide V2 Phase 1 XLSX ingestion."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from server import create_app
from services.ingestion.xlsx_import import (
    IngestionError,
    MAX_XLSX_BYTES,
    confirm_import,
    parse_xlsx,
    save_pending_upload,
    suggest_mapping,
    validate_and_normalize,
)


PROJECT_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = PROJECT_DIR / "data" / "samples"
EXPECTED_FILE = PROJECT_DIR / "data" / "evaluation" / "phase1_expected_results.json"


class XlsxImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = json.loads(EXPECTED_FILE.read_text(encoding="utf-8"))

    def evaluate_sample(self, filename: str):
        parsed = parse_xlsx(SAMPLE_DIR / filename)
        mapping = suggest_mapping(parsed.headers)
        return parsed, mapping, validate_and_normalize(parsed, mapping)

    def test_valid_sample_matches_ground_truth(self) -> None:
        parsed, mapping, result = self.evaluate_sample("valid_project_tasks_cn.xlsx")
        self.assertTrue(result["valid"])
        self.assertEqual(6, result["summary"]["task_count"])
        self.assertEqual(7, result["summary"]["dependency_count"])
        self.assertEqual("项目编号", mapping["project_id"])
        self.assertEqual("负责人", mapping["owner"])
        self.assertEqual(100, result["tasks"][0]["progress_percent"])
        self.assertEqual(parsed.sha256, parse_xlsx(SAMPLE_DIR / "valid_project_tasks_cn.xlsx").sha256)

    def test_missing_owner_reports_original_row(self) -> None:
        _parsed, _mapping, result = self.evaluate_sample("invalid_missing_owner.xlsx")
        errors = [item for item in result["errors"] if item["code"] == "required_value_missing"]
        self.assertFalse(result["valid"])
        self.assertEqual([4], [item["row"] for item in errors])
        self.assertEqual("owner", errors[0]["field"])

    def test_invalid_dates_report_both_failure_types(self) -> None:
        _parsed, _mapping, result = self.evaluate_sample("invalid_dates.xlsx")
        by_code = {item["code"]: item["row"] for item in result["errors"]}
        self.assertEqual(2, by_code["invalid_date"])
        self.assertEqual(3, by_code["date_order"])

    def test_invalid_dependencies_are_blocked(self) -> None:
        _parsed, _mapping, result = self.evaluate_sample("invalid_dependencies.xlsx")
        by_code = {item["code"]: item["row"] for item in result["errors"]}
        self.assertEqual(4, by_code["duplicate_task_id"])
        self.assertEqual(5, by_code["self_dependency"])
        self.assertEqual(6, by_code["dependency_not_found"])

    def test_missing_required_mapping_is_blocked(self) -> None:
        parsed = parse_xlsx(SAMPLE_DIR / "valid_project_tasks_cn.xlsx")
        mapping = suggest_mapping(parsed.headers)
        mapping["owner"] = ""
        result = validate_and_normalize(parsed, mapping)
        self.assertTrue(any(item["code"] == "mapping_required" for item in result["errors"]))

    def test_free_text_unknown_column_returns_clear_error(self) -> None:
        parsed = parse_xlsx(SAMPLE_DIR / "valid_project_tasks_cn.xlsx")
        mapping = suggest_mapping(parsed.headers)
        mapping["owner"] = "我自己输入的负责人列"
        result = validate_and_normalize(parsed, mapping)
        unknown = [item for item in result["errors"] if item["code"] == "mapping_unknown_column"]
        self.assertEqual(1, len(unknown))
        self.assertIn("我自己输入的负责人列", unknown[0]["message"])
        self.assertFalse(any(item["code"] == "mapping_required" and item.get("field") == "owner" for item in result["errors"]))

    def test_mapping_page_uses_free_text_inputs_with_header_suggestions(self) -> None:
        script = (PROJECT_DIR / "data-sources.js").read_text(encoding="utf-8")
        self.assertIn('input.type = "text"', script)
        self.assertIn('document.createElement("datalist")', script)
        self.assertNotIn('querySelectorAll("select[data-field]")', script)

    def test_one_source_column_cannot_map_twice(self) -> None:
        parsed = parse_xlsx(SAMPLE_DIR / "valid_project_tasks_cn.xlsx")
        mapping = suggest_mapping(parsed.headers)
        mapping["task_name"] = mapping["task_id"]
        result = validate_and_normalize(parsed, mapping)
        self.assertTrue(any(item["code"] == "mapping_duplicate_source" for item in result["errors"]))

    def test_confirm_saves_raw_and_normalized_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = (SAMPLE_DIR / "valid_project_tasks_cn.xlsx").read_bytes()
            preview_id, pending_path = save_pending_upload(content, "valid_project_tasks_cn.xlsx", root / "pending")
            parsed = parse_xlsx(pending_path, "valid_project_tasks_cn.xlsx")
            result = confirm_import(preview_id, suggest_mapping(parsed.headers), root / "pending", root / "raw", root / "normalized")
            normalized_files = list((root / "normalized").glob("*.json"))
            raw_files = list((root / "raw").glob("*.xlsx"))
            self.assertEqual(1, len(normalized_files))
            self.assertEqual(1, len(raw_files))
            saved = json.loads(normalized_files[0].read_text(encoding="utf-8"))
            self.assertEqual(result["source"]["sha256"], saved["source"]["sha256"])
            self.assertEqual(6, saved["summary"]["task_count"])
            self.assertEqual(2, saved["tasks"][0]["source_row"])

    def test_duplicate_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = (SAMPLE_DIR / "valid_project_tasks_cn.xlsx").read_bytes()
            first_id, first_path = save_pending_upload(content, "tasks.xlsx", root / "pending")
            first_parsed = parse_xlsx(first_path, "tasks.xlsx")
            mapping = suggest_mapping(first_parsed.headers)
            confirm_import(first_id, mapping, root / "pending", root / "raw", root / "normalized")
            second_id, _ = save_pending_upload(content, "tasks.xlsx", root / "pending")
            with self.assertRaisesRegex(IngestionError, "已经导入"):
                confirm_import(second_id, mapping, root / "pending", root / "raw", root / "normalized")

    def test_non_xlsx_name_is_rejected_before_save(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(IngestionError, "只支持"):
                save_pending_upload(b"not-an-xlsx", "tasks.xls", Path(temporary))

    def test_file_over_two_megabytes_is_rejected_before_save(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(IngestionError, "2 MB"):
                save_pending_upload(
                    b"x" * (MAX_XLSX_BYTES + 1),
                    "oversized.xlsx",
                    Path(temporary),
                )

    def test_preview_and_confirm_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                pending_import_dir=root / "pending",
                raw_data_dir=root / "raw",
                normalized_data_dir=root / "normalized",
            )
            app.config["TESTING"] = True
            client = app.test_client()
            content = (SAMPLE_DIR / "valid_project_tasks_cn.xlsx").read_bytes()
            preview_response = client.post(
                "/api/imports/preview",
                data={"file": (io.BytesIO(content), "valid_project_tasks_cn.xlsx")},
                content_type="multipart/form-data",
            )
            self.assertEqual(200, preview_response.status_code)
            preview = preview_response.get_json()
            self.assertTrue(preview["valid"])
            confirm_response = client.post(
                "/api/imports/confirm",
                json={"preview_id": preview["preview_id"], "mapping": preview["mapping"]},
            )
            self.assertEqual(201, confirm_response.status_code)
            self.assertEqual(6, confirm_response.get_json()["summary"]["task_count"])

    def test_invalid_sample_endpoint_never_saves_formal_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                pending_import_dir=root / "pending",
                raw_data_dir=root / "raw",
                normalized_data_dir=root / "normalized",
            )
            app.config["TESTING"] = True
            client = app.test_client()
            content = (SAMPLE_DIR / "invalid_missing_owner.xlsx").read_bytes()
            response = client.post(
                "/api/imports/preview",
                data={"file": (io.BytesIO(content), "invalid_missing_owner.xlsx")},
                content_type="multipart/form-data",
            )
            self.assertEqual(200, response.status_code)
            preview = response.get_json()
            self.assertFalse(preview["valid"])
            confirm_response = client.post(
                "/api/imports/confirm",
                json={"preview_id": preview["preview_id"], "mapping": preview["mapping"]},
            )
            self.assertEqual(400, confirm_response.status_code)
            self.assertFalse((root / "raw").exists())
            self.assertFalse((root / "normalized").exists())

    def test_bundled_sample_endpoint_returns_real_xlsx_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                pending_import_dir=root / "pending",
                raw_data_dir=root / "raw",
                normalized_data_dir=root / "normalized",
            )
            app.config["TESTING"] = True
            response = app.test_client().post(
                "/api/imports/sample/invalid_dates.xlsx"
            )
            self.assertEqual(200, response.status_code)
            data = response.get_json()
            self.assertTrue(data["sample_mode"])
            self.assertFalse(data["valid"])
            self.assertTrue(any(item["code"] == "invalid_date" for item in data["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
