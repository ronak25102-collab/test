from pathlib import Path

import pytest
from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.settings import Settings


@pytest.fixture
def store(tmp_path: Path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    store = Store(session_factory(engine), tmp_path)
    store.bootstrap()
    return store


@pytest.fixture
def settings(tmp_path: Path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", data_dir=tmp_path, auto_start_worker=False)
