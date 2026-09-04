"""Versioned SQLite schema and human-approved action workflow."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = 1

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
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)", (SCHEMA_VERSION, now_iso()))


def seed_demo(path: Path) -> None:
    migrate(path)
    stamp = now_iso()
    with connect(path) as connection:
        connection.execute("INSERT OR IGNORE INTO projects VALUES(?,?,?)", ("project-001", "星云 CRM 升级项目", stamp))
        connection.execute("INSERT OR IGNORE INTO risk_candidates VALUES(?,?,?,?,?)", ("candidate-interface", "project-001", "接口评审未通过影响联调", "confirmed", stamp))
        connection.execute("INSERT OR IGNORE INTO risk_evidence VALUES(?,?,?,?)", ("evidence-interface", "candidate-interface", "接口评审未通过，等待架构组确认。", "周报段落 5"))


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
    with connect(path) as connection:
        candidate = connection.execute("SELECT 1 FROM risk_candidates WHERE candidate_id=?", (values["candidate_id"],)).fetchone()
        if not candidate:
            raise StoreError("候选风险不存在")
        connection.execute("INSERT INTO action_items VALUES(?,?,?,?,?,?,?,?,?)", (action_id, values["candidate_id"], values["title"], values["owner_role"], values["due_date"], values["completion_signal"], "open", stamp, stamp))
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
    allowed = {"open": {"in_progress", "cancelled"}, "in_progress": {"completed", "open", "cancelled"}, "completed": set(), "cancelled": set()}
    actor = str(actor).strip()
    if not actor:
        raise StoreError("请填写操作人")
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
    with connect(path) as connection:
        actions = [dict(row) for row in connection.execute("SELECT * FROM action_items ORDER BY due_date,created_at")]
    for item in actions:
        item["overdue"] = item["status"] not in {"completed", "cancelled"} and date.fromisoformat(item["due_date"]) < today
    return {"actions": actions, "summary": {"total": len(actions), "open": sum(a["status"] in {"open", "in_progress"} for a in actions), "overdue": sum(a["overdue"] for a in actions), "completed": sum(a["status"] == "completed" for a in actions)}}


def schema_inventory(path: Path) -> list[str]:
    with connect(path) as connection:
        return [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
