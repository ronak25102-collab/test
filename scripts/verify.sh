#!/usr/bin/env bash
set -euo pipefail
uv run ruff check backend/src tests
uv run pytest -q
(cd frontend && npm run build)
