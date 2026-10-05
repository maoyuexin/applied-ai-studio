"""SQLite run store: runs, steps, artifacts, decisions, events, media index and daily usage.

One connection guarded by a lock. Every statement is small, so calls are made directly from the
event loop; WAL mode keeps readers from blocking the writer.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  pipeline TEXT NOT NULL,
  title TEXT NOT NULL,
  template TEXT,
  status TEXT NOT NULL,
  brief TEXT NOT NULL DEFAULT '{}',
  settings TEXT NOT NULL DEFAULT '{}',
  parent_run_id TEXT,
  tags TEXT NOT NULL DEFAULT '[]',
  restricted INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'studio',
  current_step TEXT,
  counters TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  rev INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  key TEXT NOT NULL,
  title TEXT NOT NULL,
  gate INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  started_at TEXT,
  finished_at TEXT,
  PRIMARY KEY (run_id, key)
);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  step_key TEXT NOT NULL,
  kind TEXT NOT NULL,
  grp TEXT,
  label TEXT,
  parent_id TEXT,
  status TEXT NOT NULL,
  role TEXT,
  provider TEXT,
  deployment TEXT,
  model_version TEXT,
  prompt TEXT,
  inputs TEXT NOT NULL DEFAULT '[]',
  params TEXT NOT NULL DEFAULT '{}',
  vendor_job_id TEXT,
  progress INTEGER,
  media_sha TEXT,
  media_type TEXT,
  thumb_sha TEXT,
  gen_seconds REAL,
  metrics TEXT NOT NULL DEFAULT '{}',
  checks TEXT NOT NULL DEFAULT '[]',
  verdict TEXT,
  note TEXT,
  checklist TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  error_code TEXT,
  data TEXT NOT NULL DEFAULT '{}',
  seq INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_artifacts_run ON artifacts(run_id, step_key, seq);
CREATE INDEX IF NOT EXISTS ix_artifacts_status ON artifacts(status);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  artifact_id TEXT,
  step_key TEXT,
  action TEXT NOT NULL,
  verdict TEXT,
  note TEXT,
  checklist TEXT NOT NULL DEFAULT '{}',
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_decisions_run ON decisions(run_id, id);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  at TEXT NOT NULL,
  level TEXT NOT NULL,
  code TEXT,
  message TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_events_run ON events(run_id, id);
CREATE TABLE IF NOT EXISTS media (
  sha TEXT PRIMARY KEY,
  media_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  meta TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
  day TEXT NOT NULL,
  role TEXT NOT NULL,
  units REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (day, role)
);
"""

JSON_COLUMNS: dict[str, set[str]] = {
    "runs": {"brief", "settings", "tags", "counters"},
    "steps": {"data"},
    "artifacts": {"inputs", "params", "metrics", "checks", "checklist", "data"},
    "decisions": {"checklist"},
    "events": {"data"},
    "media": {"meta"},
}

UPDATABLE: dict[str, set[str]] = {
    "runs": {"title", "template", "status", "brief", "settings", "tags", "restricted", "current_step", "counters", "error"},
    "steps": {"title", "gate", "status", "data", "error", "started_at", "finished_at"},
    "artifacts": {
        "status", "label", "grp", "parent_id", "role", "provider", "deployment", "model_version", "prompt", "inputs",
        "params", "vendor_job_id", "progress", "media_sha", "media_type", "thumb_sha", "gen_seconds", "metrics",
        "checks", "verdict", "note", "checklist", "error", "error_code", "data",
    },
}

ACTIVE_ARTIFACT_STATUSES = ("queued", "running")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().astimezone().date().isoformat()


def new_run_id() -> str:
    return f"run_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{secrets.token_hex(2)}"


def new_artifact_id() -> str:
    return f"a_{secrets.token_hex(6)}"


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Low-level helpers

    def _decode(self, table: str, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        record = dict(row)
        for column in JSON_COLUMNS.get(table, ()):  # noqa: SIM118
            if column in record and isinstance(record[column], str):
                record[column] = json.loads(record[column])
        if table == "runs":
            record["restricted"] = bool(record["restricted"])
        if table == "steps":
            record["gate"] = bool(record["gate"])
        return record

    def _encode(self, table: str, fields: dict[str, Any]) -> dict[str, Any]:
        encoded = {}
        for key, value in fields.items():
            if key in JSON_COLUMNS.get(table, ()):
                encoded[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                encoded[key] = int(value)
            else:
                encoded[key] = value
        return encoded

    def _insert(self, table: str, fields: dict[str, Any]) -> None:
        encoded = self._encode(table, fields)
        columns = ", ".join(encoded)
        placeholders = ", ".join("?" for _ in encoded)
        self._db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(encoded.values()))

    def _update(self, table: str, where: str, params: tuple[Any, ...], fields: dict[str, Any]) -> None:
        unknown = set(fields) - UPDATABLE[table]
        if unknown:
            raise ValueError(f"Cannot update {table} columns: {sorted(unknown)}")
        encoded = self._encode(table, fields)
        if table in ("runs", "artifacts"):
            encoded["updated_at"] = now()
        assignments = ", ".join(f"{column} = ?" for column in encoded)
        self._db.execute(f"UPDATE {table} SET {assignments} WHERE {where}", (*encoded.values(), *params))

    # Runs

    def insert_run(self, run: dict[str, Any], steps: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._insert("runs", run)
                for step in steps:
                    self._insert("steps", {"run_id": run["id"], **step})
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return self.get_run(run["id"])  # type: ignore[return-value]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._decode("runs", row)

    def list_runs(
        self,
        *,
        pipeline: str | None = None,
        status: str | None = None,
        query: str | None = None,
        tag: str | None = None,
        since: str | None = None,
        include_restricted: bool = True,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if pipeline:
            clauses.append("pipeline = ?")
            params.append(pipeline)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if query:
            clauses.append("(title LIKE ? OR brief LIKE ? OR id LIKE ?)")
            params.extend([f"%{query}%"] * 3)
        if tag:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        if not include_restricted:
            clauses.append("restricted = 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT ?", (*params, limit)
            ).fetchall()
        return [self._decode("runs", row) for row in rows]  # type: ignore[misc]

    def update_run(self, run_id: str, **fields: Any) -> None:
        with self._lock:
            self._update("runs", "id = ?", (run_id,), fields)

    def bump(self, run_id: str) -> int:
        with self._lock:
            self._db.execute("UPDATE runs SET rev = rev + 1, updated_at = ? WHERE id = ?", (now(), run_id))
            row = self._db.execute("SELECT rev FROM runs WHERE id = ?", (run_id,)).fetchone()
        return int(row["rev"]) if row else 0

    def delete_run(self, run_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def all_tags(self) -> list[str]:
        with self._lock:
            rows = self._db.execute("SELECT tags FROM runs").fetchall()
        tags: set[str] = set()
        for row in rows:
            tags.update(json.loads(row["tags"]))
        return sorted(tags)

    # Steps

    def get_steps(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY idx", (run_id,)).fetchall()
        return [self._decode("steps", row) for row in rows]  # type: ignore[misc]

    def get_step(self, run_id: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM steps WHERE run_id = ? AND key = ?", (run_id, key)).fetchone()
        return self._decode("steps", row)

    def update_step(self, run_id: str, key: str, **fields: Any) -> None:
        with self._lock:
            self._update("steps", "run_id = ? AND key = ?", (run_id, key), fields)

    # Artifacts

    def insert_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        stamp = now()
        record = {"id": new_artifact_id(), "created_at": stamp, "updated_at": stamp, **artifact}
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM artifacts WHERE run_id = ?", (record["run_id"],)
            ).fetchone()
            record.setdefault("seq", int(row["next"]))
            self._insert("artifacts", record)
        return self.get_artifact(record["id"])  # type: ignore[return-value]

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return self._decode("artifacts", row)

    def list_artifacts(
        self, run_id: str, *, step_key: str | None = None, kind: str | None = None, grp: str | None = None
    ) -> list[dict[str, Any]]:
        clauses, params = ["run_id = ?"], [run_id]
        for column, value in (("step_key", step_key), ("kind", kind), ("grp", grp)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM artifacts WHERE {' AND '.join(clauses)} ORDER BY seq", tuple(params)
            ).fetchall()
        return [self._decode("artifacts", row) for row in rows]  # type: ignore[misc]

    def active_artifacts(self, run_id: str | None = None) -> list[dict[str, Any]]:
        placeholders = ", ".join("?" for _ in ACTIVE_ARTIFACT_STATUSES)
        sql = f"SELECT * FROM artifacts WHERE status IN ({placeholders})"
        params: tuple[Any, ...] = ACTIVE_ARTIFACT_STATUSES
        if run_id:
            sql += " AND run_id = ?"
            params = (*params, run_id)
        with self._lock:
            rows = self._db.execute(sql + " ORDER BY seq", params).fetchall()
        return [self._decode("artifacts", row) for row in rows]  # type: ignore[misc]

    def update_artifact(self, artifact_id: str, **fields: Any) -> None:
        with self._lock:
            self._update("artifacts", "id = ?", (artifact_id,), fields)

    # Decisions and events

    def add_decision(self, run_id: str, action: str, **fields: Any) -> None:
        with self._lock:
            self._insert("decisions", {"run_id": run_id, "action": action, "at": now(), **fields})

    def list_decisions(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM decisions WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        return [self._decode("decisions", row) for row in rows]  # type: ignore[misc]

    def add_event(
        self, run_id: str, level: str, message: str, *, code: str | None = None, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        record = {"run_id": run_id, "at": now(), "level": level, "code": code, "message": message, "data": data or {}}
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO events (run_id, at, level, code, message, data) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, record["at"], level, code, message, json.dumps(record["data"], ensure_ascii=False)),
            )
            record["id"] = cursor.lastrowid
        return record

    def list_events(self, run_id: str, limit: int = 300) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT * FROM events WHERE run_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id",
                (run_id, limit),
            ).fetchall()
        return [self._decode("events", row) for row in rows]  # type: ignore[misc]

    def import_rows(
        self, run: dict[str, Any], steps: list[dict[str, Any]], artifacts: list[dict[str, Any]],
        decisions: list[dict[str, Any]], events: list[dict[str, Any]],
    ) -> None:
        """Insert a whole run (from a bundle or the importer) in one transaction, keeping its ids."""
        run_columns = {"id", "pipeline", "title", "template", "status", "brief", "settings", "parent_run_id", "tags",
                       "restricted", "source", "current_step", "counters", "error", "rev", "created_at", "updated_at"}
        step_columns = {"run_id", "idx", "key", "title", "gate", "status", "data", "error", "started_at", "finished_at"}
        artifact_columns = UPDATABLE["artifacts"] | {"id", "run_id", "step_key", "kind", "seq", "created_at",
                                                      "updated_at"}
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._insert("runs", {k: v for k, v in run.items() if k in run_columns})
                for step in steps:
                    self._insert("steps", {k: v for k, v in {**step, "run_id": run["id"]}.items() if k in step_columns})
                for artifact in artifacts:
                    row = {k: v for k, v in {**artifact, "run_id": run["id"]}.items() if k in artifact_columns}
                    self._insert("artifacts", row)
                for decision in decisions:
                    row = {k: decision.get(k) for k in ("artifact_id", "step_key", "action", "verdict", "note", "at")}
                    self._insert("decisions", {**row, "run_id": run["id"], "checklist": decision.get("checklist") or {}})
                for event in events:
                    row = {k: event.get(k) for k in ("at", "level", "code", "message")}
                    self._insert("events", {**row, "run_id": run["id"], "data": event.get("data") or {}})
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    # Media index

    def put_media(self, sha: str, media_type: str, size: int, meta: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO media (sha, media_type, size, meta, created_at) VALUES (?, ?, ?, ?, ?)",
                (sha, media_type, size, json.dumps(meta or {}), now()),
            )

    def get_media(self, sha: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM media WHERE sha = ?", (sha,)).fetchone()
        return self._decode("media", row)

    def unreferenced_media(self, older_than: str | None = None) -> list[str]:
        sql = (
            "SELECT sha FROM media WHERE sha NOT IN (SELECT media_sha FROM artifacts WHERE media_sha IS NOT NULL) "
            "AND sha NOT IN (SELECT thumb_sha FROM artifacts WHERE thumb_sha IS NOT NULL)"
        )
        params: tuple[Any, ...] = ()
        if older_than:
            sql += " AND created_at < ?"
            params = (older_than,)
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        return [row["sha"] for row in rows]

    def delete_media_rows(self, shas: Iterable[str]) -> None:
        with self._lock:
            self._db.executemany("DELETE FROM media WHERE sha = ?", [(sha,) for sha in shas])

    def media_total_bytes(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(SUM(size), 0) AS total FROM media").fetchone()
        return int(row["total"])

    # Daily usage and caps

    def usage(self, day: str | None = None) -> dict[str, float]:
        with self._lock:
            rows = self._db.execute("SELECT role, units FROM usage WHERE day = ?", (day or today(),)).fetchall()
        return {row["role"]: float(row["units"]) for row in rows}

    def try_reserve(self, role: str, units: float, cap: float) -> bool:
        """Atomically add usage if it stays within the cap. Returns False when the cap would be exceeded."""
        day = today()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute("SELECT units FROM usage WHERE day = ? AND role = ?", (day, role)).fetchone()
                used = float(row["units"]) if row else 0.0
                if used + units > cap:
                    self._db.execute("ROLLBACK")
                    return False
                self._db.execute(
                    "INSERT INTO usage (day, role, units) VALUES (?, ?, ?) "
                    "ON CONFLICT(day, role) DO UPDATE SET units = units + excluded.units",
                    (day, role, units),
                )
                self._db.execute("COMMIT")
                return True
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def release(self, role: str, units: float) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE usage SET units = MAX(units - ?, 0) WHERE day = ? AND role = ?", (units, today(), role)
            )
