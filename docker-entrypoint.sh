#!/bin/bash
set -e

echo "══════════════════════════════════════════════════"
echo "  Autonomous Data Analyst Agent — Starting Up"
echo "══════════════════════════════════════════════════"

# ── Wait for PostgreSQL ────────────────────────────────────────
echo "⏳ Waiting for PostgreSQL..."
DB_HOST="${DATABASE_URL##*@}"
DB_HOST="${DB_HOST%%:*}"
DB_HOST="${DB_HOST%%/*}"

# Extract host and port from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/dbname
# Robust extraction even if port is missing or URL has params
PGHOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/?#]+).*|\1|')
PGPORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+).*|\1|' | grep -E '^[0-9]+$' || echo "5432")

MAX_RETRIES=30
RETRY_COUNT=0
until pg_isready -h "$PGHOST" -p "$PGPORT" -q 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "❌ PostgreSQL not available after $MAX_RETRIES retries. Exiting."
        exit 1
    fi
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES — waiting 2s..."
    sleep 2
done
echo "✅ PostgreSQL is ready!"

# ── Run Alembic Migrations ────────────────────────────────────
echo "🔄 Running database migrations..."
alembic upgrade head
echo "✅ Migrations complete!"

# ── Start the Application ─────────────────────────────────────
echo "🚀 Starting application..."
echo "══════════════════════════════════════════════════"
exec "$@"
