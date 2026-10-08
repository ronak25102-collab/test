from __future__ import annotations

import time
import uuid

from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.settings import get_settings

from .machine import ResearchMachine


def run_worker(once: bool = False) -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = session_factory(engine)
    store = Store(factory, settings.data_dir)
    store.bootstrap()
    machine = ResearchMachine(store, settings)
    owner = f"worker-{uuid.uuid4()}"
    while True:
        run_id = store.lease_next(owner)
        if run_id:
            machine.process(run_id)
        elif once:
            return
        else:
            time.sleep(1)


if __name__ == "__main__":
    run_worker()
