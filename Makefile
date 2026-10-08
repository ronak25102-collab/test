.PHONY: doctor test test-integration test-e2e lint verify doctor-live

doctor:
	uv run python scripts/doctor.py

test:
	uv run pytest tests/unit tests/integration -q

test-integration:
	uv run pytest tests/integration -q

test-e2e:
	cd frontend && npm run test:e2e

lint:
	uv run ruff check backend/src tests

verify: lint test

doctor-live:
	uv run python scripts/doctor.py --live
