from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from rfactory.config import settings
from rfactory.db import models  # noqa: F401  -- registers tables on SQLModel.metadata

logger = logging.getLogger(__name__)

_engine = None
_engine_path = None


def engine():  # type: ignore[no-untyped-def]
    """Cached against the path it was built for. Keyed to nothing, a changed db_path
    was silently ignored and every caller kept writing to the first database opened."""
    global _engine, _engine_path
    if _engine is None or _engine_path != settings.db_path:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{settings.db_path}", echo=False)
        _engine_path = settings.db_path
    return _engine


def _scalar_defaults() -> dict[str, dict[str, Any]]:
    """Per table, the simple defaults declared on the model, used to backfill rows that
    existed before a column did."""
    defaults: dict[str, dict[str, Any]] = {}
    for cls in SQLModel.__subclasses__():
        table = getattr(cls, "__tablename__", None)
        fields = getattr(cls, "model_fields", None)
        if not table or not fields:
            continue
        values: dict[str, Any] = {}
        for name, field in fields.items():
            default = field.default
            if isinstance(default, Enum):
                default = default.value
            if isinstance(default, (str, int, float, bool)):
                values[name] = default
        defaults[str(table)] = values
    return defaults


def migrate() -> list[str]:
    """Add columns that the models declare but the database does not have.

    SQLModel's create_all only creates missing TABLES. A model that gains a field
    leaves an existing table untouched, and from then on every query against it fails
    with "no such column" -- invisible in tests, because tests build a fresh database
    every time.

    Additive only, on purpose: columns are added and backfilled with the model's
    default. Nothing is renamed, retyped or dropped, so this can never lose data. A
    change that needs more than an added column needs a real migration tool, and this
    returning an empty list is not evidence that the schema matches.
    """
    eng = engine()
    defaults = _scalar_defaults()
    applied: list[str] = []

    with eng.begin() as connection:
        # Read the live schema through PRAGMA rather than SQLAlchemy's Inspector: the
        # Inspector caches its reflection, so after the first ALTER it reports the old
        # column list and the next add fails with "duplicate column name".
        existing = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in existing:
                continue  # create_all will make it
            present = {
                row[1] for row in connection.execute(text(f"PRAGMA table_info({table.name})"))
            }
            for column in table.columns:
                if column.name in present:
                    continue
                ddl_type = column.type.compile(eng.dialect)
                connection.execute(
                    text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {ddl_type}')
                )
                default = defaults.get(table.name, {}).get(column.name)
                if default is not None:
                    connection.execute(
                        text(
                            f'UPDATE {table.name} SET "{column.name}" = :value '
                            f'WHERE "{column.name}" IS NULL'
                        ),
                        {"value": int(default) if isinstance(default, bool) else default},
                    )
                applied.append(f"{table.name}.{column.name}")
                logger.info("added column %s.%s", table.name, column.name)

    if applied:
        logger.info("schema migrated: %s", ", ".join(applied))
    return applied


def init_db() -> None:
    SQLModel.metadata.create_all(engine())
    migrate()


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine()) as session:
        yield session
