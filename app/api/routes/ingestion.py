"""Endpoints that bring reviews into BluntScore from different kinds of sources."""
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.ingestion.adapters import ParsedBatch, RawReview, parse_csv, parse_datetime
from app.models.enums import SourceType
from app.schemas.ingestion import (
    IngestionReportOut,
    IngestRequest,
    RowErrorOut,
    SampleTopicOut,
)
from app.services.ingestion_service import IngestionReport, ingest_batch, load_sample_dataset

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_CSV_ROWS = 5000


def _report_out(report: IngestionReport) -> IngestionReportOut:
    b = report.breakdown
    return IngestionReportOut(
        topic_id=report.topic.id,
        topic_slug=report.topic.slug,
        topic_name=report.topic.name,
        source=report.source.name,
        received=report.received,
        inserted=report.inserted,
        duplicates=report.duplicates,
        rejected=report.rejected,
        errors=[RowErrorOut(row=e.row, message=e.message) for e in report.errors],
        sentiment_score=b.score if b else None,
        verdict=b.verdict if b else None,
    )


@router.post("/reviews", response_model=IngestionReportOut, summary="Ingest reviews as JSON")
def ingest_json(payload: IngestRequest, db: Session = Depends(get_db)) -> IngestionReportOut:
    batch = ParsedBatch(
        records=[
            RawReview(
                text=r.text,
                author=r.author or None,
                external_id=r.external_id or None,
                published_at=parse_datetime(r.published_at),
            )
            for r in payload.reviews
        ]
    )
    report = ingest_batch(
        db, payload.topic, payload.source, batch,
        source_type=payload.source_type, category=payload.category,
    )
    return _report_out(report)


@router.post("/csv", response_model=IngestionReportOut, summary="Ingest reviews from a CSV upload")
def ingest_csv(
    file: UploadFile = File(..., description="CSV with a header row and a 'text'/'review' column"),
    topic: str = Form(..., min_length=1, max_length=120),
    source: str = Form(..., min_length=1, max_length=80),
    source_type: SourceType = Form(SourceType.OTHER),
    db: Session = Depends(get_db),
) -> IngestionReportOut:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .csv files are accepted")

    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "CSV file must be 2 MB or smaller")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV must be UTF-8 encoded")

    try:
        batch = parse_csv(content)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if batch.received == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV has no data rows")
    if batch.received > MAX_CSV_ROWS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"CSV may contain at most {MAX_CSV_ROWS} rows")

    try:
        report = ingest_batch(db, topic, source, batch, source_type=source_type)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return _report_out(report)


@router.post("/samples", response_model=List[SampleTopicOut], summary="Load the bundled demo dataset")
def ingest_samples(db: Session = Depends(get_db)) -> List[SampleTopicOut]:
    return [
        SampleTopicOut(
            topic_id=r.topic.id,
            topic_slug=r.topic.slug,
            topic_name=r.topic.name,
            inserted_reviews=r.inserted_reviews,
            inserted_ratings=r.inserted_ratings,
            sentiment_score=r.breakdown.score,
            verdict=r.breakdown.verdict,
        )
        for r in load_sample_dataset(db)
    ]
