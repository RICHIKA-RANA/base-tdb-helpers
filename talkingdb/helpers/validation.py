from fastapi import HTTPException, UploadFile, status

from talkingdb.helpers.client import config


def validate_file_type(file: UploadFile) -> str:
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error_code": "UNSUPPORTED_FILE_TYPE",
                "message": f"File type '.{ext}' is not supported" if ext else "File has no extension",
                "supported_types": sorted(config.ALLOWED_EXTENSIONS),
            },
        )
    return ext


async def validate_file_size(file: UploadFile) -> int:
    contents = await file.read()
    file_size = len(contents)
    if file_size > config.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error_code": "FILE_TOO_LARGE",
                "message": (
                    f"File size ({file_size // (1024 * 1024)}MB) "
                    f"exceeds the maximum allowed size ({config.MAX_FILE_SIZE_MB}MB)"
                ),
                "max_file_size_mb": config.MAX_FILE_SIZE_MB,
            },
        )
    await file.seek(0)
    return file_size
