"""BluntScore — FastAPI application entry point."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, ingestion, ratings, scores, sentiment, sources, topics
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.db.database import init_db
from app.nlp.analyzer import get_analyzer

settings = get_settings()
setup_logging(settings.debug)
logger = logging.getLogger("bluntscore")

TAGS = [
    {"name": "Topics", "description": "Search topics and read their scores, summaries and reviews."},
    {"name": "Ratings", "description": "Submit and aggregate 1-5 star user ratings."},
    {"name": "Ingestion", "description": "Bring in reviews from JSON, CSV uploads or the sample dataset."},
    {"name": "Sources", "description": "Review sources and their reliability weights."},
    {"name": "Scores", "description": "Bulk score refresh."},
    {"name": "Sentiment", "description": "Run the NLP classifier on raw text."},
    {"name": "Health", "description": "Service status."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("Database ready at %s", settings.database_url)
    get_analyzer()  # load the NLP lexicon once at startup, not on the first request
    logger.info("Sentiment analyzer loaded")
    yield
    logger.info("%s shutting down", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Multi-source sentiment analysis & rating engine. "
            "Classifies reviews as positive/neutral/negative and produces "
            "a normalized 0-100 sentiment score per topic."
        ),
        openapi_tags=TAGS,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Tag every request with an id and timing so logs and responses can be matched up."""
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        logger.info("%s %s -> %s (%.1f ms) [%s]", request.method, request.url.path,
                    response.status_code, elapsed_ms, request_id)
        return response

    register_exception_handlers(app)

    for module in (health, topics, ratings, ingestion, sources, scores, sentiment):
        app.include_router(module.router, prefix=settings.api_prefix)

    @app.get("/", tags=["Health"], summary="API root")
    def root() -> dict:
        return {
            "message": f"Welcome to {settings.app_name}",
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    logger.info("%s v%s created (%s)", settings.app_name, settings.app_version, settings.environment)
    return app


app = create_app()
