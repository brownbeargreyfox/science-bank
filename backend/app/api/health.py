from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict:
    """Liveness check — does not touch the database."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)) -> dict:
    """Readiness check — confirms the database connection works."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
