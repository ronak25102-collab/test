# Engineering decisions

* The implementation uses FastAPI, Pydantic 2, SQLAlchemy 2, Alembic and a
  separate worker process as specified.
* SQLite is supported as a local development fallback so the deterministic
  suite can run without Docker. Compose uses PostgreSQL 16 and exercises the
  same repository interfaces.
* Replay evidence is synthetic and permanently labelled. It is available for
  tests and rehearsals only; live mode cannot activate it implicitly.
* Provider SDKs are kept behind small adapters. The OpenAI adapter uses the
  Responses API when the optional SDK is installed; the application reports a
  typed configuration error otherwise.
* The frontend is intentionally dependency-light and uses native SVG charts;
  this avoids adding a chart dependency while retaining keyboard-accessible
  table alternatives.

* The sandbox interpreter changed during the session. Verification ran under
  uv-managed Python 3.14.8; the Docker compatibility baseline stays Python
  3.12. Dependency locks are in `uv.lock` and `frontend/package-lock.json`.
* The final live attempt failed visibly because `TAVILY_API_KEY` was absent.
  No fixtures were substituted into live mode.
