"""Versioned SQLite schema and human-approved action workflow."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(project_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(source_id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(document_id TEXT NOT NULL, version TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(document_id, version));
CREATE TABLE IF NOT EXISTS risk_candidates(candidate_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS risk_evidence(evidence_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, quote TEXT NOT NULL, source_location TEXT NOT NULL, FOREIGN KEY(candidate_id) REFERENCES risk_candidates(candidate_id));
CREATE TABLE IF NOT EXISTS human_decisions(decision_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, decision TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS action_items(action_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, title TEXT NOT NULL, owner_role TEXT NOT NULL, due_date TEXT NOT NULL, completion_signal TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(candidate_id) REFERENCES risk_candidates(candidate_id));
CREATE TABLE IF NOT EXISTS action_events(event_id TEXT PRIMARY KEY, action_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(action_id) REFERENCES action_items(action_id));
CREATE TABLE IF NOT EXISTS reports(report_id TEXT PRIMARY KEY, period TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feedback(feedback_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, useful INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_runs(run_id TEXT PRIMARY KEY, feature TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS error_logs(error_id TEXT PRIMARY KEY, code TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class StoreError(ValueError):
    pass


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback and close when used as a context manager."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migrate(path: Path) -> None:
    previous_version = 0
    if path.exists() and path.stat().st_size:
        try:
            with connect(path) as connection:
                has_migrations = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
                ).fetchone()
                if has_migrations:
                    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
                    previous_version = int(row[0] or 0)
        except sqlite3.DatabaseError:
            previous_version = 0
    if previous_version == 1:
        backup = path.with_suffix(path.suffix + ".pre-v2.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        candidate_columns = {row[1] for row in connection.execute("PRAGMA table_info(risk_candidates)")}
        for name in ("company_id", "task_id", "source_id", "scan_id", "evidence_json", "citations_json"):
            if name not in candidate_columns:
                connection.execute(f"ALTER TABLE risk_candidates ADD COLUMN {name} TEXT")
        action_columns = {row[1] for row in connection.execute("PRAGMA table_info(action_items)")}
        for name, definition in (
            ("risk_decision_id", "TEXT"),
            ("plan_run_id", "TEXT"),
            ("plan_step", "INTEGER"),
            ("task_id", "TEXT"),
            ("policy_reference", "TEXT"),
        ):
            if name not in action_columns:
                connection.execute(f"ALTER TABLE action_items ADD COLUMN {name} {definition}")
        connection.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)", (now_iso(),))
        connection.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)", (SCHEMA_VERSION, now_iso()))


def seed_demo(path: Path) -> None:
    migrate(path)
    stamp = now_iso()
    with connect(path) as connection:
        connection.execute("INSERT OR IGNORE INTO projects VALUES(?,?,?)", ("project-001", "星云 CRM 升级项目", stamp))
        connection.execute(
            "INSERT OR IGNORE INTO risk_candidates(candidate_id,project_id,title,status,created_at) VALUES(?,?,?,?,?)",
            ("candidate-interface", "project-001", "接口评审未通过影响联调", "confirmed", stamp),
        )
        connection.execute("INSERT OR IGNORE INTO risk_evidence VALUES(?,?,?,?)", ("evidence-interface", "candidate-interface", "接口评审未通过，等待架构组确认。", "周报段落 5"))
        connection.execute("INSERT OR IGNORE INTO human_decisions VALUES(?,?,?,?,?,?,?)", ("decision-risk-demo", "risk_candidate", "candidate-interface", "confirm", "演示用户", "固定测试确认", stamp))


def record_candidate_decision(
    path: Path,
    candidate: dict[str, Any],
    decision_record: dict[str, Any],
) -> dict[str, Any]:
    """Persist the candidate identity and its append-only human decision."""

    candidate_id = str(candidate.get("candidate_id", "")).strip()
    project_id = str(candidate.get("project_id", "")).strip()
    decision_id = str(decision_record.get("decision_id", "")).strip()
    if not candidate_id or not project_id or not decision_id:
        raise StoreError("候选风险、项目或人工决策编号缺失")
    stamp = str(decision_record.get("recorded_at") or now_iso())
    migrate(path)
    with connect(path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO projects(project_id,name,created_at) VALUES(?,?,?)",
            (project_id, str(candidate.get("project_name") or project_id)[:200], stamp),
        )
        connection.execute(
            """INSERT INTO risk_candidates(
                   candidate_id,project_id,title,status,created_at,company_id,task_id,
                   source_id,scan_id,evidence_json,citations_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(candidate_id) DO UPDATE SET
                   project_id=excluded.project_id,title=excluded.title,status=excluded.status,
                   company_id=excluded.company_id,task_id=excluded.task_id,
                   source_id=excluded.source_id,scan_id=excluded.scan_id,
                   evidence_json=excluded.evidence_json,citations_json=excluded.citations_json""",
            (
                candidate_id,
                project_id,
                str(candidate.get("title") or candidate_id)[:200],
                str(decision_record.get("decision") or "candidate"),
                stamp,
                str(candidate.get("company_id") or "")[:80],
                str(candidate.get("task_id") or "")[:80],
                str(candidate.get("source_id") or "")[:120],
                str(candidate.get("scan_id") or "")[:120],
                json.dumps(candidate.get("evidence") or [], ensure_ascii=False),
                json.dumps(candidate.get("citations") or [], ensure_ascii=False),
            ),
        )
        connection.execute(
            "INSERT INTO human_decisions VALUES(?,?,?,?,?,?,?)",
            (
                decision_id,
                "risk_candidate",
                candidate_id,
                str(decision_record.get("decision") or ""),
                str(decision_record.get("actor") or "本地演示用户")[:80],
                str(decision_record.get("note") or "")[:500],
                stamp,
            ),
        )
    return decision_record


def create_action(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("human_confirmed") is not True:
        raise StoreError("保存行动前必须明确人工确认")
    required = ("candidate_id", "title", "owner_role", "due_date", "completion_signal", "actor")
    values = {key: str(payload.get(key, "")).strip() for key in required}
    if any(not value for value in values.values()):
        raise StoreError("行动、负责人角色、期限、完成信号和确认人均为必填")
    try:
        date.fromisoformat(values["due_date"])
    except ValueError as error:
        raise StoreError("期限必须是 YYYY-MM-DD") from error
    stamp = now_iso()
    action_id = f"action-{uuid4().hex[:12]}"
    project_id = str(payload.get("project_id", "local-project")).strip() or "local-project"
    candidate_title = str(payload.get("candidate_title", values["title"])).strip() or values["title"]
    if len(project_id) > 80 or len(candidate_title) > 200:
        raise StoreError("候选风险引用无效")
    migrate(path)
    risk_decision_id = str(payload.get("risk_decision_id", "")).strip()
    with connect(path) as connection:
        candidate = connection.execute("SELECT 1 FROM risk_candidates WHERE candidate_id=?", (values["candidate_id"],)).fetchone()
        if not candidate:
            raise StoreError("候选风险尚未记录人工决策")
        latest_decision = connection.execute(
            "SELECT decision_id,decision FROM human_decisions WHERE entity_type='risk_candidate' AND entity_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
            (values["candidate_id"],),
        ).fetchone()
        if not latest_decision or latest_decision["decision"] != "confirm":
            raise StoreError("风险必须先由人工确认，才能创建行动")
        if risk_decision_id and risk_decision_id != latest_decision["decision_id"]:
            raise StoreError("行动必须引用当前有效的风险确认记录")
        risk_decision_id = latest_decision["decision_id"]
        connection.execute(
            """INSERT INTO action_items(
                   action_id,candidate_id,title,owner_role,due_date,completion_signal,status,
                   created_at,updated_at,risk_decision_id,plan_run_id,plan_step,task_id,policy_reference
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                action_id,
                values["candidate_id"],
                values["title"],
                values["owner_role"],
                values["due_date"],
                values["completion_signal"],
                "open",
                stamp,
                stamp,
                risk_decision_id,
                str(payload.get("plan_run_id") or "")[:120] or None,
                int(payload.get("plan_step") or 0) or None,
                str(payload.get("task_id") or "")[:80] or None,
                str(payload.get("policy_reference") or "")[:300] or None,
            ),
        )
        connection.execute("INSERT INTO human_decisions VALUES(?,?,?,?,?,?,?)", (f"decision-{uuid4().hex[:12]}", "action", action_id, "create", values["actor"], str(payload.get("note", ""))[:500], stamp))
        connection.execute("INSERT INTO action_events VALUES(?,?,?,?,?,?,?)", (f"event-{uuid4().hex[:12]}", action_id, None, "open", values["actor"], "人工确认创建", stamp))
    return get_action(path, action_id)


def get_action(path: Path, action_id: str) -> dict[str, Any]:
    with connect(path) as connection:
        row = connection.execute("SELECT * FROM action_items WHERE action_id=?", (action_id,)).fetchone()
        if not row:
            raise StoreError("行动不存在")
        events = [dict(item) for item in connection.execute("SELECT * FROM action_events WHERE action_id=? ORDER BY created_at,event_id", (action_id,))]
    return {**dict(row), "events": events}


def transition_action(path: Path, action_id: str, status: str, actor: str, note: str = "") -> dict[str, Any]:
    allowed = {
        "open": {"in_progress", "cancelled"},
        "in_progress": {"completed", "open", "cancelled"},
        "completed": {"open"},
        "cancelled": {"open"},
    }
    actor = str(actor).strip()
    if not actor:
        raise StoreError("请填写操作人")
    migrate(path)
    with connect(path) as connection:
        row = connection.execute("SELECT status FROM action_items WHERE action_id=?", (action_id,)).fetchone()
        if not row:
            raise StoreError("行动不存在")
        previous = row["status"]
        if status not in allowed.get(previous, set()):
            raise StoreError(f"不允许从 {previous} 变为 {status}")
        stamp = now_iso()
        connection.execute("UPDATE action_items SET status=?,updated_at=? WHERE action_id=?", (status, stamp, action_id))
        connection.execute("INSERT INTO action_events VALUES(?,?,?,?,?,?,?)", (f"event-{uuid4().hex[:12]}", action_id, previous, status, actor, str(note)[:500], stamp))
    return get_action(path, action_id)


def dashboard(path: Path, as_of: str | None = None) -> dict[str, Any]:
    today = date.fromisoformat(as_of) if as_of else date.today()
    migrate(path)
    with connect(path) as connection:
        actions = [dict(row) for row in connection.execute("SELECT * FROM action_items ORDER BY due_date,created_at")]
    for item in actions:
        item["overdue"] = item["status"] not in {"completed", "cancelled"} and date.fromisoformat(item["due_date"]) < today
    return {"actions": actions, "summary": {"total": len(actions), "open": sum(a["status"] in {"open", "in_progress"} for a in actions), "overdue": sum(a["overdue"] for a in actions), "completed": sum(a["status"] == "completed" for a in actions)}}


def schema_inventory(path: Path) -> list[str]:
    with connect(path) as connection:
        return [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
