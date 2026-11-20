"""API errors: one JSON shape, `{"detail": ..., "code": ...}` plus optional extra fields."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str, **extra: Any) -> None:
        self.status, self.code, self.detail, self.extra = status, code, detail, extra


def unauthorized(detail: str = "Sign in first.") -> ApiError:
    return ApiError(401, "unauthorized", detail)


def forbidden(detail: str) -> ApiError:
    return ApiError(403, "forbidden", detail)


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} not found.")


def conflict(code: str, detail: str, **extra: Any) -> ApiError:
    return ApiError(409, code, detail, **extra)


def invalid(detail: str) -> ApiError:
    return ApiError(422, "invalid", detail)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            {"detail": exc.detail, "code": exc.code, **exc.extra}, status_code=exc.status
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        # The API checks rules first; this is the database safety net (design.md §3).
        return JSONResponse(
            {"detail": "The change conflicts with existing data.", "code": "integrity"},
            status_code=409,
        )
