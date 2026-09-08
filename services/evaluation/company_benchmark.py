"""Evaluate deterministic risk rules against the fixed multi-company seed.

The expected labels are authored synthetic fixtures. They are useful for
regression and rule-gap discovery, but are not expert-labelled production data.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from services.risk_rules.deterministic_scan import scan_project


class CompanyBenchmarkError(ValueError):
    """Raised when the fixed benchmark cannot be evaluated."""

    def __init__(self, code: str, message: str, status: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CompanyBenchmarkError("benchmark_file_not_found", f"缺少{label}：{path.name}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise CompanyBenchmarkError("benchmark_file_invalid", f"{label}无法读取：{path.name}") from error
    if not isinstance(value, dict):
        raise CompanyBenchmarkError("benchmark_file_invalid", f"{label}必须是 JSON 对象")
    return value


def _metrics(tp: int, fp: int, fn: int, severity_match: int, severity_total: int) -> dict[str, Any]:
    precision = tp / (tp + fp) * 100 if tp + fp else 0.0
    recall = tp / (tp + fn) * 100 if tp + fn else 0.0
    severity_rate = severity_match / severity_total * 100 if severity_total else 0.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision_percent": round(precision, 2),
        "recall_percent": round(recall, 2),
        "severity_match": severity_match,
        "severity_total": severity_total,
        "severity_match_percent": round(severity_rate, 2),
    }


def _new_bucket() -> dict[str, int]:
    return {"tp": 0, "fp": 0, "fn": 0, "severity_match": 0, "severity_total": 0}


def _finish_groups(groups: dict[str, dict[str, int]], key_name: str) -> list[dict[str, Any]]:
    return [
        {key_name: name, **_metrics(value["tp"], value["fp"], value["fn"], value["severity_match"], value["severity_total"])}
        for name, value in sorted(groups.items())
    ]


def run_company_benchmark(seed_path: Path, expected_path: Path) -> dict[str, Any]:
    """Run the fixed rules without invoking DeepSeek or reading mutable runtime data."""
    seed = _read_object(seed_path, "模拟公司数据")
    benchmark = _read_object(expected_path, "跨公司标准答案")
    companies = seed.get("companies")
    cases = benchmark.get("cases")
    if not isinstance(companies, list) or not isinstance(cases, list):
        raise CompanyBenchmarkError("benchmark_file_invalid", "评测数据缺少 companies 或 cases 列表")
    if seed.get("dataset_revision") != benchmark.get("dataset_revision"):
        raise CompanyBenchmarkError("benchmark_revision_mismatch", "模拟数据与标准答案版本不一致")

    company_by_id = {str(item.get("company_id")): item for item in companies if isinstance(item, dict)}
    case_by_project = {str(item.get("project_id")): item for item in cases if isinstance(item, dict)}
    if len(case_by_project) != len(cases):
        raise CompanyBenchmarkError("benchmark_file_invalid", "标准答案含重复或无效项目编号")

    overall = _new_bucket()
    group_specs = {
        "by_company": (defaultdict(_new_bucket), "company_name"),
        "by_industry": (defaultdict(_new_bucket), "industry"),
        "by_project_type": (defaultdict(_new_bucket), "project_type"),
        "by_risk_type": (defaultdict(_new_bucket), "risk_type"),
    }
    false_positives: list[dict[str, str]] = []
    false_negatives: list[dict[str, str]] = []
    severity_mismatches: list[dict[str, str]] = []

    def add(group: dict[str, int], field: str, amount: int = 1) -> None:
        group[field] += amount

    def add_case_groups(case: dict[str, Any], field: str, amount: int = 1) -> None:
        for group_name, (group, key_name) in group_specs.items():
            if group_name == "by_risk_type":
                continue
            add(group[str(case.get(key_name) or "未分类")], field, amount)

    evaluated = 0
    for company in companies:
        company_id = str(company.get("company_id") or "")
        for project in company.get("projects") or []:
            project_id = str(project.get("project_id") or "")
            case = case_by_project.get(project_id)
            if case is None or case.get("company_id") != company_id:
                raise CompanyBenchmarkError("benchmark_case_mismatch", f"项目 {project_id} 缺少匹配标准答案")
            document = {
                "as_of": benchmark.get("as_of"),
                "source": {"source_id": f"benchmark-{company_id}-{project_id}", "source_name": "固定跨公司评测"},
                "company": company,
                "project": {"project_id": project_id, "project_name": project.get("project_name")},
                "tasks": project.get("tasks"),
            }
            result = scan_project(document, benchmark.get("as_of"))
            predicted = {item["candidate_key"]: item for item in result["candidates"]}
            positives = set(case.get("positive_candidate_keys") or [])
            negatives = set(case.get("negative_candidate_keys") or [])
            expected_severity = case.get("expected_severity_by_key") or {}
            tp_keys = predicted.keys() & positives
            fp_keys = predicted.keys() & negatives
            fn_keys = positives - predicted.keys()

            for field, keys in (("tp", tp_keys), ("fp", fp_keys), ("fn", fn_keys)):
                add(overall, field, len(keys)); add_case_groups(case, field, len(keys))
                risk_groups = group_specs["by_risk_type"][0]
                for key in keys:
                    add(risk_groups[key.rsplit(":", 1)[-1]], field)

            for key in sorted(tp_keys):
                add(overall, "severity_total"); add_case_groups(case, "severity_total")
                add(group_specs["by_risk_type"][0][key.rsplit(":", 1)[-1]], "severity_total")
                actual = str(predicted[key].get("severity")); expected = str(expected_severity.get(key))
                if actual == expected:
                    add(overall, "severity_match"); add_case_groups(case, "severity_match")
                    add(group_specs["by_risk_type"][0][key.rsplit(":", 1)[-1]], "severity_match")
                else:
                    severity_mismatches.append({"company": str(case["company_name"]), "project": str(case["project_name"]), "candidate_key": key, "expected": expected, "actual": actual})
            for key in sorted(fp_keys):
                false_positives.append({"company": str(case["company_name"]), "project": str(case["project_name"]), "candidate_key": key})
            for key in sorted(fn_keys):
                false_negatives.append({"company": str(case["company_name"]), "project": str(case["project_name"]), "candidate_key": key})
            evaluated += 1

    if evaluated != len(cases) or set(company_by_id) != {str(case.get("company_id")) for case in cases}:
        raise CompanyBenchmarkError("benchmark_case_mismatch", "公司或项目评测范围不完整")

    return {
        "scope": "fixed_differentiated_simulated_benchmark",
        "scope_note": "固定合成场景及作者规则标注，仅用于回归和发现规则缺口；不代表真实企业准确率，也不证明 DeepSeek 泛化能力。",
        "dataset_revision": seed.get("dataset_revision"),
        "as_of": benchmark.get("as_of"),
        "case_count": evaluated,
        "company_count": len(companies),
        "overall": _metrics(overall["tp"], overall["fp"], overall["fn"], overall["severity_match"], overall["severity_total"]),
        "by_company": _finish_groups(group_specs["by_company"][0], "company_name"),
        "by_industry": _finish_groups(group_specs["by_industry"][0], "industry"),
        "by_project_type": _finish_groups(group_specs["by_project_type"][0], "project_type"),
        "by_risk_type": _finish_groups(group_specs["by_risk_type"][0], "risk_type"),
        "false_positive_cases": false_positives,
        "false_negative_cases": false_negatives,
        "severity_mismatches": severity_mismatches,
        "expected_ask_cases": sum(case.get("expected_ai_decision") == "ASK" for case in cases),
        "expected_plan_cases": sum(case.get("expected_ai_decision") == "PLAN" for case in cases),
        "deepseek_runs": 0,
        "deepseek_status": "not_run",
        "boundaries": benchmark.get("boundaries") or {},
    }
