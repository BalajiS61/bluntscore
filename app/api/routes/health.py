"""Health-check endpoint: confirms the API and the database are reachable."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Service and database health check")
def health_check(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except SQLAlchemyError:
        database_status = "unavailable"

    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
