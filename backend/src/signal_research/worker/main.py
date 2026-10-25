from __future__ import annotations

import logging
import uuid
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.settings import Settings, get_settings

from .machine import ResearchMachine

logger = logging.getLogger(__name__)


def run_worker(once: bool = False, *, settings: Settings | None = None,
               wakeup: Event | None = None, stop: Event | None = None,
               idle: Event | None = None) -> None:
    settings = settings or get_settings()
    stop = stop or Event()
    engine = build_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    factory = session_factory(engine)
    store = Store(factory, settings.data_dir)
    store.bootstrap()
    if settings.pipeline_mode == "precomputed":
        from signal_research.precomputed.catalog import bootstrap_catalog
        bootstrap_catalog(store, settings)
    machine = ResearchMachine(store, settings)
    owner = f"worker-{uuid.uuid4()}"
    try:
        while not stop.is_set():
            if wakeup is not None:
                # Clear before querying so a request committed after that query
                # cannot lose its notification while the worker starts waiting.
                wakeup.clear()
            if idle is not None:
                idle.clear()
            try:
                run_id = store.lease_next(owner, settings.max_active_runs)
                if run_id:
                    machine.process(run_id)
                elif once:
                    return
                elif wakeup is not None:
                    delay = store.worker_idle_delay(settings.worker_idle_poll_seconds)
                    if idle is not None:
                        idle.set()
                    wakeup.wait(timeout=delay)
                else:
                    stop.wait(1)
            except SQLAlchemyError:
                if once:
                    raise
                logger.exception("Worker database connection interrupted; retrying")
                stop.wait(5)
    finally:
        if idle is not None:
            idle.clear()
        engine.dispose()


if __name__ == "__main__":
    run_worker()
