from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SiteSettings


def get_site_settings(db: Session) -> SiteSettings:
    """Migration 0003 seeds row 1; recreate it from env defaults if someone removed it."""
    row = db.get(SiteSettings, 1)
    if row is None:
        row = SiteSettings(id=1, registration_open=get_settings().registration_open)
        db.add(row)
        db.flush()
    return row
