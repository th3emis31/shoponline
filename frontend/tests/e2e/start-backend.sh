#!/usr/bin/env bash
# Starts the FastAPI backend on a fresh throwaway SQLite database for E2E tests.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
E2E_DIR="$HERE/../../.e2e"
mkdir -p "$E2E_DIR"
rm -f "$E2E_DIR/e2e.db"
cd "$HERE/../../../backend"
export DATABASE_URL="sqlite:///$E2E_DIR/e2e.db"
# Payments off: E2E covers the storefront flow, Stripe is covered by backend tests.
export STRIPE_SECRET_KEY="" STRIPE_WEBHOOK_SECRET=""
PY="${PYTHON:-python3}"
"$PY" -m alembic upgrade head
"$PY" -m app.seed
exec "$PY" -m uvicorn app.main:app --port "${BACKEND_PORT:-8100}"
