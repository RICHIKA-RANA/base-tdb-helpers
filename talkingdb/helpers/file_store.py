"""Content-addressed file storage in MinIO: hashing, path-building, upload/fetch.

Layout: {bucket}/files/{rc}/{hash[0:2]}/{hash[2:4]}/{hash}
`rc` isolates release channels (including "localhost"); within a channel,
files dedup by md5 hash.
"""

import hashlib
from datetime import timedelta
from typing import Optional

from talkingdb.clients.minio import get_minio_client, MINIO_BUCKET, ensure_bucket


def compute_md5(local_path: str, chunk_size: int = 1024 * 1024) -> str:
    """Stream-hash a file on disk so large uploads don't load into memory."""
    hasher = hashlib.md5()
    with open(local_path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def object_path(rc: str, file_hash: str) -> str:
    """Build the sharded MinIO object key for a given (rc, hash)."""
    return f"files/{rc}/{file_hash[0:2]}/{file_hash[2:4]}/{file_hash}"


def upload_file(rc: str, file_hash: str, local_path: str) -> str:
    """Upload to MinIO under its content-addressed path.

    No-op if the object already exists for this (rc, hash) - this is the
    per-channel dedup.
    """
    client = get_minio_client()
    ensure_bucket()
    key = object_path(rc, file_hash)

    try:
        client.stat_object(MINIO_BUCKET, key)
        return key
    except Exception:
        pass

    client.fput_object(MINIO_BUCKET, key, local_path)
    return key


def get_presigned_url(
    rc: str, file_hash: str, expires_minutes: int = 15
) -> Optional[str]:
    """Time-limited URL the frontend can fetch the file from directly."""
    client = get_minio_client()
    key = object_path(rc, file_hash)
    try:
        return client.presigned_get_object(
            MINIO_BUCKET, key, expires=timedelta(minutes=expires_minutes)
        )
    except Exception:
        return None

def get_file_stream(rc: str, file_hash: str):
    """Open a streaming read of the object from MinIO.

    Returns the raw urllib3 response (has .read(chunk) and must be closed
    by the caller via .close() + .release_conn()), or None if missing.
    """
    client = get_minio_client()
    key = object_path(rc, file_hash)
    try:
        return client.get_object(MINIO_BUCKET, key)
    except Exception:
        return None