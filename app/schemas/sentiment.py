"""Request/response models for the sentiment endpoints (with validation)."""
from typing import Annotated, List

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import SentimentLabel

MAX_TEXT_LENGTH = 5000
MAX_BATCH_SIZE = 100

ReviewText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_LENGTH)
]


class AnalyzeRequest(BaseModel):
    text: ReviewText = Field(examples=["The camera is amazing but the battery is laggy and overpriced."])


class BatchAnalyzeRequest(BaseModel):
    texts: List[ReviewText] = Field(
        min_length=1,
        max_length=MAX_BATCH_SIZE,
        examples=[["I love this phone!", "Worst purchase ever.", "It comes in black."]],
    )


class SentimentScores(BaseModel):
    positive: float
    neutral: float
    negative: float


class SentimentResultOut(BaseModel):
    text: str
    label: SentimentLabel
    compound: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    scores: SentimentScores


class BatchSummary(BaseModel):
    total: int
    positive: int
    neutral: int
    negative: int
    average_compound: float


class BatchAnalyzeResponse(BaseModel):
    results: List[SentimentResultOut]
    summary: BatchSummary
