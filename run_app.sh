#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "Starting Yantronix application components..."

if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        PYTHON_BIN="python"
    fi
fi

VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/.venv}"
if [[ "$VENV_PATH" != /* ]]; then
    VENV_PATH="$PROJECT_ROOT/$VENV_PATH"
fi
REQUIREMENTS_FILE="$PROJECT_ROOT/backend/requirements.txt"
REQUIREMENTS_STAMP="$VENV_PATH/.requirements.installed"

if [ ! -d "$VENV_PATH" ]; then
    echo "Creating Python virtual environment at $VENV_PATH..."
    "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

if [ -f "$VENV_PATH/bin/activate" ]; then
    # Linux/macOS virtualenv layout
    # shellcheck disable=SC1091
    source "$VENV_PATH/bin/activate"
elif [ -f "$VENV_PATH/Scripts/activate" ]; then
    # Windows Git Bash virtualenv layout
    # shellcheck disable=SC1091
    source "$VENV_PATH/Scripts/activate"
else
    echo "Unable to find a virtualenv activation script in $VENV_PATH" >&2
    exit 1
fi

if [ -x "$VENV_PATH/bin/python" ]; then
    VENV_PYTHON="$VENV_PATH/bin/python"
elif [ -x "$VENV_PATH/Scripts/python.exe" ]; then
    VENV_PYTHON="$VENV_PATH/Scripts/python.exe"
else
    VENV_PYTHON="python"
fi

if [ ! -f "$REQUIREMENTS_STAMP" ] || [ "$REQUIREMENTS_FILE" -nt "$REQUIREMENTS_STAMP" ]; then
    echo "Installing backend requirements..."
    "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
    touch "$REQUIREMENTS_STAMP"
fi

if [ ! -d "$PROJECT_ROOT/node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

PIDS=()
STARTED_DOCKER_DBS=false
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/local-dbs/docker-compose.yml"

has_docker_compose() {
    { command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; } || command -v docker-compose >/dev/null 2>&1
}

docker_compose() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

cleanup() {
    echo "Stopping application components..."
    for pid in "${PIDS[@]:-}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done
    if [ "$STARTED_DOCKER_DBS" = "true" ]; then
        docker_compose -f "$DOCKER_COMPOSE_FILE" down >/dev/null 2>&1 || true
    fi
    wait >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

start_redis() {
    if command -v redis-server >/dev/null 2>&1; then
        echo "Starting Redis from PATH..."
        redis-server --port "${REDIS_PORT:-6379}" &
        PIDS+=("$!")
    elif [ -x "$PROJECT_ROOT/local-dbs/redis/redis-server.exe" ]; then
        echo "Starting bundled Windows Redis..."
        (cd "$PROJECT_ROOT/local-dbs/redis" && ./redis-server.exe) &
        PIDS+=("$!")
    else
        echo "Redis binary not found; run ./setup_dbs.sh or start Redis separately before queueing AI jobs."
    fi
}

start_mongo() {
    if command -v mongod >/dev/null 2>&1; then
        echo "Starting MongoDB from PATH..."
        mkdir -p "$PROJECT_ROOT/local-dbs/mongodb/data/db"
        mongod --dbpath "$PROJECT_ROOT/local-dbs/mongodb/data/db" --bind_ip 127.0.0.1 --port "${MONGO_PORT:-27017}" --quiet &
        PIDS+=("$!")
    elif [ -x "$PROJECT_ROOT/local-dbs/mongodb/bin/mongod.exe" ]; then
        echo "Starting bundled Windows MongoDB..."
        (cd "$PROJECT_ROOT/local-dbs/mongodb/bin" && ./mongod.exe --dbpath "$PROJECT_ROOT/local-dbs/mongodb/data/db") &
        PIDS+=("$!")
    else
        echo "MongoDB binary not found; run ./setup_dbs.sh or start MongoDB separately before generating products."
    fi
}

start_databases() {
    if [ -f "$DOCKER_COMPOSE_FILE" ] && has_docker_compose; then
        echo "Starting Redis and MongoDB with Docker Compose..."
        docker_compose -f "$DOCKER_COMPOSE_FILE" up -d
        STARTED_DOCKER_DBS=true
    else
        start_redis
        start_mongo
    fi
}

start_databases

sleep 2

echo "Starting Next.js frontend on http://localhost:3000..."
npm run dev &
PIDS+=("$!")

echo "Starting FastAPI backend on http://localhost:8000..."
(cd "$PROJECT_ROOT/backend" && "$VENV_PYTHON" -m uvicorn main:app --reload) &
PIDS+=("$!")

echo "Starting Celery worker..."
(cd "$PROJECT_ROOT/backend" && "$VENV_PYTHON" -m celery -A tasks worker --loglevel=info --pool=solo) &
PIDS+=("$!")

echo "All available components are running. Press Ctrl+C to stop them."
wait
