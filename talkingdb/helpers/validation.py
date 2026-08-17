import os
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile, status

from talkingdb.models.failure import messages
from talkingdb.models.failure.reason import FailureReason


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default

DEFAULT_MAX_FILE_SIZE_MB = _env_int("TDB_MAX_FILE_SIZE_MB", 50)

SUPPORTED_TYPES: Dict[str, Dict[str, Any]] = {
    "pdf": {
        "mime_type": "application/pdf",
        "max_file_size_mb": _env_int("TDB_MAX_PDF_FILE_SIZE_MB", 25),
    },
    "docx": {
        "mime_type": (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        "max_file_size_mb": _env_int(
            "TDB_MAX_DOCX_FILE_SIZE_MB", DEFAULT_MAX_FILE_SIZE_MB
        ),
    },
}

MULTIPART_ENVELOPE_ALLOWANCE_BYTES = _env_int(
    "TDB_MULTIPART_ENVELOPE_ALLOWANCE_BYTES", 1024 * 1024
)

ALLOWED_EXTENSIONS = set(SUPPORTED_TYPES)
MAX_FILE_SIZE_MB = DEFAULT_MAX_FILE_SIZE_MB
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def ext_of(filename: Optional[str]) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


_ext_of = ext_of


def max_file_size_mb_for(ext: Optional[str]) -> int:
    spec = SUPPORTED_TYPES.get((ext or "").lower())
    return spec["max_file_size_mb"] if spec else DEFAULT_MAX_FILE_SIZE_MB


def max_file_size_bytes_for(ext: Optional[str]) -> int:
    return max_file_size_mb_for(ext) * 1024 * 1024


def supported_upload_types() -> List[Dict[str, Any]]:
    return [
        {
            "extension": ext,
            "mime_type": spec["mime_type"],
            "max_file_size_mb": spec["max_file_size_mb"],
        }
        for ext, spec in sorted(SUPPORTED_TYPES.items())
    ]


def max_supported_file_size_mb() -> int:
    return max(spec["max_file_size_mb"] for spec in SUPPORTED_TYPES.values())


def content_length_over_every_cap(content_length: Optional[str]) -> Optional[int]:
    if content_length is None:
        return None
    try:
        declared_bytes = int(content_length)
    except (TypeError, ValueError):
        return None
    if declared_bytes < 0:
        return None

    cap_mb = max_supported_file_size_mb()
    ceiling = cap_mb * 1024 * 1024 + MULTIPART_ENVELOPE_ALLOWANCE_BYTES
    return cap_mb if declared_bytes > ceiling else None


def validate_file_type(file: UploadFile) -> str:
    ext = _ext_of(file.filename)
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error_code": FailureReason.UNSUPPORTED_FILE_TYPE.value,
                "failure_reason": FailureReason.UNSUPPORTED_FILE_TYPE.value,
                "message": messages.unsupported_file_type_message(
                    SUPPORTED_TYPES
                ),
                "supported_types": sorted(SUPPORTED_TYPES),
            },
        )
    return ext


def assert_content_length_within_cap(
    content_length: Optional[str],
    ext: Optional[str],
) -> None:
    if content_length is None:
        return
    try:
        declared_bytes = int(content_length)
    except (TypeError, ValueError):
        return
    if declared_bytes < 0:
        return

    cap_mb = max_file_size_mb_for(ext)
    ceiling = cap_mb * 1024 * 1024 + MULTIPART_ENVELOPE_ALLOWANCE_BYTES
    if declared_bytes <= ceiling:
        return

    raise HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail={
            "error_code": FailureReason.FILE_TOO_LARGE.value,
            "failure_reason": FailureReason.FILE_TOO_LARGE.value,
            "message": messages.file_too_large_message(cap_mb),
            "max_file_size_mb": cap_mb,
        },
    )
