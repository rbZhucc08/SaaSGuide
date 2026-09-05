"""Product-domain skill contracts used by the SaaSGuide V2 workflow.

These are product-domain skills, not Codex installation skills.  Each contract
names the existing deterministic tool that supplies its trusted input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.retrieval.knowledge_base import load_documents, retrieve


SKILL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "name": "project-data-intake",
        "mode": "deterministic",
        "tool": "services.ingestion",
        "input": "XLSX, TXT, Markdown, DOCX or supported PDF",
        "output": "source-linked canonical data or reviewable evidence",
        "failure": "stop on unsupported, ambiguous or invalid input",
    },
    {
        "name": "risk-signal-scan",
        "mode": "deterministic",
        "tool": "services.risk_rules.deterministic_scan",
        "input": "validated canonical project data",
        "output": "deduplicated candidates with source evidence",
        "failure": "return a typed validation error",
    },
    {
        "name": "evidence-grounded-assessment",
        "mode": "deterministic-retrieval",
        "tool": "services.retrieval.knowledge_base",
        "input": "one candidate and the effective knowledge versions",
        "output": "allowlisted citations for model assessment",
        "failure": "return no citations instead of inventing evidence",
    },
    {
        "name": "risk-action-planner",
        "mode": "deepseek-json",
        "tool": "DeepSeek JSON completion plus Python validation",
        "input": "candidate, original evidence and retrieved citations",
        "output": "ASK or a cited PLAN draft",
        "failure": "block invalid JSON, fabricated citations or missing fields",
    },
    {
        "name": "weekly-risk-report",
        "mode": "deterministic",
        "tool": "services.reporting.metrics",
        "input": "Python-calculated metrics",
        "output": "reviewable report draft without model-written numbers",
        "failure": "keep deterministic report available",
    },
)


QUERY_BY_RISK_TYPE = {
    "schedule_delay": "项目延期 里程碑 前置任务 截止日期",
    "delivery_blocked": "项目延期 阻塞 风险负责人 行动",
    "schedule_pressure": "项目风险分级 截止日期 行动",
    "dependency_risk": "项目延期 前置任务 依赖关系",
}


def catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in SKILL_CATALOG]


def retrieve_candidate_evidence(candidate: dict[str, Any], knowledge_path: Path) -> list[dict[str, str]]:
    """Run the evidence-grounded-assessment retrieval tool."""
    query = " ".join(
        value
        for value in (
            QUERY_BY_RISK_TYPE.get(str(candidate.get("risk_type", "")), "项目风险 负责人 行动"),
            str(candidate.get("title", "")),
            str(candidate.get("task_name", "")),
        )
        if value
    )
    matches = retrieve(query, load_documents(knowledge_path), limit=8)
    effective = [item for item in matches if item.get("status") == "effective"][:3]
    return [
        {
            "citation_id": f"{item['document_id']}@{item['version']}",
            "document_id": item["document_id"],
            "title": item["title"],
            "version": item["version"],
            "effective_date": item["effective_date"],
            "quote": item["content"],
        }
        for item in effective
    ]
