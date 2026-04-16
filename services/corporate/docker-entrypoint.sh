#!/bin/bash
set -e

echo "Waiting for PostgreSQL at $DATABASE_URL..."
# Simple check for Postgres availability could be added here

echo "Starting Corporate Environment Service on port 8009..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8009 --workers 4
