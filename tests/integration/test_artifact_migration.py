"""Exercise the old artifact schema on SQLite and the CI PostgreSQL database."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from signal_research.db.models import ArtifactModel
from signal_research.db.session import build_engine
from sqlalchemy import JSON, Column, MetaData, String, Table, inspect, select, text
from sqlalchemy.schema import CreateSchema, DropSchema


def test_artifact_kind_migration_preserves_failover_state(tmp_path):
    engine = build_engine(os.getenv('TEST_DATABASE_URL', f'sqlite:///{tmp_path / "migration.db"}'))
    schema = 'migration_' + uuid4().hex if engine.dialect.name == 'postgresql' else None
    path = Path(__file__).resolve().parents[2] / 'backend/migrations/versions/0004_artifact_kind_capacity.py'
    spec = importlib.util.spec_from_file_location('artifact_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    old = Table('artifacts', MetaData(), Column('id', String(36), primary_key=True),
                Column('kind', String(50), nullable=False, index=True), Column('payload', JSON))
    long_kind = 'exhausted:' + 'a' * 32 + ':codecraft:0'
    assert len(long_kind) > 50
    try:
        with engine.begin() as connection:
            if schema:
                connection.execute(CreateSchema(schema))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            old.create(connection)
            connection.execute(old.insert().values(id='existing', kind='result:cached', payload={'value': 42}))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()  # Fresh installs already have the wider model column.
                kind = next(c for c in inspect(connection).get_columns('artifacts') if c['name'] == 'kind')
                assert kind['type'].length == ArtifactModel.__table__.c.kind.type.length == 128
                assert any(i['column_names'] == ['kind'] for i in inspect(connection).get_indexes('artifacts'))
                connection.execute(old.insert().values(id='failover', kind=long_kind,
                                                       payload={'slot': 'codecraft:0', 'reason': 'HTTP 402'}))
                saved = connection.execute(select(old).where(old.c.kind == long_kind)).mappings().one()
                assert saved['payload']['reason'] == 'HTTP 402'
                with pytest.raises(RuntimeError, match='long durable identifiers'):
                    migration.downgrade()
                assert connection.scalar(select(old.c.kind).where(old.c.id == 'failover')) == long_kind
                connection.execute(old.delete().where(old.c.id == 'failover'))
                migration.downgrade()
                kind = next(c for c in inspect(connection).get_columns('artifacts') if c['name'] == 'kind')
                assert kind['type'].length == 50
                assert connection.scalar(select(old.c.payload).where(old.c.id == 'existing')) == {'value': 42}
    finally:
        if schema:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()
