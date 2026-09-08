"""Local Flask application that connects the SaaSGuide phase-five workflow."""

from __future__ import annotations

import html
import json
import os
import sqlite3
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from flask import Flask, Response, g, jsonify, request, send_file, send_from_directory, url_for
from database.store import StoreError, create_action, dashboard as action_dashboard, record_candidate_decision, transition_action

from deepseek_ask_build import DeepSeekError, ModelOutputError, evaluate_brief
from deepseek_ask_build import DeepSeekClient
from deepseek_risk_assistant import analyze_risk
from services.ai.orchestrator import (
    RISK_OUTPUT_PROTOCOL_VERSION,
    RISK_PROMPT_VERSION,
    orchestrate_risk_candidate,
)
from services.ai.skills import catalog as ai_skill_catalog
from services.ingestion.xlsx_import import (
    IngestionError,
    MAX_XLSX_BYTES,
    confirm_import,
    load_pending,
    parse_xlsx,
    preview_payload,
    save_pending_upload,
    suggest_mapping,
)
from services.ingestion.text_evidence import (
    MAX_TEXT_BYTES,
    TextEvidenceError,
    parse_evidence,
    save_review,
)
from services.ingestion.pdf_audio import MediaError, parse_pdf
from services.adapters.contracts import AdapterError, validate_envelope
from services.risk_rules.deterministic_scan import (
    RiskScanError,
    evaluate_candidates,
    save_human_decision,
    scan_project,
)
from services.retrieval.knowledge_base import answer as knowledge_answer
from services.retrieval.knowledge_base import evaluate as evaluate_knowledge
from services.retrieval.knowledge_base import load_documents
from services.reporting.metrics import calculate as calculate_report
from services.reporting.metrics import csv_bytes as report_csv_bytes
from services.reporting.metrics import xlsx_bytes as report_xlsx_bytes
from services.company_data.store import (
    CompanyDataError,
    clear as clear_company_data,
    create_company,
    create_policy,
    create_project,
    delete_company,
    delete_policy,
    delete_project,
    project_document,
    read as read_company_data,
    reset as reset_company_data,
    set_active_company,
    update_company,
    update_policy,
    update_project,
)
from services.evaluation.company_benchmark import CompanyBenchmarkError, run_company_benchmark
from routes.v3_operations import create_v3_operations_blueprint
from validate_data import RISK_FILE, validate_risk_data


PROJECT_DIR = Path(__file__).resolve().parent
GENERATED_DIR = PROJECT_DIR / "generated"
MAX_JSON_REQUEST_BYTES = 64 * 1024
PENDING_IMPORT_DIR = GENERATED_DIR / "imports" / "pending"
RAW_DATA_DIR = PROJECT_DIR / "data" / "raw"
NORMALIZED_DATA_DIR = PROJECT_DIR / "data" / "normalized"
SAMPLE_DATA_DIR = PROJECT_DIR / "data" / "samples"
PHASE2_SAMPLE_FILE = PROJECT_DIR / "data" / "evaluation" / "phase2_project_timeline.json"
PHASE2_EXPECTED_FILE = PROJECT_DIR / "data" / "evaluation" / "phase2_expected_results.json"
RISK_DECISION_FILE = GENERATED_DIR / "risk-decisions.jsonl"
EVIDENCE_REVIEW_FILE = GENERATED_DIR / "evidence-reviews.jsonl"
EVIDENCE_PREVIEWS: dict[str, dict[str, Any]] = {}
KNOWLEDGE_FILE = PROJECT_DIR / "knowledge" / "documents" / "policies.json"
PHASE4_EVALUATION_FILE = PROJECT_DIR / "data" / "evaluation" / "phase4_questions.json"
DEMO_DATABASE = GENERATED_DIR / "saasguide-demo.db"
COMPANY_SEED_FILE = PROJECT_DIR / "data" / "demo" / "nebula_company_seed.json"
COMPANY_BENCHMARK_FILE = PROJECT_DIR / "data" / "evaluation" / "company_scenario_expected.json"
V3_DEVELOPMENT_BLIND_FILE = PROJECT_DIR / "data" / "evaluation" / "v3" / "development_blind.json"
V3_HOLDOUT_BLIND_FILE = PROJECT_DIR / "data" / "evaluation" / "v3" / "holdout_blind.json"
COMPANY_DATA_FILE = GENERATED_DIR / "company-data.json"
ALLOWED_SAMPLE_FILES = {
    "valid_project_tasks_cn.xlsx",
    "invalid_missing_owner.xlsx",
    "invalid_dates.xlsx",
    "invalid_dependencies.xlsx",
}
RISK_WRITE_LOCK = threading.Lock()
RISK_DECISION_LOCK = threading.Lock()
ERROR_LOG_LOCK = threading.Lock()
AI_RUN_LOCK = threading.Lock()
HTTP_ERROR_LOG = GENERATED_DIR / "http-errors.jsonl"
AI_RUN_LOG = GENERATED_DIR / "ai-runs.jsonl"
PUBLIC_FILES = {
    "index.html",
    "styles.css",
    "v2-shell.css",
    "shell.js",
    "app.js",
    "guide-data.json",
    "risk-data.json",
    "builder.html",
    "builder.css",
    "builder.js",
    "data-sources.html",
    "data-sources.css",
    "data-sources.js",
    "risk-radar.html",
    "risk-radar.css",
    "risk-radar.js",
    "evidence-intake.html",
    "evidence-intake.css",
    "evidence-intake.js",
    "knowledge-base.html",
    "knowledge-base.css",
    "knowledge-base.js",
    "action-tracker.html",
    "action-tracker.css",
    "action-tracker.js",
    "reports.html",
    "reports.css",
    "reports.js",
    "input-lab.html",
    "input-lab.css",
    "input-lab.js",
}

PUBLIC_MIMETYPES = {
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
}


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def build_runtime_report(risk_decisions_path: Path, database_path: Path, as_of: str | None = None) -> dict[str, Any]:
    today = date.fromisoformat(as_of) if as_of else date.today()
    decisions = _read_json_lines(risk_decisions_path)
    latest_by_candidate: dict[str, dict[str, Any]] = {}
    for item in decisions:
        candidate_id = str(item.get("candidate_id") or "")
        if candidate_id:
            latest_by_candidate[candidate_id] = item
    risks = []
    status_map = {"confirm": "confirmed", "watch": "observing", "reject": "dismissed", "false_positive": "dismissed"}
    for item in latest_by_candidate.values():
        stamp = str(item.get("recorded_at") or today.isoformat())
        risks.append({
            "id": str(item.get("candidate_id") or "unknown"),
            "date": stamp[:10],
            "level": str(item.get("severity") or "unknown"),
            "status": status_map.get(str(item.get("decision")), "observing"),
            "false_positive": item.get("decision") == "false_positive",
            "resolution_hours": None,
        })
    action_data = action_dashboard(database_path, today.isoformat())
    actions = [{"id": item["action_id"], "candidate_id": item["candidate_id"], "risk_decision_id": item.get("risk_decision_id"), "plan_run_id": item.get("plan_run_id"), "plan_step": item.get("plan_step"), "title": item["title"], "owner_role": item["owner_role"], "due_date": item["due_date"], "status": item["status"]} for item in action_data["actions"]]
    dates = [item["date"] for item in risks]
    period = f"{min(dates)} / {max(dates)}" if dates else "暂无人工风险记录"
    result = calculate_report({"period": period, "risks": risks, "actions": actions, "scope": "runtime_local_records"}, today.isoformat())
    result["traceability"] = {
        "latest_decision_ids": [item.get("decision_id") for item in latest_by_candidate.values()],
        "candidate_ids": sorted(latest_by_candidate),
        "action_ids": [item["id"] for item in actions],
    }
    return result


def build_dashboard_payload(normalized_dir: Path, risk_decisions_path: Path, evidence_reviews_path: Path, database_path: Path, knowledge_path: Path) -> dict[str, Any]:
    imports: list[dict[str, Any]] = []
    paths = sorted(normalized_dir.glob("*.json")) if normalized_dir.exists() else []
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and isinstance(document.get("source"), dict):
            imports.append(document)

    latest_by_project: dict[str, dict[str, Any]] = {}
    for document in imports:
        project = document.get("project") or {}
        source = document.get("source") or {}
        project_id = str(project.get("project_id") or document.get("import_id") or "")
        stamp = str(source.get("imported_at") or "")
        previous = latest_by_project.get(project_id)
        if previous is None or stamp >= str((previous.get("source") or {}).get("imported_at") or ""):
            latest_by_project[project_id] = document

    decisions = _read_json_lines(risk_decisions_path)
    reviews = _read_json_lines(evidence_reviews_path)
    action_summary = {"total": 0, "open": 0, "overdue": 0, "completed": 0}
    action_activity: list[dict[str, Any]] = []
    if database_path.exists():
        try:
            with sqlite3.connect(database_path) as connection:
                connection.row_factory = sqlite3.Row
                has_actions = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='action_items'").fetchone()
                rows = [dict(row) for row in connection.execute("SELECT title,status,due_date,updated_at FROM action_items ORDER BY updated_at DESC")] if has_actions else []
            today = datetime.now().date().isoformat()
            action_summary = {"total": len(rows), "open": sum(item["status"] in {"open", "in_progress"} for item in rows), "overdue": sum(item["status"] not in {"completed", "cancelled"} and item["due_date"] < today for item in rows), "completed": sum(item["status"] == "completed" for item in rows)}
            action_activity = [{"type": "action", "title": item["title"], "detail": f"行动状态：{item['status']}", "timestamp": item["updated_at"]} for item in rows[:5]]
        except (sqlite3.Error, OSError):
            pass

    try:
        knowledge = json.loads(knowledge_path.read_text(encoding="utf-8"))
        knowledge_count = len(knowledge) if isinstance(knowledge, list) else 0
    except (OSError, json.JSONDecodeError):
        knowledge_count = 0

    activities: list[dict[str, Any]] = []
    for document in imports:
        source, project, summary = document.get("source") or {}, document.get("project") or {}, document.get("summary") or {}
        activities.append({"type": "import", "title": f"已确认导入 {source.get('source_name', '项目数据')}", "detail": f"{project.get('project_name', '未命名项目')} · {summary.get('task_count', 0)} 条任务", "timestamp": source.get("imported_at")})
    for record in decisions:
        activities.append({"type": "risk_decision", "title": "已记录风险人工决策", "detail": f"决策：{record.get('decision', '未记录')} · 未自动写回正式风险", "timestamp": record.get("recorded_at")})
    for record in reviews:
        source = record.get("source") or {}
        activities.append({"type": "evidence_review", "title": f"已核对 {source.get('filename', '文本证据')}", "detail": f"{len(record.get('decisions') or [])} 条候选事实已人工处理", "timestamp": record.get("created_at")})
    activities.extend(action_activity)
    activities.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return {"generated_at": now_iso(), "summary": {"imports": len(imports), "projects": len(latest_by_project), "tasks": sum(int((item.get("summary") or {}).get("task_count") or len(item.get("tasks") or [])) for item in latest_by_project.values()), "risk_decisions": len(decisions), "evidence_reviews": len(reviews), "knowledge_versions": knowledge_count}, "actions": action_summary, "recent_activity": activities[:8], "scope": "local_confirmed_records_only"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def runtime_knowledge_path(company_data: dict[str, Any], company_data_path: Path) -> Path:
    path = company_data_path.with_name("runtime-knowledge.json")
    atomic_write_text(path, json.dumps(company_data.get("policies", []), ensure_ascii=False, indent=2) + "\n")
    return path


def append_run_log(output_dir: Path, brief: dict[str, Any], result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "createdAt": now_iso(),
        "featureName": brief.get("featureName", ""),
        "decision": result.get("decision"),
        "source": result.get("source"),
        "model": result.get("model"),
        "usage": result.get("usage"),
    }
    with (output_dir / "run-log.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")


def render_guide_html(brief: dict[str, Any], result: dict[str, Any]) -> str:
    guide = result["guide"]
    steps = guide["guideSteps"]
    step_cards = "\n".join(
        f"""
        <article class="step-card">
          <span>步骤 {step['step']}</span>
          <h2>{html.escape(step['title'])}</h2>
          <p>{html.escape(step['description'])}</p>
          <small>目标：{html.escape(step['target'])}</small>
        </article>"""
        for step in steps
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(str(brief['featureName']))}｜生成预览</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, "Microsoft YaHei", sans-serif; color: #252238; background: #f5f3fb; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 40px 20px; }}
    main {{ width: min(880px, 100%); margin: auto; }}
    .notice {{ padding: 12px 16px; border: 1px solid #ddd5f6; border-radius: 12px; background: #fff; color: #655b80; }}
    h1 {{ margin: 28px 0 8px; font-size: clamp(28px, 5vw, 44px); }}
    .summary {{ margin: 0 0 28px; color: #686278; line-height: 1.7; }}
    .steps {{ display: grid; gap: 16px; }}
    .step-card {{ padding: 22px; border: 1px solid #e4dff0; border-radius: 18px; background: #fff; box-shadow: 0 12px 30px rgba(55, 38, 90, .07); }}
    .step-card span {{ color: #6e43d6; font-weight: 700; }}
    .step-card h2 {{ margin: 8px 0; }}
    .step-card p {{ color: #625d6f; line-height: 1.7; }}
    .step-card small {{ color: #8a8497; }}
    footer {{ margin-top: 28px; color: #777083; font-size: 14px; }}
  </style>
</head>
<body>
  <main>
    <div class="notice">个人学习 Demo · 虚构 SaaS 与模拟输入 · 由 DeepSeek 生成并经本地规则校验</div>
    <h1>{html.escape(str(brief['featureName']))}</h1>
    <p class="summary">{html.escape(str(brief['featureBrief']))}</p>
    <section class="steps" aria-label="生成的引导步骤">
      {step_cards}
    </section>
    <footer>生成时间：{html.escape(now_iso())} · 模型：{html.escape(str(result.get('model', '未记录')))}</footer>
  </main>
</body>
</html>
"""


def save_build_outputs(
    output_dir: Path, brief: dict[str, Any], result: dict[str, Any]
) -> dict[str, str]:
    guide_path = output_dir / "guide-data.generated.json"
    preview_path = output_dir / "guide-preview.generated.html"
    guide_document = {
        "meta": {
            "generatedAt": now_iso(),
            "featureName": brief["featureName"],
            "source": result.get("source"),
            "model": result.get("model"),
            "usage": result.get("usage"),
        },
        **result["guide"],
    }
    atomic_write_text(
        guide_path, json.dumps(guide_document, ensure_ascii=False, indent=2) + "\n"
    )
    atomic_write_text(preview_path, render_guide_html(brief, result))
    return {"guide": guide_path.name, "preview": preview_path.name}


def save_risk_analysis(output_dir: Path, risk: dict[str, Any], result: dict[str, Any]) -> str:
    analysis_path = output_dir / "latest-risk-analysis.json"
    document = {
        "meta": {
            "createdAt": now_iso(),
            "riskId": risk.get("id"),
            "riskTitle": risk.get("title"),
            "source": result.get("source"),
            "model": result.get("model"),
            "usage": result.get("usage"),
        },
        "analysis": result,
    }
    atomic_write_text(analysis_path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return analysis_path.name


def append_risk_log(output_dir: Path, risk: dict[str, Any], result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "createdAt": now_iso(),
        "riskId": risk.get("id"),
        "riskTitle": risk.get("title"),
        "decision": result.get("decision"),
        "source": result.get("source"),
        "model": result.get("model"),
        "usage": result.get("usage"),
    }
    with (output_dir / "risk-assistant-run-log.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")


def _required_text(source: dict[str, Any], field: str, label: str, limit: int) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"请填写{label}")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{label}不能超过 {limit} 个字符")
    return value


def build_confirmed_risk(draft: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    from datetime import date

    if analysis.get("decision") != "PLAN":
        raise ValueError("只有通过校验的 PLAN 才能加入风险列表")
    from deepseek_risk_assistant import validate_risk_result

    analysis_errors = validate_risk_result(analysis)
    if analysis_errors:
        raise ValueError("AI 分析结果无效：" + "；".join(analysis_errors))

    level_to_type = {"高风险": "high", "中风险": "medium", "低风险": "low"}
    level = analysis["suggestedLevel"]
    due_text = _required_text(draft, "due", "截止日期", 10)
    try:
        due_date = date.fromisoformat(due_text)
    except ValueError as error:
        raise ValueError("截止日期必须是有效的 YYYY-MM-DD 日期") from error

    actions = [item["action"].strip() for item in analysis["actions"]]
    return {
        "id": f"risk-{uuid4().hex[:10]}",
        "type": level_to_type[level],
        "level": level,
        "title": _required_text(draft, "title", "风险标题", 100),
        "summary": _required_text(analysis, "summary", "风险摘要", 200),
        "description": _required_text(draft, "description", "风险描述", 1000),
        "owner": _required_text(draft, "owner", "责任人", 50),
        "avatarClass": "avatar--green" if level == "低风险" else "avatar--purple",
        "due": due_text,
        "overdue": due_date < date.today(),
        "impact": _required_text(draft, "impact", "影响范围", 200),
        "status": "待处理",
        "plan": actions,
    }


def persist_risk(risk_file: Path, output_dir: Path, risk: dict[str, Any]) -> None:
    with RISK_WRITE_LOCK:
        try:
            current = json.loads(risk_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise OSError("当前风险数据无法读取") from error
        risks = current.get("risks")
        if not isinstance(risks, list):
            raise OSError("当前风险数据缺少 risks 列表")

        updated = {"risks": [*risks, risk]}
        errors = validate_risk_data(updated)
        if errors:
            raise ValueError("新风险未通过数据校验：" + "；".join(errors))

        backup_dir = output_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        atomic_write_text(
            backup_dir / f"risk-data.{stamp}.backup.json",
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        )
        atomic_write_text(risk_file, json.dumps(updated, ensure_ascii=False, indent=2) + "\n")


def create_app(
    output_dir: Path = GENERATED_DIR,
    evaluator: Callable[[Any], dict[str, Any]] = evaluate_brief,
    risk_evaluator: Callable[[Any, str], dict[str, Any]] = analyze_risk,
    ai_orchestrator: Callable[[Any, Any, Any, str, Path], dict[str, Any]] = orchestrate_risk_candidate,
    risk_file: Path = RISK_FILE,
    pending_import_dir: Path = PENDING_IMPORT_DIR,
    raw_data_dir: Path = RAW_DATA_DIR,
    normalized_data_dir: Path = NORMALIZED_DATA_DIR,
    risk_decision_file: Path = RISK_DECISION_FILE,
    evidence_review_file: Path = EVIDENCE_REVIEW_FILE,
    database_path: Path = DEMO_DATABASE,
    knowledge_file: Path = KNOWLEDGE_FILE,
    company_data_file: Path | None = None,
    company_seed_file: Path = COMPANY_SEED_FILE,
    company_benchmark_file: Path = COMPANY_BENCHMARK_FILE,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
    company_data_path = company_data_file or output_dir / "company-data.json"
    app.register_blueprint(create_v3_operations_blueprint(
        development_blind_file=V3_DEVELOPMENT_BLIND_FILE,
        holdout_blind_file=V3_HOLDOUT_BLIND_FILE,
        annotations_dir=output_dir / "evaluation" / "annotations",
        client_factory=DeepSeekClient,
        skill_catalog=ai_skill_catalog,
        prompt_version=RISK_PROMPT_VERSION,
        protocol_version=RISK_OUTPUT_PROTOCOL_VERSION,
    ))

    @app.before_request
    def begin_request_trace():
        g.request_id = f"http-{uuid4().hex[:12]}"
        g.request_started = time.perf_counter()

    @app.after_request
    def security_headers(response):
        response.headers["X-Request-ID"] = g.get("request_id", "http-unknown")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        if response.status_code >= 400 and not app.config.get("TESTING"):
            record = {
                "event": "http_error",
                "request_id": g.get("request_id", "http-unknown"),
                "created_at": now_iso(),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000),
            }
            try:
                with ERROR_LOG_LOCK:
                    HTTP_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
                    with HTTP_ERROR_LOG.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                app.logger.exception("Unable to append HTTP error log")
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "saasguide-local-demo", "scope": "simulated-data-only", "version": "2.0-demo"})

    @app.get("/")
    def dashboard():
        return send_from_directory(PROJECT_DIR, "index.html")

    @app.get("/api/dashboard")
    def dashboard_data():
        try:
            return jsonify(build_dashboard_payload(normalized_data_dir, risk_decision_file, evidence_review_file, database_path, knowledge_file))
        except (OSError, json.JSONDecodeError):
            return jsonify({"error": "工作台本地状态无法读取", "code": "dashboard_unavailable"}), 500

    @app.get("/api/company-data")
    def company_data():
        try:
            return jsonify(read_company_data(company_data_path, company_seed_file))
        except (CompanyDataError, OSError, json.JSONDecodeError) as error:
            code = error.code if isinstance(error, CompanyDataError) else "company_data_unavailable"
            status = error.status if isinstance(error, CompanyDataError) else 500
            return jsonify({"error": str(error), "code": code}), status

    @app.post("/api/company-data/reset")
    def reset_company_records():
        try:
            return jsonify(reset_company_data(company_data_path, company_seed_file))
        except (CompanyDataError, OSError, json.JSONDecodeError) as error:
            return jsonify({"error": str(error), "code": "company_data_reset_failed"}), 500

    @app.post("/api/company-data/companies")
    def add_company_record():
        try:
            return jsonify(create_company(company_data_path, company_seed_file, request.get_json(silent=True))), 201
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.put("/api/company-data/companies/<company_id>")
    def edit_company_record(company_id: str):
        try:
            return jsonify(update_company(company_data_path, company_seed_file, company_id, request.get_json(silent=True)))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.delete("/api/company-data/companies/<company_id>")
    def remove_company_record(company_id: str):
        try:
            return jsonify(delete_company(company_data_path, company_seed_file, company_id))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.put("/api/company-data/active-company")
    def choose_active_company():
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(set_active_company(company_data_path, company_seed_file, str(payload.get("company_id", ""))))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.post("/api/company-data/clear")
    def clear_company_records():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("confirmed") is not True:
            return jsonify({"error": "清空前必须明确确认", "code": "confirmation_required"}), 400
        try:
            return jsonify(clear_company_data(company_data_path, company_seed_file))
        except (CompanyDataError, OSError, json.JSONDecodeError) as error:
            return jsonify({"error": str(error), "code": "company_data_clear_failed"}), 500

    @app.post("/api/company-data/projects")
    def add_company_project():
        try:
            return jsonify(create_project(company_data_path, company_seed_file, request.get_json(silent=True))), 201
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.put("/api/company-data/projects/<project_id>")
    def edit_company_project(project_id: str):
        try:
            return jsonify(update_project(company_data_path, company_seed_file, project_id, request.get_json(silent=True)))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.delete("/api/company-data/projects/<project_id>")
    def remove_company_project(project_id: str):
        try:
            return jsonify(delete_project(company_data_path, company_seed_file, project_id))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.post("/api/company-data/projects/<project_id>/scan")
    def scan_company_project(project_id: str):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        try:
            data = read_company_data(company_data_path, company_seed_file)
            result = scan_project(project_document(data, project_id, payload.get("as_of")), payload.get("as_of"))
            result["company"] = data["company"]
            result["evaluation"] = None
            result["sample_mode"] = False
            result["source_mode"] = "editable_company_project"
            return jsonify(result)
        except (CompanyDataError, RiskScanError) as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.post("/api/company-data/policies")
    def add_company_policy():
        try:
            return jsonify(create_policy(company_data_path, company_seed_file, request.get_json(silent=True))), 201
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.get("/api/evaluation/company-benchmark")
    def company_benchmark():
        try:
            return jsonify(run_company_benchmark(company_seed_file, company_benchmark_file))
        except CompanyBenchmarkError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.put("/api/company-data/policies/<document_id>/<version>")
    def edit_company_policy(document_id: str, version: str):
        try:
            return jsonify(update_policy(company_data_path, company_seed_file, document_id, version, request.get_json(silent=True)))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.delete("/api/company-data/policies/<document_id>/<version>")
    def remove_company_policy(document_id: str, version: str):
        try:
            return jsonify(delete_policy(company_data_path, company_seed_file, document_id, version))
        except CompanyDataError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.get("/builder")
    @app.get("/builder.html")
    def builder():
        return send_from_directory(PROJECT_DIR, "builder.html")

    @app.get("/data-sources")
    @app.get("/data-sources.html")
    def data_sources():
        return send_from_directory(PROJECT_DIR, "data-sources.html")

    @app.get("/risk-radar")
    @app.get("/risk-radar.html")
    def risk_radar():
        return send_from_directory(PROJECT_DIR, "risk-radar.html")

    @app.get("/evidence-intake")
    @app.get("/evidence-intake.html")
    def evidence_intake():
        return send_from_directory(PROJECT_DIR, "evidence-intake.html")

    @app.get("/knowledge-base")
    @app.get("/knowledge-base.html")
    def knowledge_base():
        return send_from_directory(PROJECT_DIR, "knowledge-base.html")

    @app.get("/action-tracker")
    @app.get("/action-tracker.html")
    def action_tracker():
        return send_from_directory(PROJECT_DIR, "action-tracker.html")

    @app.get("/reports")
    @app.get("/reports.html")
    def reports():
        return send_from_directory(PROJECT_DIR, "reports.html")

    @app.get("/input-lab")
    @app.get("/input-lab.html")
    def input_lab():
        return send_from_directory(PROJECT_DIR, "input-lab.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        if filename not in PUBLIC_FILES:
            return jsonify({"error": "文件不存在"}), 404
        return send_from_directory(PROJECT_DIR, filename, mimetype=PUBLIC_MIMETYPES.get(Path(filename).suffix.lower()))

    @app.get("/generated/<path:filename>")
    def generated_file(filename: str):
        if filename not in {
            "guide-data.generated.json",
            "guide-preview.generated.html",
            "latest-risk-analysis.json",
        }:
            return jsonify({"error": "文件不存在"}), 404
        return send_from_directory(output_dir, filename)

    @app.post("/api/guides/generate")
    def generate_guide():
        if request.content_length and request.content_length > MAX_JSON_REQUEST_BYTES:
            return jsonify({"error": "Brief 内容过长，最大允许 64 KB"}), 413
        brief = request.get_json(silent=True)
        if not isinstance(brief, dict):
            return jsonify({"error": "请求必须是 JSON 对象"}), 400

        try:
            result = evaluator(brief)
            append_run_log(output_dir, brief, result)
            if result.get("decision") == "BUILD":
                files = save_build_outputs(output_dir, brief, result)
                result["artifacts"] = {
                    "guideUrl": url_for("generated_file", filename=files["guide"]),
                    "previewUrl": url_for("generated_file", filename=files["preview"]),
                }
            return jsonify(result)
        except (DeepSeekError, ModelOutputError) as error:
            return jsonify({"error": str(error)}), 502
        except OSError:
            app.logger.exception("Unable to save generated output")
            return jsonify({"error": "结果已生成，但本地文件保存失败"}), 500

    @app.post("/api/risks/analyze")
    def analyze_current_risk():
        if request.content_length and request.content_length > MAX_JSON_REQUEST_BYTES:
            return jsonify({"error": "风险分析请求过长，最大允许 64 KB"}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("risk"), dict):
            return jsonify({"error": "请求必须包含 risk 对象"}), 400
        risk = payload["risk"]
        context_note = payload.get("contextNote", "")
        if not isinstance(context_note, str):
            return jsonify({"error": "contextNote 必须是文字"}), 400
        if len(context_note) > 2000:
            return jsonify({"error": "补充说明不能超过 2000 个字符"}), 400

        try:
            result = risk_evaluator(risk, context_note)
            append_risk_log(output_dir, risk, result)
            if result.get("decision") == "PLAN":
                filename = save_risk_analysis(output_dir, risk, result)
                result["artifactUrl"] = url_for("generated_file", filename=filename)
            return jsonify(result)
        except (DeepSeekError, ModelOutputError) as error:
            return jsonify({"error": str(error)}), 502
        except OSError:
            app.logger.exception("Unable to save risk analysis")
            return jsonify({"error": "分析已完成，但本地记录保存失败"}), 500

    @app.post("/api/risks")
    def create_risk():
        if request.content_length and request.content_length > MAX_JSON_REQUEST_BYTES:
            return jsonify({"error": "新建风险请求过长，最大允许 64 KB"}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象"}), 400
        draft = payload.get("draft")
        analysis = payload.get("analysis")
        if not isinstance(draft, dict) or not isinstance(analysis, dict):
            return jsonify({"error": "请求必须包含 draft 和 analysis 对象"}), 400

        try:
            risk = build_confirmed_risk(draft, analysis)
            persist_risk(risk_file, output_dir, risk)
            return jsonify({"risk": risk, "message": "新风险已保存"}), 201
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except OSError:
            app.logger.exception("Unable to persist new risk")
            return jsonify({"error": "新风险无法写入本地数据文件"}), 500

    @app.post("/api/imports/preview")
    def preview_import():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"error": "请选择一个 XLSX 文件", "code": "file_required"}), 400
        try:
            content = upload.stream.read(MAX_XLSX_BYTES + 1)
            preview_id, workbook_path = save_pending_upload(
                content, upload.filename, pending_import_dir
            )
            parsed = parse_xlsx(workbook_path, upload.filename)
            mapping = suggest_mapping(parsed.headers)
            return jsonify(preview_payload(parsed, mapping, preview_id))
        except IngestionError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status
        except OSError:
            app.logger.exception("Unable to create XLSX preview")
            return jsonify({"error": "XLSX 预览无法保存", "code": "preview_save_failed"}), 500

    @app.post("/api/imports/sample/<filename>")
    def preview_sample_import(filename: str):
        if filename not in ALLOWED_SAMPLE_FILES:
            return jsonify({"error": "内置模拟样本不存在", "code": "sample_not_found"}), 404
        try:
            content = (SAMPLE_DATA_DIR / filename).read_bytes()
            preview_id, workbook_path = save_pending_upload(content, filename, pending_import_dir)
            parsed = parse_xlsx(workbook_path, filename)
            mapping = suggest_mapping(parsed.headers)
            response = preview_payload(parsed, mapping, preview_id)
            response["sample_mode"] = True
            return jsonify(response)
        except IngestionError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status
        except OSError:
            app.logger.exception("Unable to load bundled XLSX sample")
            return jsonify({"error": "内置模拟样本无法读取", "code": "sample_read_failed"}), 500

    @app.post("/api/imports/validate")
    def validate_import():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("mapping"), dict):
            return jsonify({"error": "请求必须包含 mapping 对象", "code": "mapping_required"}), 400
        try:
            workbook_path, source_name = load_pending(payload.get("preview_id", ""), pending_import_dir)
            parsed = parse_xlsx(workbook_path, source_name)
            return jsonify(preview_payload(parsed, payload["mapping"], payload["preview_id"]))
        except IngestionError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.post("/api/imports/confirm")
    def confirm_xlsx_import():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("mapping"), dict):
            return jsonify({"error": "请求必须包含 mapping 对象", "code": "mapping_required"}), 400
        try:
            result = confirm_import(
                payload.get("preview_id", ""),
                payload["mapping"],
                pending_import_dir,
                raw_data_dir,
                normalized_data_dir,
            )
            return jsonify(result), 201
        except IngestionError as error:
            if error.code == "validation_failed":
                try:
                    workbook_path, source_name = load_pending(payload.get("preview_id", ""), pending_import_dir)
                    parsed = parse_xlsx(workbook_path, source_name)
                    response = preview_payload(parsed, payload["mapping"], payload.get("preview_id"))
                    response.update({"error": str(error), "code": error.code})
                    return jsonify(response), error.status
                except IngestionError:
                    pass
            return jsonify({"error": str(error), "code": error.code}), error.status
        except OSError:
            app.logger.exception("Unable to persist confirmed XLSX import")
            return jsonify({"error": "确认后的导入文件无法保存", "code": "import_save_failed"}), 500

    @app.post("/api/risk-scans/sample")
    def scan_evaluation_sample():
        try:
            document = json.loads(PHASE2_SAMPLE_FILE.read_text(encoding="utf-8"))
            expected = json.loads(PHASE2_EXPECTED_FILE.read_text(encoding="utf-8"))
            result = scan_project(document)
            result["evaluation"] = evaluate_candidates(result["candidates"], expected)
            result["sample_mode"] = True
            return jsonify(result)
        except RiskScanError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status
        except (OSError, json.JSONDecodeError):
            app.logger.exception("Unable to read Phase 2 evaluation fixture")
            return jsonify({"error": "固定评测样本无法读取", "code": "evaluation_fixture_failed"}), 500

    @app.post("/api/risk-scans/latest")
    def scan_latest_import():
        if request.content_length and request.content_length > MAX_JSON_REQUEST_BYTES:
            return jsonify({"error": "风险扫描请求过长，最大允许 64 KB", "code": "request_too_large"}), 413
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        normalized_files = sorted(
            normalized_data_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True
        )
        if not normalized_files:
            return jsonify({"error": "尚无已确认的统一项目 JSON，请先完成 XLSX 导入", "code": "normalized_import_not_found"}), 404
        try:
            document = json.loads(normalized_files[0].read_text(encoding="utf-8"))
            result = scan_project(document, payload.get("as_of"))
            result["evaluation"] = None
            result["sample_mode"] = False
            return jsonify(result)
        except RiskScanError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status
        except (OSError, json.JSONDecodeError):
            app.logger.exception("Unable to read latest normalized import")
            return jsonify({"error": "最近的统一项目 JSON 无法读取", "code": "normalized_import_invalid"}), 500

    @app.post("/api/risk-scans/decisions")
    def record_risk_decision():
        if request.content_length and request.content_length > MAX_JSON_REQUEST_BYTES:
            return jsonify({"error": "人工决策请求过长，最大允许 64 KB", "code": "request_too_large"}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        try:
            with RISK_DECISION_LOCK:
                record = save_human_decision(risk_decision_file, payload)
                record_candidate_decision(
                    database_path,
                    {
                        "candidate_id": record["candidate_id"],
                        "project_id": record.get("project_id", "local-project"),
                        "project_name": record.get("project_name", "本地项目"),
                        "title": record.get("title", record["candidate_id"]),
                        "company_id": record.get("company_id", ""),
                        "task_id": record.get("task_id", ""),
                        "source_id": record.get("source_id", ""),
                        "scan_id": record.get("scan_id", ""),
                        "evidence": record.get("evidence", []),
                        "citations": record.get("citations", []),
                    },
                    record,
                )
            return jsonify({"message": "人工选择已记录", "record": record}), 201
        except RiskScanError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status
        except OSError:
            app.logger.exception("Unable to save human risk decision")
            return jsonify({"error": "人工选择无法保存", "code": "decision_save_failed"}), 500

    @app.post("/api/agent/risk-assessment")
    def agent_risk_assessment():
        if request.content_length and request.content_length > MAX_JSON_REQUEST_BYTES:
            return jsonify({"error": "AI 研判请求过长，最大允许 64 KB", "code": "request_too_large"}), 413
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        try:
            company_context = read_company_data(company_data_path, company_seed_file)
            project_context = dict(payload.get("project") or {})
            project_context["company_context"] = company_context["company"]
            result = ai_orchestrator(
                payload.get("candidate"),
                project_context,
                payload.get("source"),
                str(payload.get("context_note", "")),
                runtime_knowledge_path(company_context, company_data_path),
            )
            record = {
                "run_id": result.get("run_id"),
                "feature": "v2-risk-assessment",
                "status": result.get("decision", "unknown"),
                "model_status": result.get("model_status", "unknown"),
                "model": result.get("model"),
                "candidate_id": str(payload.get("candidate", {}).get("candidate_id", "")) if isinstance(payload.get("candidate"), dict) else "",
                "company_id": company_context["active_company_id"],
                "trace": result.get("trace", []),
                "created_at": result.get("created_at", now_iso()),
                "prompt_version": result.get("prompt_version"),
                "protocol_version": result.get("protocol_version"),
                "telemetry": result.get("telemetry", {}),
                "usage": result.get("usage", {}),
            }
            if not app.config.get("TESTING"):
                with AI_RUN_LOCK:
                    AI_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
                    with AI_RUN_LOG.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            return jsonify(result)
        except DeepSeekError as error:
            if not app.config.get("TESTING"):
                failure = {
                    "run_id": error.run.get("run_id"),
                    "feature": "v3-risk-assessment",
                    "status": "failed",
                    "model_status": "failed",
                    "error_category": error.code,
                    "telemetry": error.run,
                    "created_at": now_iso(),
                }
                with AI_RUN_LOCK:
                    AI_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
                    with AI_RUN_LOG.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
            return jsonify({
                "error": str(error),
                "code": "agent_unavailable",
                "error_category": error.code,
                "model_status": "failed",
                "telemetry": error.run,
                "fallback": "规则候选和人工确认路径仍可使用",
            }), 502
        except ModelOutputError as error:
            if not app.config.get("TESTING"):
                failure = {
                    "run_id": error.run.get("run_id"),
                    "feature": "v3-risk-assessment",
                    "status": "rejected",
                    "model_status": "invalid_output",
                    "error_category": "invalid_model_output",
                    "telemetry": error.run,
                    "created_at": now_iso(),
                }
                with AI_RUN_LOCK:
                    AI_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
                    with AI_RUN_LOG.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
            return jsonify({
                "error": str(error),
                "code": "agent_unavailable",
                "error_category": "invalid_model_output",
                "model_status": "failed",
                "telemetry": error.run,
                "fallback": "规则候选和人工确认路径仍可使用",
            }), 502
        except (OSError, ValueError, json.JSONDecodeError):
            app.logger.exception("Unable to run V2 orchestrator")
            return jsonify({"error": "AI 协调流程当前无法运行", "code": "agent_failed"}), 500

    @app.post("/api/evidence/preview")
    def preview_evidence():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"error": "请选择 TXT、Markdown 或 DOCX 文件", "code": "file_required"}), 400
        try:
            content = upload.stream.read(MAX_TEXT_BYTES + 1)
            result = parse_evidence(content, upload.filename)
            EVIDENCE_PREVIEWS[result["preview_id"]] = result
            return jsonify(result)
        except TextEvidenceError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.post("/api/evidence/sample")
    def preview_evidence_sample():
        try:
            sample = PROJECT_DIR / "data" / "documents" / "phase3_project_weekly_update.docx"
            result = parse_evidence(sample.read_bytes(), sample.name)
            result["sample_mode"] = True
            EVIDENCE_PREVIEWS[result["preview_id"]] = result
            return jsonify(result)
        except (OSError, TextEvidenceError) as error:
            code = error.code if isinstance(error, TextEvidenceError) else "sample_read_failed"
            status = error.status if isinstance(error, TextEvidenceError) else 500
            return jsonify({"error": str(error), "code": code}), status

    @app.post("/api/evidence/reviews")
    def review_evidence():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        preview = EVIDENCE_PREVIEWS.get(str(payload.get("preview_id", "")))
        if preview is None:
            return jsonify({"error": "预览已失效，请重新解析文件", "code": "preview_not_found"}), 404
        try:
            record = save_review(EVIDENCE_REVIEW_FILE, preview, payload)
            return jsonify({"message": "人工核对已记录；未写回任务或正式风险", "record": record}), 201
        except TextEvidenceError as error:
            return jsonify({"error": str(error), "code": error.code}), error.status

    @app.post("/api/knowledge/answer")
    def answer_from_knowledge():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("question"), str):
            return jsonify({"error": "请求必须包含 question 文字", "code": "question_required"}), 400
        filters = payload.get("filters") or {}
        if not isinstance(filters, dict) or set(filters) - {"document_id", "status", "company_id", "document_type", "tags"}:
            return jsonify({"error": "知识检索筛选条件无效", "code": "filters_invalid"}), 400
        try:
            documents = read_company_data(company_data_path, company_seed_file)["policies"]
            return jsonify(knowledge_answer(payload["question"], documents, filters))
        except (CompanyDataError, OSError, ValueError, json.JSONDecodeError):
            app.logger.exception("Unable to query knowledge base")
            return jsonify({"error": "知识库当前无法读取", "code": "knowledge_unavailable"}), 500

    @app.post("/api/knowledge/evaluate")
    def evaluate_knowledge_base():
        try:
            documents = load_documents(knowledge_file)
            cases = json.loads(PHASE4_EVALUATION_FILE.read_text(encoding="utf-8"))
            result = evaluate_knowledge(documents, cases)
            result["scope"] = "fixed_simulated_dataset"
            return jsonify(result)
        except (OSError, ValueError, json.JSONDecodeError):
            app.logger.exception("Unable to evaluate knowledge base")
            return jsonify({"error": "知识库评测无法运行", "code": "evaluation_unavailable"}), 500

    @app.get("/api/actions")
    def list_actions():
        try:
            return jsonify(action_dashboard(database_path, request.args.get("as_of")))
        except (OSError, ValueError):
            return jsonify({"error": "行动数据无法读取", "code": "action_store_unavailable"}), 500

    @app.post("/api/actions")
    def add_action():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        try:
            return jsonify({"message": "人工确认的行动已保存", "action": create_action(database_path, payload)}), 201
        except StoreError as error:
            return jsonify({"error": str(error), "code": "action_invalid"}), 400

    @app.post("/api/actions/<action_id>/transition")
    def change_action(action_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求必须是 JSON 对象", "code": "invalid_request"}), 400
        try:
            action = transition_action(database_path, action_id, str(payload.get("status", "")), str(payload.get("actor", "")), str(payload.get("note", "")))
            return jsonify({"message": "行动状态和审计事件已更新", "action": action})
        except StoreError as error:
            return jsonify({"error": str(error), "code": "transition_invalid"}), 400

    @app.get("/api/reports/weekly")
    def weekly_report():
        try:
            return jsonify(build_runtime_report(risk_decision_file, database_path, request.args.get("as_of")))
        except (OSError, ValueError, json.JSONDecodeError):
            return jsonify({"error": "报告数据无法读取", "code": "report_unavailable"}), 500

    @app.get("/downloads/weekly-risk-report.csv")
    def download_weekly_csv():
        try:
            result = build_runtime_report(risk_decision_file, database_path, request.args.get("as_of"))
            return Response(report_csv_bytes(result), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=weekly-risk-report.csv"})
        except (OSError, ValueError, json.JSONDecodeError):
            return jsonify({"error": "CSV 报告无法生成", "code": "report_unavailable"}), 500

    @app.get("/downloads/weekly-risk-report.xlsx")
    def download_weekly_xlsx():
        try:
            result = build_runtime_report(risk_decision_file, database_path, request.args.get("as_of"))
            return Response(report_xlsx_bytes(result), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=weekly-risk-report.xlsx"})
        except (OSError, ValueError, json.JSONDecodeError):
            return jsonify({"error": "XLSX 报告无法生成", "code": "report_unavailable"}), 500

    @app.post("/api/media/pdf/sample")
    def parse_pdf_sample():
        path = PROJECT_DIR / "data" / "documents" / "phase7_meeting_notes.pdf"
        try:
            result = parse_pdf(path.read_bytes(), path.name)
            result["sample_mode"] = True
            return jsonify(result)
        except (OSError, MediaError) as error:
            code = error.code if isinstance(error, MediaError) else "sample_read_failed"
            status = error.status if isinstance(error, MediaError) else 500
            return jsonify({"error": str(error), "code": code}), status

    @app.post("/api/adapters/validate")
    def validate_adapter():
        payload = request.get_json(silent=True)
        try:
            return jsonify(validate_envelope(payload))
        except AdapterError as error:
            return jsonify({"error": str(error), "code": "adapter_invalid"}), 400

    @app.get("/api/media/voice/status")
    def voice_status():
        return jsonify({"input_interface": "wav-metadata", "browser_recording": "not_implemented", "transcription": "not_configured", "verified": False, "reason": "没有配置或调用真实语音识别服务"})

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "请求内容过大；XLSX 文件最大允许 2 MB"}), 413

    @app.get("/<path:filename>")
    def public_file(filename: str):
        if filename not in PUBLIC_FILES:
            return jsonify({"error": "文件不存在"}), 404
        return send_from_directory(PROJECT_DIR, filename, mimetype=PUBLIC_MIMETYPES.get(Path(filename).suffix.lower()))

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("SAASGUIDE_PORT", "4173"))
    app.run(host="127.0.0.1", port=port, debug=False)
