import tempfile
import unittest
from pathlib import Path

from server import create_app
from services.evaluation.company_benchmark import CompanyBenchmarkError, run_company_benchmark


ROOT = Path(__file__).resolve().parent
SEED = ROOT / "data" / "demo" / "nebula_company_seed.json"
EXPECTED = ROOT / "data" / "evaluation" / "company_scenario_expected.json"


class CompanyBenchmarkTests(unittest.TestCase):
    def test_fixed_benchmark_exposes_real_rule_gaps(self):
        result = run_company_benchmark(SEED, EXPECTED)
        self.assertEqual(30, result["case_count"])
        self.assertEqual(6, result["company_count"])
        self.assertEqual(119, result["overall"]["true_positive"])
        self.assertEqual(4, result["overall"]["false_positive"])
        self.assertEqual(18, result["overall"]["false_negative"])
        self.assertEqual(96.75, result["overall"]["precision_percent"])
        self.assertEqual(86.86, result["overall"]["recall_percent"])

    def test_severity_and_company_groups_are_reported(self):
        result = run_company_benchmark(SEED, EXPECTED)
        self.assertEqual(6, len(result["by_company"]))
        self.assertEqual(6, len(result["by_industry"]))
        self.assertEqual(4, len(result["by_risk_type"]))
        self.assertGreater(result["overall"]["severity_total"], 0)
        self.assertGreaterEqual(result["overall"]["severity_match_percent"], 0)

    def test_ai_expectations_are_not_reported_as_actual_runs(self):
        result = run_company_benchmark(SEED, EXPECTED)
        self.assertEqual(6, result["expected_ask_cases"])
        self.assertEqual(24, result["expected_plan_cases"])
        self.assertEqual(0, result["deepseek_runs"])
        self.assertEqual("not_run", result["deepseek_status"])

    def test_missing_expected_file_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(CompanyBenchmarkError) as raised:
                run_company_benchmark(SEED, Path(temporary) / "missing.json")
        self.assertEqual("benchmark_file_not_found", raised.exception.code)


class CompanyBenchmarkApiTests(unittest.TestCase):
    def test_api_reads_versioned_seed_instead_of_runtime_company_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(
                output_dir=root / "generated",
                company_data_file=root / "runtime-company.json",
                company_seed_file=SEED,
                company_benchmark_file=EXPECTED,
            )
            app.config["TESTING"] = True
            client = app.test_client()
            client.post("/api/company-data/clear", json={"confirmed": True})
            response = client.get("/api/evaluation/company-benchmark")
            self.assertEqual(200, response.status_code)
            self.assertEqual("fixed_differentiated_simulated_benchmark", response.get_json()["scope"])
            self.assertEqual(30, response.get_json()["case_count"])

    def test_api_returns_readable_missing_file_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = create_app(company_seed_file=SEED, company_benchmark_file=root / "missing.json")
            app.config["TESTING"] = True
            response = app.test_client().get("/api/evaluation/company-benchmark")
            self.assertEqual(500, response.status_code)
            self.assertEqual("benchmark_file_not_found", response.get_json()["code"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
