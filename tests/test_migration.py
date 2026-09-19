"""Schema migration on a database that already has rows.

The failure this guards against is invisible to every other test in this suite: they
all build a fresh database, where create_all does the right thing. A model that gains
a field against a database created before it fails on the first query with
"no such column", and only ever in real use.
"""

from __future__ import annotations

import sqlite3

import pytest
from sqlmodel import select

from rfactory import service
from rfactory.config import settings
from rfactory.db import session as db_session
from rfactory.db.models import Application


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "rfactory.db")
    monkeypatch.setattr(settings, "out_dir", tmp_path / "out")
    monkeypatch.setattr(service, "_app", None)
    monkeypatch.setattr(db_session, "_engine", None)
    monkeypatch.setattr(db_session, "_engine_path", None)
    return tmp_path


def _columns() -> set[str]:
    with sqlite3.connect(str(settings.db_path)) as connection:
        return {row[1] for row in connection.execute("PRAGMA table_info(application)")}


def test_a_column_added_after_rows_exist_is_migrated_in(fresh):
    record = service.create_application(track="ai_eng", jd_text="SQL.", company="Acme")
    assert "llm_provider" in _columns()

    # Simulate the database as it was before the model gained those fields.
    with sqlite3.connect(str(settings.db_path)) as connection:
        connection.execute("ALTER TABLE application DROP COLUMN llm_provider")
        connection.execute("ALTER TABLE application DROP COLUMN llm_model")
        connection.commit()
    assert "llm_provider" not in _columns()

    db_session.migrate()

    assert {"llm_provider", "llm_model"} <= _columns()
    with db_session.get_session() as db:
        rows = list(db.exec(select(Application)))
    assert len(rows) == 1, "existing rows must survive the migration"
    assert rows[0].id == record.id
    assert rows[0].company == "Acme"
    assert rows[0].llm_provider == "", "backfilled with the model's default, not NULL"


def test_migrate_is_idempotent(fresh):
    service.create_application(track="ai_eng", jd_text="SQL.")
    assert db_session.migrate() == []
    assert db_session.migrate() == []


def test_init_db_migrates_an_existing_database(fresh):
    service.create_application(track="ai_eng", jd_text="SQL.")
    with sqlite3.connect(str(settings.db_path)) as connection:
        connection.execute("ALTER TABLE application DROP COLUMN spacing_risk")
        connection.commit()

    db_session.init_db()

    assert "spacing_risk" in _columns()
    with db_session.get_session() as db:
        assert list(db.exec(select(Application)))[0].spacing_risk is False
