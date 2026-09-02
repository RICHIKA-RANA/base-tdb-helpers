"""Content-addressed file storage in MinIO: hashing, path-building, upload/fetch.

Layout: {bucket}/files/{channel}/{hash[0:2]}/{hash[2:4]}/{hash}
`rc` isolates release channels (including "localhost"); within a channel,
files dedup by sha256 hash.
"""

import hashlib
from datetime import timedelta
from typing import Optional
from minio.error import S3Error

from talkingdb.clients.minio import get_minio_client, is_configured, MINIO_BUCKET
from talkingdb.logger.console import logger


def compute_sha256(local_path: str, chunk_size: int = 1024 * 1024) -> str:
    """Stream-hash a file on disk so large uploads don't load into memory."""
    hasher = hashlib.sha256()
    with open(local_path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def object_path(channel: str, file_hash: str) -> str:
    """Build the sharded MinIO object key for a given (channel, hash)."""
    return f"files/{channel}/{file_hash[0:2]}/{file_hash[2:4]}/{file_hash}"


def upload_file(channel: str, file_hash: str, local_path: str) -> Optional[str]:
    """Upload to MinIO under its content-addressed path.

    No-op if the object already exists for this (channel, hash) - this is the
    per-channel dedup.
    """
    if not is_configured():
        logger.warning(
            "MinIO not configured - skipping storage of file (channel=%s, hash=%s)",
            channel, file_hash,
        )
        return None

    client = get_minio_client()

    key = object_path(channel, file_hash)

    try:
        client.stat_object(MINIO_BUCKET, key)
        return key
    except S3Error as e:
        if e.code != "NoSuchKey":
            raise

    client.fput_object(MINIO_BUCKET, key, local_path)
    return key


def overwrite_file(channel: str, file_hash: str, local_path: str) -> Optional[str]:
    """Upload to MinIO under (channel, file_hash), replacing any existing
    object at that key.

    The key (channel, file_hash) never changes - only the bytes behind it do -
    so there's no DB row to repoint and nothing to race.
    """
    if not is_configured():
        logger.warning(
            "MinIO not configured - skipping overwrite of file (channel=%s, hash=%s)",
            channel, file_hash,
        )
        return None

    client = get_minio_client()
    key = object_path(channel, file_hash)
    client.fput_object(MINIO_BUCKET, key, local_path)
    return key


def get_presigned_url(
    channel: str, file_hash: str, expires_minutes: int = 15
) -> Optional[str]:
    """Time-limited URL the frontend can fetch the file from directly.

    Returns None if MinIO isn't configured - there's nothing stored to link to.
    """
    if not is_configured():
        return None
    client = get_minio_client()
    key = object_path(channel, file_hash)
    try:
        return client.presigned_get_object(
            MINIO_BUCKET, key, expires=timedelta(minutes=expires_minutes)
        )
    except S3Error as e:
        if e.code == "NoSuchKey":
            return None
        raise

def stat_file(channel: str, file_hash: str):
    """Return the object's stat info (has .size), or None if missing.

    Also returns None, if MinIO isn't configured.
    """
    if not is_configured():
        return None
    client = get_minio_client()
    key = object_path(channel, file_hash)
    try:
        return client.stat_object(MINIO_BUCKET, key)
    except S3Error as e:
        if e.code == "NoSuchKey":
            return None
        raise


def get_file_stream(channel: str, file_hash: str):
    """Open a streaming read of the object from MinIO.

    Returns the raw urllib3 response (has .read(chunk) and must be closed
    by the caller via .close() + .release_conn()), or None if missing or if
    MinIO isn't configured.
    """
    if not is_configured():
        return None
    client = get_minio_client()
    key = object_path(channel, file_hash)
    try:
        return client.get_object(MINIO_BUCKET, key)
    except S3Error as e:
        if e.code == "NoSuchKey":
            return None
        raise

def delete_file(channel: str, file_hash: str) -> None:
    """Idempotent - safe to call even if the object is already gone.

    No-op if MinIO isn't configured - there's nothing to delete.
    """
    if not is_configured():
        return None
    client = get_minio_client()
    key = object_path(channel, file_hash)
    try:
        client.remove_object(MINIO_BUCKET, key)
    except S3Error as e:
        if e.code == "NoSuchKey":
            return None
        raise