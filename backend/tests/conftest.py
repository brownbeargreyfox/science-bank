"""API/DB tests need Postgres. Point TEST_DATABASE_URL at a server where the user may create databases,
e.g. postgresql+psycopg://sb:sb@127.0.0.1:5432/sb_test — the database is dropped and recreated per run.
Engine-only tests (test_engine.py) run without it."""

import os
from pathlib import Path

import pytest

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DB_URL:
    os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 32)

BACKEND = Path(__file__).resolve().parents[1]
TEACHER = {"username": "nina", "password": "correct horse battery"}


def pytest_collection_modifyitems(config, items):
    if TEST_DB_URL:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if {"db", "client", "anon", "database"} & set(item.fixturenames):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def database():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(TEST_DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")

    from app.core.config import get_settings
    from app.core.db import SessionLocal
    from app.core.security import hash_password
    from app.models import User
    from app.services.families.registry import sync_families
    from app.standards.importer import import_standards

    with SessionLocal() as s:
        import_standards(s, get_settings().standards_dir)
        sync_families(s)
        s.add(User(username=TEACHER["username"], password_hash=hash_password(TEACHER["password"]), role="admin"))
        s.commit()
    yield


@pytest.fixture
def db(database):
    from app.core.db import SessionLocal

    with SessionLocal() as s:
        yield s


@pytest.fixture
def anon(database):
    from fastapi.testclient import TestClient

    from app.core.security import login_throttle
    from app.main import app

    login_throttle._failures.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anon):
    r = anon.post("/api/auth/login", json=TEACHER)
    assert r.status_code == 200, r.text
    return anon
