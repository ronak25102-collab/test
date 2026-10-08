#!/usr/bin/env bash
set -euo pipefail
: "${COMPANY:?Set COMPANY to a listed financial-company symbol}"
uv run signal-research research --company "$COMPANY" --mode live
