"""Endpoints to try the NLP engine directly on raw text."""
from fastapi import APIRouter, Depends

from app.models.enums import SentimentLabel
from app.nlp.analyzer import SentimentAnalyzer, SentimentResult, get_analyzer
from app.schemas.sentiment import (
    AnalyzeRequest,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    BatchSummary,
    SentimentResultOut,
    SentimentScores,
)

router = APIRouter(prefix="/sentiment", tags=["Sentiment"])


def _to_out(text: str, result: SentimentResult) -> SentimentResultOut:
    return SentimentResultOut(
        text=text,
        label=result.label,
        compound=result.compound,
        confidence=result.confidence,
        scores=SentimentScores(
            positive=result.positive, neutral=result.neutral, negative=result.negative
        ),
    )


@router.post("/analyze", response_model=SentimentResultOut, summary="Classify one text")
def analyze_text(
    payload: AnalyzeRequest, analyzer: SentimentAnalyzer = Depends(get_analyzer)
) -> SentimentResultOut:
    return _to_out(payload.text, analyzer.analyze(payload.text))


@router.post("/analyze/batch", response_model=BatchAnalyzeResponse, summary="Classify many texts")
def analyze_batch(
    payload: BatchAnalyzeRequest, analyzer: SentimentAnalyzer = Depends(get_analyzer)
) -> BatchAnalyzeResponse:
    results = analyzer.analyze_batch(payload.texts)
    outs = [_to_out(text, r) for text, r in zip(payload.texts, results)]
    labels = [r.label for r in results]
    summary = BatchSummary(
        total=len(results),
        positive=labels.count(SentimentLabel.POSITIVE),
        neutral=labels.count(SentimentLabel.NEUTRAL),
        negative=labels.count(SentimentLabel.NEGATIVE),
        average_compound=round(sum(r.compound for r in results) / len(results), 4),
    )
    return BatchAnalyzeResponse(results=outs, summary=summary)
