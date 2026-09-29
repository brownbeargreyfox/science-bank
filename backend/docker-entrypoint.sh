#!/bin/sh
# Start-up order: schema migrations -> standards import + family sync (idempotent) -> app server.
set -eu

echo "science-bank: applying database migrations"
alembic upgrade head

echo "science-bank: importing standards and syncing question families"
python -m app.cli bootstrap

exec "$@"
