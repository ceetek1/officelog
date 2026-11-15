"""Spec §12: the app's database role cannot UPDATE or DELETE activity_log (builder's choice B1
extends this to scans and decisions)."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import app_engine
from app.dbrole import TABLE_PRIVILEGES
from app.models import Base


def _app_exec(sql: str, **params):
    with app_engine().begin() as conn:
        return conn.execute(text(sql), params)


def test_every_table_has_privileges_listed():
    assert set(TABLE_PRIVILEGES) == set(Base.metadata.tables)


def test_app_role_can_insert_and_read_activity_log():
    _app_exec("INSERT INTO activity_log (action, entity) VALUES ('test', 'test')")
    with app_engine().connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM activity_log")).scalar_one() == 1


@pytest.mark.parametrize("sql", [
    "UPDATE activity_log SET action = 'changed'",
    "DELETE FROM activity_log",
    "TRUNCATE activity_log",
])
def test_app_role_cannot_change_activity_log(sql):
    _app_exec("INSERT INTO activity_log (action, entity) VALUES ('test', 'test')")
    with pytest.raises(DBAPIError) as exc:
        _app_exec(sql)
    assert "permission denied" in str(exc.value)


@pytest.mark.parametrize("table", ["scans", "decisions", "scan_attempts"])
def test_app_role_cannot_update_or_delete_append_only_tables(table):
    for sql in (f"UPDATE {table} SET id = id", f"DELETE FROM {table}"):
        with pytest.raises(DBAPIError) as exc:
            _app_exec(sql)
        assert "permission denied" in str(exc.value)


def test_even_the_owner_cannot_change_activity_log(owner):
    with owner.begin() as conn:
        conn.execute(text("INSERT INTO activity_log (action, entity) VALUES ('test', 'test')"))
    for sql in ("UPDATE activity_log SET action = 'x'", "DELETE FROM activity_log"):
        with pytest.raises(DBAPIError) as exc:
            with owner.begin() as conn:
                conn.execute(text(sql))
        assert "append-only" in str(exc.value)


def test_app_role_cannot_touch_migration_bookkeeping():
    with pytest.raises(DBAPIError):
        _app_exec("SELECT * FROM alembic_version")


def test_only_one_active_md_and_one_active_manager(make_user):
    make_user("Manager 1", "manager")
    make_user("Old manager", "manager", active=False)  # inactive ones don't count
    with pytest.raises(DBAPIError):
        make_user("Manager 2", "manager")
    make_user("MD 1", "md", "md1@company.test", "x" * 12)
    with pytest.raises(DBAPIError):
        make_user("MD 2", "md", "md2@company.test", "x" * 12)
