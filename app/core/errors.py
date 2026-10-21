"""Consistent error handling for the whole API.

Every error response has the same shape:
    {"detail": <message or list of validation problems>, "code": "<machine_readable_code>"}
so a frontend can always read `detail` for humans and `code` for logic.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("bluntscore.errors")

_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "too_many_requests",
}


class AppError(Exception):
    """Base class for errors raised on purpose by our own code."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


def _error(status_code: int, detail, code: str, headers=None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code}, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError):
        return _error(exc.status_code, exc.message, exc.code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, exc.detail, _CODES.get(exc.status_code, "http_error"),
                      getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        return _error(422, jsonable_encoder(exc.errors()), "validation_error")

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_request: Request, exc: IntegrityError):
        logger.warning("Integrity error: %s", exc.orig)
        return _error(409, "The request conflicts with existing data", "conflict")

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "Internal server error", "internal_error")
