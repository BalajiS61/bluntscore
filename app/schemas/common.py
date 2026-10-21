"""Shared response shapes and documented error responses."""
from typing import Any, Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int


class ErrorOut(BaseModel):
    """Shape of every error response the API returns."""

    detail: Any
    code: str


def error_responses(*codes: int) -> dict:
    """OpenAPI docs for the error codes a route can return, so Swagger shows them."""
    descriptions = {
        400: "Bad request",
        404: "Not found",
        409: "Conflict with existing data",
        413: "Upload too large",
    }
    return {code: {"model": ErrorOut, "description": descriptions[code]} for code in codes}
