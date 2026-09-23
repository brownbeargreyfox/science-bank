from app.core.db import Base

# Phase 2 (standards schema) and later phases add model modules here, e.g.:
#   from app.models.standard import Standard  # noqa: F401
# Alembic autogenerate needs every model imported here so it's registered on Base.metadata.

__all__ = ["Base"]
