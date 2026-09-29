"""Upgrades a pre-0003 database and checks roles, backfill, and case-insensitive usernames."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from tests.conftest import BACKEND, TEST_DB_URL


def _alembic(url: str, target: str, monkeypatch) -> None:
    from alembic import command
    from alembic.config import Config
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        command.upgrade(cfg, target)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


@pytest.fixture
def scratch_url(database):
    base = make_url(TEST_DB_URL)
    url = base.set(database=base.database + "_mig")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    yield url.render_as_string(hide_password=False)
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    admin.dispose()


def test_upgrade_backfills_roles_and_owners(scratch_url, monkeypatch):
    _alembic(scratch_url, "0002_eocep_constraints", monkeypatch)
    eng = create_engine(scratch_url)
    with eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('brandon','x'), ('Nina','y')"))
        c.execute(text("insert into assessments (title, instructions) values ('Old quiz', '')"))
    _alembic(scratch_url, "head", monkeypatch)
    with eng.begin() as c:
        roles = dict(c.execute(text("select username, role from users")).all())
        assert roles == {"brandon": "admin", "Nina": "power"}
        brandon_id = c.scalar(text("select id from users where username='brandon'"))
        assert c.scalar(text("select owner_id from assessments")) == brandon_id
        assert c.scalar(text("select registration_open from site_settings where id=1")) is True
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('NINA','z')"))
    eng.dispose()


def test_upgrade_promotes_first_user_when_no_brandon(scratch_url, monkeypatch):
    _alembic(scratch_url, "0002_eocep_constraints", monkeypatch)
    eng = create_engine(scratch_url)
    with eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('solo','x')"))
    _alembic(scratch_url, "head", monkeypatch)
    with eng.begin() as c:
        assert c.scalar(text("select role from users where username='solo'")) == "admin"
    eng.dispose()


def test_upgrade_refuses_case_duplicate_usernames(scratch_url, monkeypatch):
    _alembic(scratch_url, "0002_eocep_constraints", monkeypatch)
    eng = create_engine(scratch_url)
    with eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('nina','x'), ('Nina','y')"))
    with pytest.raises(Exception, match="duplicate usernames"):
        _alembic(scratch_url, "head", monkeypatch)
    eng.dispose()
