"""Format error standar API (PRD §9)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id

log = logging.getLogger("spe")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: list[Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def not_found(entity: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{entity} tidak ditemukan")


def forbidden(message: str = "Akses ditolak") -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def conflict(message: str) -> ApiError:
    return ApiError(409, "CONFLICT", message)


def _body(code: str, message: str, details: list[Any] | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details or []},
        "meta": {"request_id": current_request_id()},
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(_body("VALIDATION_ERROR", "Input tidak valid", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        log.warning("integrity error: %s", exc.orig)
        return JSONResponse(
            _body("CONFLICT", "Data bertentangan dengan data yang sudah ada", [{"constraint": constraint}] if constraint else []),
            status_code=409,
        )

    @app.exception_handler(DBAPIError)
    async def _db(_: Request, exc: DBAPIError) -> JSONResponse:
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == "42501":  # insufficient_privilege, termasuk pelanggaran RLS
            return JSONResponse(_body("FORBIDDEN", "Operasi ditolak oleh kebijakan akses data"), status_code=403)
        log.exception("database error")
        return JSONResponse(_body("INTERNAL_ERROR", "Terjadi kesalahan pada database"), status_code=500)
