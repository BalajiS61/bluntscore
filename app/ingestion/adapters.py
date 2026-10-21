"""Source adapters: turn raw JSON records or CSV files into clean, validated reviews.

Different sources name their fields differently ("review", "body", "comment"...),
so each field accepts several common aliases. Bad rows are collected as errors
with their row number instead of failing the whole upload.
"""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional

MAX_TEXT_LENGTH = 5000
MAX_AUTHOR_LENGTH = 120
MAX_EXTERNAL_ID_LENGTH = 120

TEXT_KEYS = ("text", "review", "review_text", "body", "content", "comment")
AUTHOR_KEYS = ("author", "user", "username", "reviewer", "name")
ID_KEYS = ("external_id", "id", "review_id")
DATE_KEYS = ("published_at", "date", "created_at", "timestamp", "time")

_NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")


@dataclass(frozen=True)
class RawReview:
    text: str
    author: Optional[str] = None
    external_id: Optional[str] = None
    published_at: Optional[datetime] = None


@dataclass(frozen=True)
class RowError:
    row: int
    message: str


@dataclass
class ParsedBatch:
    records: List[RawReview] = field(default_factory=list)
    errors: List[RowError] = field(default_factory=list)

    @property
    def received(self) -> int:
        return len(self.records) + len(self.errors)


def parse_datetime(value: Any) -> Optional[datetime]:
    """Accepts ISO strings ('2026-10-01', '2026-10-01T09:30:00Z'), unix timestamps or datetimes.
    Always returns a UTC datetime (naive values are assumed to be UTC)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            return None
        if _NUMBER_RE.match(text):
            dt = datetime.fromtimestamp(float(text), tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_keys(row: Mapping[str, Any]) -> dict:
    return {str(k).strip().lstrip("\ufeff").lower(): v for k, v in row.items() if k is not None}


def _first(row: dict, keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def parse_record(row: Mapping[str, Any]) -> RawReview:
    """Validate one record. Raises ValueError with a readable message if it is unusable."""
    data = _normalize_keys(row)

    text = _first(data, TEXT_KEYS)
    text = str(text).strip() if text is not None else ""
    if not text:
        raise ValueError("Review text is missing or empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Review text is longer than {MAX_TEXT_LENGTH} characters")

    author = _first(data, AUTHOR_KEYS)
    author = str(author).strip() if author is not None else None
    if author and len(author) > MAX_AUTHOR_LENGTH:
        raise ValueError(f"Author is longer than {MAX_AUTHOR_LENGTH} characters")

    external_id = _first(data, ID_KEYS)
    external_id = str(external_id).strip() if external_id is not None else None
    if external_id and len(external_id) > MAX_EXTERNAL_ID_LENGTH:
        raise ValueError(f"External id is longer than {MAX_EXTERNAL_ID_LENGTH} characters")

    raw_date = _first(data, DATE_KEYS)
    try:
        published_at = parse_datetime(raw_date)
    except (ValueError, OverflowError, OSError):
        raise ValueError(f"Unrecognised date: {raw_date!r} (use ISO format like 2026-10-01)")

    return RawReview(text=text, author=author or None, external_id=external_id or None,
                     published_at=published_at)


def parse_records(rows: Iterable[Mapping[str, Any]], first_row_number: int = 1) -> ParsedBatch:
    batch = ParsedBatch()
    for row_number, row in enumerate(rows, start=first_row_number):
        if not isinstance(row, Mapping):
            batch.errors.append(RowError(row_number, "Each record must be an object"))
            continue
        try:
            batch.records.append(parse_record(row))
        except ValueError as exc:
            batch.errors.append(RowError(row_number, str(exc)))
    return batch


def parse_json_records(records: List[Mapping[str, Any]]) -> ParsedBatch:
    """Records from a JSON array. Row numbers start at 1."""
    return parse_records(records, first_row_number=1)


def parse_csv(content: str) -> ParsedBatch:
    """CSV text with a header row. Row numbers match spreadsheet lines (header = line 1)."""
    content = content.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(content))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if not any(h in TEXT_KEYS for h in headers):
        raise ValueError(
            "CSV needs a header row with a review text column named one of: " + ", ".join(TEXT_KEYS)
        )
    return parse_records(reader, first_row_number=2)
