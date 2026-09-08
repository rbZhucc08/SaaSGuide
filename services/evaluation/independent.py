"""Independent evaluation contracts kept separate from system predictions."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


FORBIDDEN_BLIND_FIELDS = {"prediction", "predictions", "expected", "ground_truth", "system_output"}
RISK_LABELS = {"positive", "negative", "insufficient"}
SEVERITIES = {"low", "medium", "high", "not_applicable", "insufficient"}
DECISIONS = {"ASK", "PLAN", "insufficient"}
TRISTATE = {"yes", "no", "insufficient", "not_reviewed"}
ERROR_TAGS = {"false_positive", "false_negative", "citation_error", "insufficient_information", "unexecutable_action", "severity_mismatch", "none"}


class EvaluationError(ValueError):
    pass


def validate_blind_cases(cases: list[dict[str, Any]], expected_split: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or not cases:
        raise EvaluationError("盲标包必须包含至少一个案例")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationError("每个盲标案例必须是对象")
        forbidden = FORBIDDEN_BLIND_FIELDS & set(case)
        if forbidden:
            raise EvaluationError(f"盲标案例不得包含系统预测字段：{', '.join(sorted(forbidden))}")
        case_id = str(case.get("case_id") or "").strip()
        split = str(case.get("split") or "").strip()
        if not case_id or case_id in seen:
            raise EvaluationError("案例编号缺失或重复")
        if split not in {"development", "holdout"}:
            raise EvaluationError("split 必须是 development 或 holdout")
        if expected_split and split != expected_split:
            raise EvaluationError("盲标包混入了其他数据集")
        if not isinstance(case.get("facts"), list) or not case["facts"]:
            raise EvaluationError("案例必须提供可核查事实")
        seen.add(case_id)
    return cases


def validate_annotation_set(payload: dict[str, Any], case_ids: set[str]) -> dict[str, Any]:
    annotator_id = str(payload.get("annotator_id") or "").strip()
    if not annotator_id:
        raise EvaluationError("标注者编号不能为空")
    labels = payload.get("labels")
    if not isinstance(labels, list) or {str(item.get("case_id")) for item in labels} != case_ids:
        raise EvaluationError("标注文件必须覆盖盲标包中的全部案例且不能多出案例")
    for item in labels:
        if item.get("risk_label") not in RISK_LABELS:
            raise EvaluationError("risk_label 无效")
        if item.get("severity") not in SEVERITIES:
            raise EvaluationError("severity 无效")
        if item.get("desired_decision") not in DECISIONS:
            raise EvaluationError("desired_decision 无效")
        if item.get("citation_supported", "not_reviewed") not in TRISTATE:
            raise EvaluationError("citation_supported 无效")
        if item.get("action_executable", "not_reviewed") not in TRISTATE:
            raise EvaluationError("action_executable 无效")
        tags = item.get("error_tags") or []
        if not isinstance(tags, list) or not set(tags) <= ERROR_TAGS:
            raise EvaluationError("error_tags 无效")
        if not str(item.get("rationale") or "").strip():
            raise EvaluationError("每条标注必须写判断依据")
    return payload


def agreement_report(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    if first.get("annotator_id") == second.get("annotator_id"):
        raise EvaluationError("两份标注必须来自不同标注者")
    left = {item["case_id"]: item for item in first["labels"]}
    right = {item["case_id"]: item for item in second["labels"]}
    if set(left) != set(right):
        raise EvaluationError("两位标注者覆盖的案例不一致")
    fields = ("risk_label", "severity", "desired_decision", "citation_supported", "action_executable")
    disagreements = []
    agreements = Counter()
    for case_id in sorted(left):
        changed = []
        for field in fields:
            if left[case_id].get(field, "not_reviewed") == right[case_id].get(field, "not_reviewed"):
                agreements[field] += 1
            else:
                changed.append(field)
        if changed:
            disagreements.append({"case_id": case_id, "fields": changed})
    total = len(left)
    return {
        "annotators": [first["annotator_id"], second["annotator_id"]],
        "case_count": total,
        "agreement_percent": {field: round(agreements[field] / total * 100, 2) for field in fields},
        "disagreements": disagreements,
        "requires_adjudication": bool(disagreements),
    }


def adjudicate(first: dict[str, Any], second: dict[str, Any], resolutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    report = agreement_report(first, second)
    resolution_map = {item.get("case_id"): item for item in resolutions}
    unresolved = [item["case_id"] for item in report["disagreements"] if item["case_id"] not in resolution_map]
    if unresolved:
        raise EvaluationError(f"仍有未裁决案例：{', '.join(unresolved)}")
    left = {item["case_id"]: item for item in first["labels"]}
    right = {item["case_id"]: item for item in second["labels"]}
    final = []
    for case_id in sorted(left):
        if left[case_id] == right[case_id]:
            final.append(left[case_id])
        else:
            resolution = resolution_map[case_id]
            if resolution.get("case_id") != case_id:
                raise EvaluationError("裁决记录的案例编号不一致")
            final.append(resolution)
    return final


def load_blind_package(path: Path, expected_split: str) -> dict[str, Any]:
    """Load a versioned package while keeping labels and predictions out of it."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationError(f"盲标包无法读取：{path.name}") from error
    if not isinstance(payload, dict) or payload.get("split") != expected_split:
        raise EvaluationError("盲标包顶层 split 与文件用途不一致")
    cases = validate_blind_cases(payload.get("cases"), expected_split)
    return {**payload, "cases": cases}


def framework_status(
    development_path: Path,
    holdout_path: Path,
    annotations_dir: Path | None = None,
) -> dict[str, Any]:
    """Report framework readiness without treating missing human work as a pass."""
    packages = {
        "development": load_blind_package(development_path, "development"),
        "holdout": load_blind_package(holdout_path, "holdout"),
    }
    annotators: set[str] = set()
    accepted_files = 0
    if annotations_dir and annotations_dir.exists():
        case_ids = {
            case["case_id"]
            for package in packages.values()
            for case in package["cases"]
        }
        for path in sorted(annotations_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                validate_annotation_set(payload, case_ids)
            except (OSError, json.JSONDecodeError, EvaluationError):
                continue
            annotators.add(payload["annotator_id"])
            accepted_files += 1
    annotator_count = len(annotators)
    return {
        "framework_version": packages["development"].get("package_version", "unknown"),
        "development_cases": len(packages["development"]["cases"]),
        "holdout_cases": len(packages["holdout"]["cases"]),
        "prediction_fields_removed": True,
        "annotator_count": annotator_count,
        "required_annotators": 2,
        "accepted_annotation_files": accepted_files,
        "external_annotation_complete": annotator_count >= 2,
        "status": (
            "独立评测可进入一致性检查与裁决"
            if annotator_count >= 2
            else "独立评测框架完成，外部标注待完成"
        ),
        "metrics": [
            "规则 Precision / Recall / F1",
            "检索召回",
            "引用支持率",
            "模型结构合格率",
            "行动可执行率",
        ],
        "scope_note": "案例和数据均为模拟内容；没有第二位独立标注者时，不产生独立评测结论。",
    }


def component_metrics(predictions: list[dict[str, Any]], labels: list[dict[str, Any]]) -> dict[str, Any]:
    prediction_by_id = {item["case_id"]: item for item in predictions}
    assessed = [item for item in labels if item["risk_label"] in {"positive", "negative"} and item["case_id"] in prediction_by_id]
    tp = sum(item["risk_label"] == "positive" and prediction_by_id[item["case_id"]].get("rule_positive") is True for item in assessed)
    fp = sum(item["risk_label"] == "negative" and prediction_by_id[item["case_id"]].get("rule_positive") is True for item in assessed)
    fn = sum(item["risk_label"] == "positive" and prediction_by_id[item["case_id"]].get("rule_positive") is False for item in assessed)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    retrieval_scores = []
    for label in labels:
        required = set(label.get("required_doc_ids") or [])
        predicted = set(prediction_by_id.get(label["case_id"], {}).get("retrieved_doc_ids") or [])
        if required:
            retrieval_scores.append(len(required & predicted) / len(required))
    reviewed_citations = [item for item in labels if item.get("citation_supported") in {"yes", "no"}]
    reviewed_actions = [item for item in labels if item.get("action_executable") in {"yes", "no"}]
    structures = [item for item in predictions if "model_output_valid" in item]
    return {
        "rules": {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)},
        "retrieval_recall": round(sum(retrieval_scores) / len(retrieval_scores), 4) if retrieval_scores else None,
        "citation_support_rate": round(sum(item["citation_supported"] == "yes" for item in reviewed_citations) / len(reviewed_citations), 4) if reviewed_citations else None,
        "model_structure_pass_rate": round(sum(item["model_output_valid"] is True for item in structures) / len(structures), 4) if structures else None,
        "action_executable_rate": round(sum(item["action_executable"] == "yes" for item in reviewed_actions) / len(reviewed_actions), 4) if reviewed_actions else None,
    }
