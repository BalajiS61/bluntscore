"""Source adapters: field aliases, dates, validation and row-numbered errors."""
from datetime import datetime, timezone

import pytest

from app.ingestion.adapters import parse_csv, parse_datetime, parse_json_records

GOOD_CSV = (
    "\ufeffReview,User,Date,ID\n"
    "Great phone,alice,2026-10-01,a1\n"
    ",bob,2026-10-02,a2\n"
    "Bad battery,carol,not-a-date,a3\n"
    "Great phone,dave,2026-10-03,a4\n"
)


def test_csv_with_alias_headers_and_bom():
    batch = parse_csv(GOOD_CSV)
    assert batch.received == 4
    assert [r.text for r in batch.records] == ["Great phone", "Great phone"]
    first = batch.records[0]
    assert first.author == "alice"
    assert first.external_id == "a1"
    assert first.published_at == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_csv_bad_rows_reported_with_spreadsheet_line_numbers():
    errors = parse_csv(GOOD_CSV).errors
    assert [e.row for e in errors] == [3, 4]
    assert "empty" in errors[0].message
    assert "date" in errors[1].message.lower()


def test_csv_without_text_column_rejected():
    with pytest.raises(ValueError):
        parse_csv("name,stars\nbob,5\n")


def test_json_records_accept_different_field_names():
    batch = parse_json_records(
        [
            {"body": "Nice", "username": "x", "timestamp": 1760000000},
            {"comment": "Okay-ish", "date": "2026-10-01T09:30:00Z"},
            {"content": "Fine", "review_id": 42},
        ]
    )
    assert [r.text for r in batch.records] == ["Nice", "Okay-ish", "Fine"]
    assert batch.records[0].author == "x"
    assert batch.records[1].published_at == datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
    assert batch.records[2].external_id == "42"
    assert batch.errors == []


def test_json_non_object_and_empty_text_rejected():
    batch = parse_json_records(["just a string", {"text": "   "}, {"text": "ok"}])
    assert [e.row for e in batch.errors] == [1, 2]
    assert len(batch.records) == 1


def test_overlong_text_rejected():
    batch = parse_json_records([{"text": "a" * 5001}])
    assert batch.records == []
    assert "5000" in batch.errors[0].message


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-10-01", datetime(2026, 10, 1, tzinfo=timezone.utc)),
        ("2026-10-01T05:30:00+05:30", datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)),
        ("2026-10-01T09:30:00Z", datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)),
        (0, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        ("", None),
        (None, None),
    ],
)
def test_parse_datetime(value, expected):
    assert parse_datetime(value) == expected
