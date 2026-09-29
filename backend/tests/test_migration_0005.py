"""0005 adds the results tables and questions.variant_of_id, and downgrades cleanly."""

from sqlalchemy import create_engine, inspect

from tests.conftest import BACKEND
from tests.test_migration_0003 import scratch_url  # noqa: F401  (pytest fixture)

NEW_TABLES = {"administrations", "administration_items", "administration_sections", "item_results"}


def _alembic(url: str, target: str, monkeypatch, *, down: bool = False) -> None:
    from alembic import command
    from alembic.config import Config
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        (command.downgrade if down else command.upgrade)(cfg, target)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_upgrade_adds_tables_and_column_and_downgrade_removes_them(scratch_url, monkeypatch):  # noqa: F811  (fixture imported above)
    _alembic(scratch_url, "0004_bundle_generation_runs", monkeypatch)
    eng = create_engine(scratch_url)
    assert not NEW_TABLES & set(inspect(eng).get_table_names())
    assert "variant_of_id" not in {c["name"] for c in inspect(eng).get_columns("questions")}

    _alembic(scratch_url, "head", monkeypatch)
    insp = inspect(eng)
    assert NEW_TABLES <= set(insp.get_table_names())
    assert "variant_of_id" in {c["name"] for c in insp.get_columns("questions")}
    indexed = {tuple(i["column_names"]) for i in insp.get_indexes("administrations")}
    assert ("owner_id", "administered_on") in indexed
    assert ("variant_of_id",) in {tuple(i["column_names"]) for i in insp.get_indexes("questions")}
    result_checks = {c["name"] for c in insp.get_check_constraints("item_results")}
    assert {"ck_item_results_attempted_positive", "ck_item_results_correct_range"} <= result_checks

    _alembic(scratch_url, "0004_bundle_generation_runs", monkeypatch, down=True)
    insp = inspect(eng)
    assert not NEW_TABLES & set(insp.get_table_names())
    assert "variant_of_id" not in {c["name"] for c in insp.get_columns("questions")}

    _alembic(scratch_url, "head", monkeypatch)  # upgrade again after a downgrade
    assert NEW_TABLES <= set(inspect(eng).get_table_names())
    eng.dispose()
