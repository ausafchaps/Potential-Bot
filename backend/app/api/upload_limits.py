from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.auth_rate_limit import client_identity
from app.api.dependencies import CurrentUser, Database
from app.core.config import settings
from app.services.auth_rate_limit import (
    AttemptLimit,
    AuthRateLimited,
    AuthRateLimitUnavailable,
    consume_attempts,
)
from app.services.storage import StorageUnavailable, UploadLimited, check_file_size


def upload_limited(request: Request, exc: UploadLimited) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)},
                        headers={"Cache-Control": "no-store"})


def storage_unavailable(request: Request, exc: StorageUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={
        "detail": "Note storage is temporarily unavailable. Please try again shortly."},
        headers={"Retry-After": "30", "Cache-Control": "no-store"})


def limit_uploads(request: Request, db: Database, user: CurrentUser) -> None:
    try:
        identity = client_identity(request)
    except HTTPException as exc:
        raise StorageUnavailable() from exc
    try:
        consume_attempts(db, [
            AttemptLimit("upload-ip", identity, settings.upload_ip_hourly_limit, 3600),
            AttemptLimit("upload-user", str(user.id), settings.upload_user_hourly_limit, 3600),
            AttemptLimit("upload-project", "project", settings.upload_project_hourly_limit, 3600),
        ])
    except AuthRateLimited as exc:
        raise HTTPException(429,
                            f"Too many upload attempts. Try again in {exc.retry_after} seconds.",
                            headers={"Retry-After": str(exc.retry_after),
                                     "Cache-Control": "no-store"}) from exc
    except AuthRateLimitUnavailable as exc:
        raise StorageUnavailable() from exc


async def read_upload(file: UploadFile) -> bytes:
    try:
        raw_content = await file.read(settings.upload_max_bytes + 1)
        check_file_size(raw_content)
        return raw_content
    finally:
        await file.close()
