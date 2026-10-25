import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from signal_research.db.session import build_engine
from sqlalchemy import Column, DateTime, MetaData, String, Table, inspect, text
from sqlalchemy.schema import CreateSchema, DropSchema


def test_ownership_migration_preserves_anonymous_runs_and_private_ownership(tmp_path):
    engine = build_engine(os.getenv("TEST_DATABASE_URL", f'sqlite:///{tmp_path / "owners.db"}'))
    schema = "owners_" + uuid4().hex if engine.dialect.name == "postgresql" else None
    path = Path(__file__).resolve().parents[2] / "backend/migrations/versions/0006_run_ownership.py"
    spec = importlib.util.spec_from_file_location("ownership_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    old = Table("research_runs", MetaData(), Column("id", String(36), primary_key=True),
                Column("created_at", DateTime))
    try:
        with engine.begin() as connection:
            if schema:
                connection.execute(CreateSchema(schema))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            old.create(connection)
            connection.execute(old.insert().values(id="anonymous"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
                assert connection.scalar(text("SELECT id FROM research_runs WHERE owner_user_id IS NULL")) == "anonymous"
                connection.execute(text("INSERT INTO research_runs (id,owner_user_id) VALUES ('owned','user_alice')"))
                with pytest.raises(RuntimeError, match="private investigations"):
                    migration.downgrade()
                assert connection.scalar(text("SELECT owner_user_id FROM research_runs WHERE id='owned'")) == "user_alice"
                connection.execute(text("DELETE FROM research_runs WHERE id='owned'"))
                migration.downgrade()
                assert "owner_user_id" not in {c["name"] for c in inspect(connection).get_columns("research_runs")}
                assert connection.scalar(text("SELECT id FROM research_runs")) == "anonymous"
    finally:
        if schema:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()
