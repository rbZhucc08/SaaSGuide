"""V3 evaluation and model-runtime read-only endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify

from services.evaluation.independent import EvaluationError, framework_status
from services.security.governance import readiness_status


def create_v3_operations_blueprint(
    *,
    development_blind_file: Path,
    holdout_blind_file: Path,
    annotations_dir: Path,
    client_factory: Callable[[], Any],
    skill_catalog: Callable[[], list[dict[str, Any]]],
    prompt_version: str,
    protocol_version: str,
) -> Blueprint:
    blueprint = Blueprint("v3_operations", __name__)

    @blueprint.get("/api/evaluation/framework")
    def independent_evaluation_framework() -> Any:
        try:
            return jsonify(framework_status(development_blind_file, holdout_blind_file, annotations_dir))
        except EvaluationError as error:
            return jsonify({"error": str(error), "code": "evaluation_framework_invalid"}), 500

    @blueprint.get("/api/agent/capabilities")
    def agent_capabilities() -> Any:
        client = client_factory()
        return jsonify({
            "agent": "saasguide-v2-orchestrator",
            "runtime_version": "v3",
            "provider": "deepseek",
            "provider_configured": client.is_configured,
            "model": client.model,
            "model_status": "ready" if client.is_configured else "unconfigured",
            "model_status_reason": "DeepSeek 密钥已配置；调用失败时规则扫描和人工处理仍可使用" if client.is_configured else "未配置 DeepSeek；规则扫描和人工处理仍可使用",
            "prompt_version": prompt_version,
            "protocol_version": protocol_version,
            "client_protocol_version": "deepseek-json-v1",
            "timeout_seconds": client.timeout_seconds,
            "max_retries": client.max_retries,
            "budget": {
                "version": client.budget_policy.version,
                "max_input_tokens": client.budget_policy.max_input_tokens,
                "max_output_tokens": client.budget_policy.max_output_tokens,
                "max_total_tokens": client.budget_policy.max_total_tokens,
                "max_batch_calls": client.budget_policy.max_batch_calls,
                "max_batch_total_tokens": client.budget_policy.max_batch_total_tokens,
            },
            "workflow": "bounded-risk-assessment",
            "skills": skill_catalog(),
            "human_confirmation_required": True,
        })

    @blueprint.get("/api/security/readiness")
    def security_readiness() -> Any:
        return jsonify(readiness_status())

    return blueprint
