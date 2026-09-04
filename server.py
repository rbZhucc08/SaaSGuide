"""Local Flask application that connects the SaaSGuide phase-five workflow."""

from __future__ import annotations

import html
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory, url_for

from deepseek_ask_build import DeepSeekError, ModelOutputError, evaluate_brief
from deepseek_risk_assistant import analyze_risk
from validate_data import RISK_FILE, validate_risk_data


PROJECT_DIR = Path(__file__).resolve().parent
GENERATED_DIR = PROJECT_DIR / "generated"
RISK_WRITE_LOCK = threading.Lock()
PUBLIC_FILES = {
    "index.html",
    "styles.css",
    "app.js",
    "guide-data.json",
    "risk-data.json",
    "builder.html",
    "builder.css",
    "builder.js",
}


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
    risk_file: Path = RISK_FILE,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    @app.get("/")
    def dashboard():
        return send_from_directory(PROJECT_DIR, "index.html")

    @app.get("/builder")
    @app.get("/builder.html")
    def builder():
        return send_from_directory(PROJECT_DIR, "builder.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        if filename not in PUBLIC_FILES:
            return jsonify({"error": "文件不存在"}), 404
        return send_from_directory(PROJECT_DIR, filename)

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

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "Brief 内容过长，最大允许 64 KB"}), 413

    @app.get("/<path:filename>")
    def public_file(filename: str):
        if filename not in PUBLIC_FILES:
            return jsonify({"error": "文件不存在"}), 404
        return send_from_directory(PROJECT_DIR, filename)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("SAASGUIDE_PORT", "4173"))
    app.run(host="127.0.0.1", port=port, debug=False)
