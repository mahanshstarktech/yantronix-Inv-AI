#!/bin/bash
set -e

echo "Starting Celery worker in the background..."
# We use --concurrency=1 to stay within Render's 512MB RAM free tier limit
python -m celery -A app.workers.celery_app worker --loglevel=info --concurrency=1 &

echo "Starting FastAPI server in the foreground..."
# Render provides the PORT environment variable automatically
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
