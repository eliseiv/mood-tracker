#!/usr/bin/env bash
# Container entrypoint: wait for Postgres, apply migrations, seed catalog, serve.
set -euo pipefail

DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"

# --- Wait for PostgreSQL to accept TCP connections -------------------------
# depends_on: service_healthy already gates startup; this is belt-and-suspenders
# for restarts/race conditions. Uses bash /dev/tcp (no extra packages).
echo "[entrypoint] waiting for database ${DB_HOST}:${DB_PORT} ..."
for i in $(seq 1 60); do
  if (exec 3<>"/dev/tcp/${DB_HOST}/${DB_PORT}") 2>/dev/null; then
    exec 3>&- 3<&-
    echo "[entrypoint] database reachable"
    break
  fi
  if [ "${i}" -eq 60 ]; then
    echo "[entrypoint] ERROR: database not reachable after 60s" >&2
    exit 1
  fi
  sleep 1
done

# --- Apply migrations before serving (docs/07-deployment.md) ---------------
echo "[entrypoint] alembic upgrade head ..."
alembic upgrade head

# --- Seed baseline catalog (idempotent, docs/07-deployment.md) -------------
echo "[entrypoint] seeding baseline catalog (idempotent) ..."
python -m app.seed.catalog_seed

# --- Launch API (uvloop via uvicorn[standard]) -----------------------------
echo "[entrypoint] starting uvicorn on 0.0.0.0:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
