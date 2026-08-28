"""SQLite persistence for the file <-> graph mapping table."""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from talkingdb.models.file_graph.file_graph import FileGraphMappingModel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(conn: sqlite3.Connection) -> None:
    """Create the file_graph_mapping table and indexes (idempotent)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS file_graph_mapping (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel     TEXT NOT NULL,
            file_hash   TEXT NOT NULL,
            graph_id    TEXT,
            job_id      TEXT NOT NULL,
            filename    TEXT,
            created_at  TEXT,
            updated_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_fgm_graph_id ON file_graph_mapping(graph_id);
        CREATE INDEX IF NOT EXISTS idx_fgm_channel_hash   ON file_graph_mapping(channel, file_hash);
        CREATE INDEX IF NOT EXISTS idx_fgm_job_id    ON file_graph_mapping(job_id);
        """
    )


def _row_to_model(row: sqlite3.Row) -> FileGraphMappingModel:
    return FileGraphMappingModel(
        channel=row["channel"],
        file_hash=row["file_hash"],
        graph_id=row["graph_id"],
        job_id=row["job_id"],
        filename=row["filename"],
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def insert(
    conn: sqlite3.Connection,
    *,
    channel: str,
    file_hash: str,
    job_id: str,
    filename: Optional[str] = None,
    graph_id: Optional[str] = None,
) -> None:
    """Insert a mapping row at upload time (graph_id is usually still None)."""
    now = _now_iso()
    with conn:
        conn.execute(
            """
            INSERT INTO file_graph_mapping
                (channel, file_hash, graph_id, job_id, filename, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (channel, file_hash, graph_id, job_id, filename, now, now),
        )


def set_graph_id(conn: sqlite3.Connection, job_id: str, graph_id: str) -> None:
    """Attach graph_id once the indexer has generated it."""
    with conn:
        conn.execute(
            """
            UPDATE file_graph_mapping
            SET graph_id = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (graph_id, _now_iso(), job_id),
        )


def update_file_hash(conn: sqlite3.Connection, job_id: str, file_hash: str) -> None:
    """Point a job's mapping at the final stored blob hash (e.g. baked docx)."""
    with conn:
        conn.execute(
            """
            UPDATE file_graph_mapping
            SET file_hash = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (file_hash, _now_iso(), job_id),
        )


def get_by_job_id(conn: sqlite3.Connection, job_id: str) -> Optional[FileGraphMappingModel]:
    row = conn.execute(
        "SELECT * FROM file_graph_mapping WHERE job_id = ? ORDER BY id DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    return _row_to_model(row) if row else None


def delete_by_job_id(conn: sqlite3.Connection, job_id: str) -> None:
    with conn:
        conn.execute(
            "DELETE FROM file_graph_mapping WHERE job_id = ?", (job_id,)
        )


def get_by_channel_hash(conn: sqlite3.Connection, channel: str, file_hash: str) -> list[FileGraphMappingModel]:
    """Used to check whether a blob is still referenced before deleting it from MinIO."""
    rows = conn.execute(
        "SELECT * FROM file_graph_mapping WHERE channel = ? AND file_hash = ?",
        (channel, file_hash),
    ).fetchall()
    return [_row_to_model(row) for row in rows]

def get_by_graph_id(
    conn: sqlite3.Connection, graph_id: str
) -> Optional[FileGraphMappingModel]:
    row = conn.execute(
        "SELECT * FROM file_graph_mapping WHERE graph_id = ? ORDER BY id DESC LIMIT 1",
        (graph_id,),
    ).fetchone()
    return _row_to_model(row) if row else None


def delete_by_graph_id(conn: sqlite3.Connection, graph_id: str) -> None:
    with conn:
        conn.execute(
            "DELETE FROM file_graph_mapping WHERE graph_id = ?", (graph_id,)
        )