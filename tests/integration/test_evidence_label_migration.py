"""Check existing database upgrades without truncating source-bound labels."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from signal_research.db.session import build_engine
from sqlalchemy import Column, MetaData, String, Table, Text, inspect, select, text
from sqlalchemy.schema import CreateSchema, DropSchema


def test_evidence_label_migration_preserves_full_values(tmp_path):
    engine = build_engine(os.getenv("TEST_DATABASE_URL", f'sqlite:///{tmp_path / "labels.db"}'))
    schema = "labels_" + uuid4().hex if engine.dialect.name == "postgresql" else None
    path = Path(__file__).resolve().parents[2] / "backend/migrations/versions/0005_evidence_label_capacity.py"
    spec = importlib.util.spec_from_file_location("label_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = MetaData()
    tables = {name: Table(name, metadata, Column("id", String(36), primary_key=True),
                         *(Column(column, String(length)) for column, length in columns.items()))
              for name, columns in migration.COLUMNS.items()}
    try:
        with engine.begin() as connection:
            if schema:
                connection.execute(CreateSchema(schema))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            metadata.create_all(connection)
            for table in tables.values():
                connection.execute(table.insert().values(id="existing"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()  # Fresh installs already have Text columns.
                for name, table in tables.items():
                    columns = {column["name"]: column for column in inspect(connection).get_columns(name)}
                    values = {column: f"{column}:" + "source evidence " * 1500
                              for column in migration.COLUMNS[name]}
                    if engine.dialect.name != "sqlite":
                        assert all(isinstance(columns[column]["type"], Text) for column in values)
                    connection.execute(table.insert().values(id="long", **values))
                    saved = connection.execute(select(table).where(table.c.id == "long")).mappings().one()
                    assert all(saved[column] == value for column, value in values.items())
                with pytest.raises(RuntimeError, match="long source values"):
                    migration.downgrade()
                for table in tables.values():
                    connection.execute(table.delete().where(table.c.id == "long"))
                migration.downgrade()
                for name, table in tables.items():
                    assert connection.scalar(select(table.c.id)) == "existing"
                    columns = {column["name"]: column for column in inspect(connection).get_columns(name)}
                    for column, length in migration.COLUMNS[name].items():
                        assert columns[column]["type"].length == length
    finally:
        if schema:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()
