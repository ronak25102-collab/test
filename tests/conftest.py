import os
from pathlib import Path
from uuid import uuid4

import pytest
from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.settings import Settings
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture
def store(tmp_path: Path):
    engine = build_engine(os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}"))
    schema = None
    if engine.dialect.name == "postgresql":
        schema = "test_" + uuid4().hex
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(engine)
    store = Store(session_factory(engine), tmp_path)
    store.bootstrap()
    yield store
    if schema:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
    engine.dispose()


@pytest.fixture
def settings(tmp_path: Path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", data_dir=tmp_path, auto_start_worker=False)
