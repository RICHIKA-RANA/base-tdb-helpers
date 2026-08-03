import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_id() -> str:
    return f"proj::{uuid4().hex}"


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id      TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            logo            TEXT,
            logo_media_type TEXT,
            owner_email     TEXT NOT NULL,
            created_at      TEXT,
            updated_at      TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_projects_owner
            ON projects(owner_email);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_owner_name
            ON projects(owner_email, lower(name));
        """
    )


# ----------------------------------------------------------------- row mapping
def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "project_id": row["project_id"],
        "name": row["name"],
        "logo": row["logo"],
        "logo_media_type": row["logo_media_type"],
        "owner_email": row["owner_email"],
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


# ----------------------------------------------------------------------- writes
def create(
    conn: sqlite3.Connection,
    *,
    name: str,
    logo: Optional[str],
    logo_media_type: Optional[str],
    owner_email: str,
) -> Dict[str, Any]:
    now = _now_iso()
    project_id = make_id()
    conn.execute(
        """
        INSERT INTO projects (
            project_id, name, logo, logo_media_type,
            owner_email, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, name, logo, logo_media_type, owner_email, now, now),
    )
    return get(conn, project_id)


# ------------------------------------------------------------------------ reads
def get(conn: sqlite3.Connection, project_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM projects WHERE project_id = ?", (project_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_for_owner(
    conn: sqlite3.Connection, project_id: str, owner_email: str
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM projects WHERE project_id = ? AND owner_email = ?",
        (project_id, owner_email),
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_for_owner(
    conn: sqlite3.Connection,
    owner_email: str,
    *,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM projects WHERE owner_email = ? "
        "ORDER BY created_at DESC, project_id DESC LIMIT ? OFFSET ?",
        (owner_email, limit, offset),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
