"""BluntScore — FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, ingestion, sentiment
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.database import init_db
from app.nlp.analyzer import get_analyzer

settings = get_settings()
setup_logging(settings.debug)
logger = logging.getLogger("bluntscore")


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
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(sentiment.router, prefix=settings.api_prefix)
    app.include_router(ingestion.router, prefix=settings.api_prefix)

    @app.get("/", tags=["Root"], summary="API root")
    def root() -> dict:
        return {
            "message": f"Welcome to {settings.app_name}",
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
        }

    logger.info("%s v%s created (%s)", settings.app_name, settings.app_version, settings.environment)
    return app


app = create_app()
