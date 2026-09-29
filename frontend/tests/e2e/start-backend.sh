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
export ADMIN_TOKEN="e2e-admin-token"
# Scheduled jobs off in tests; the tests trigger jobs with "Run now".
export AUTOMATION_ENABLED=false
# Many sign-ins from one address during the run; production ignores this.
export RATE_LIMIT_MULTIPLIER=10
PY="${PYTHON:-python3}"
"$PY" -m alembic upgrade head
"$PY" -m app.seed
ADMIN_PASSWORD="e2e owner password" "$PY" -m app.admin_users create owner@e2e.test --role owner
ADMIN_PASSWORD="e2e staff password" "$PY" -m app.admin_users create staff@e2e.test --role staff
exec "$PY" -m uvicorn app.main:app --port "${BACKEND_PORT:-8100}"
