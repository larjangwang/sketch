from __future__ import annotations

import json
import re
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from sketch_assistant.config import ensure_workspace, read_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-zก-๙_-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or "project"


class ProjectStore:
    def __init__(self, workspace_dir: Path | None = None) -> None:
        self.workspace_dir = workspace_dir or ensure_workspace(read_settings())
        self.projects_dir = self.workspace_dir / "Projects"
        self.db_path = self.workspace_dir / "assistant.sqlite"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    client TEXT NOT NULL DEFAULT '',
                    authority TEXT NOT NULL DEFAULT '',
                    building_type TEXT NOT NULL DEFAULT '',
                    root_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS checklist_status (
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    checklist_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, checklist_id)
                );
                """
            )

    def create_project(self, name: str, client: str, authority: str, building_type: str) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        timestamp = utc_now()
        folder_name = f"{slugify(name)}-{project_id[:8]}"
        root_path = self.projects_dir / folder_name
        for child in ("sketches", "references", "generated", "exports", "revisions"):
            (root_path / child).mkdir(parents=True, exist_ok=True)

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (id, name, client, authority, building_type, root_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, name.strip(), client.strip(), authority.strip(), building_type.strip(), str(root_path), timestamp, timestamp),
            )
        return self.get_project(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY updated_at DESC, created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(f"Project not found: {project_id}")
        return dict(row)

    def update_project_timestamp(self, project_id: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (utc_now(), project_id))

    def add_artifact(self, project_id: str, kind: str, title: str, path: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        artifact_id = str(uuid.uuid4())
        timestamp = utc_now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (id, project_id, kind, title, path, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, project_id, kind, title, str(path), metadata_json, timestamp),
            )
            connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (timestamp, project_id))
        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(f"Artifact not found: {artifact_id}")
        artifact = dict(row)
        artifact["metadata"] = json.loads(artifact.pop("metadata_json") or "{}")
        return artifact

    def list_artifacts(self, project_id: str, kinds: Iterable[str] | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [project_id]
        query = "SELECT * FROM artifacts WHERE project_id = ?"
        if kinds:
            kind_list = list(kinds)
            placeholders = ",".join("?" for _ in kind_list)
            query += f" AND kind IN ({placeholders})"
            params.extend(kind_list)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        artifacts = []
        for row in rows:
            artifact = dict(row)
            artifact["metadata"] = json.loads(artifact.pop("metadata_json") or "{}")
            artifacts.append(artifact)
        return artifacts

    def import_file(self, project_id: str, source_path: Path, kind: str = "sketch") -> dict[str, Any]:
        project = self.get_project(project_id)
        target_dir = Path(project["root_path"]) / ("sketches" if kind == "sketch" else "references")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source_path.name
        if target_path.exists():
            target_path = target_dir / f"{source_path.stem}-{datetime.now().strftime('%Y%m%d%H%M%S')}{source_path.suffix}"
        shutil.copy2(source_path, target_path)
        return self.add_artifact(project_id, kind, source_path.name, target_path, {"source": str(source_path)})

    def save_checklist_status(self, project_id: str, checklist_id: str, status: str, note: str = "") -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO checklist_status (project_id, checklist_id, status, note, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, checklist_id)
                DO UPDATE SET status = excluded.status, note = excluded.note, updated_at = excluded.updated_at
                """,
                (project_id, checklist_id, status, note, utc_now()),
            )
            connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (utc_now(), project_id))

    def checklist_status_map(self, project_id: str) -> dict[str, dict[str, str]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT checklist_id, status, note FROM checklist_status WHERE project_id = ?", (project_id,)).fetchall()
        return {row["checklist_id"]: {"status": row["status"], "note": row["note"]} for row in rows}
