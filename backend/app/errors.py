"""Erros da API. A API devolve só o código; o frontend mostra a mensagem em PT ou EN."""

from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    TOO_MANY_PAGES = "too_many_pages"
    PDF_PASSWORD = "pdf_password"
    MULTIPLE_FILES = "multiple_files"
    TOO_MANY_ACTIVE_JOBS = "too_many_active_jobs"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    NOT_READY = "not_ready"
    EXPORT_FAILED = "export_failed"


class ApiError(Exception):
    def __init__(self, status_code: int, code: ErrorCode) -> None:
        super().__init__(code.value)
        self.status_code = status_code
        self.code = code


class UploadRejectedError(ApiError):
    """Arquivo recusado antes de virar uma conversão."""


async def api_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code.value})
