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
NODE_MODULES_STAMP="$PROJECT_ROOT/node_modules/.package-lock.json"

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

requirements_satisfied() {
    local dry_run_output

    [ -f "$REQUIREMENTS_STAMP" ] || return 1
    [ ! "$REQUIREMENTS_FILE" -nt "$REQUIREMENTS_STAMP" ] || return 1
    "$VENV_PYTHON" -m pip check >/dev/null 2>&1 || return 1
    dry_run_output="$("$VENV_PYTHON" -m pip install --dry-run -r "$REQUIREMENTS_FILE" 2>/dev/null)" || return 1
    ! grep -q "Would install" <<<"$dry_run_output"
}

if requirements_satisfied; then
    echo "Backend requirements already satisfied; skipping pip install."
else
    echo "Installing backend requirements..."
    "$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"
    touch "$REQUIREMENTS_STAMP"
fi

frontend_dependencies_satisfied() {
    [ -d "$PROJECT_ROOT/node_modules" ] &&
        [ -f "$NODE_MODULES_STAMP" ] &&
        [ ! "$PROJECT_ROOT/package.json" -nt "$NODE_MODULES_STAMP" ] &&
        { [ ! -f "$PROJECT_ROOT/package-lock.json" ] || [ ! "$PROJECT_ROOT/package-lock.json" -nt "$NODE_MODULES_STAMP" ]; } &&
        npm ls --depth=0 >/dev/null 2>&1
}

if frontend_dependencies_satisfied; then
    echo "Frontend dependencies already satisfied; skipping npm install."
else
    echo "Installing frontend dependencies..."
    npm install
fi

PIDS=()
STARTED_DOCKER_DBS=false
DOCKER_STARTED_SERVICES=()
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

is_port_open() {
    local host="${1:-127.0.0.1}"
    local port="$2"

    (echo >"/dev/tcp/$host/$port") >/dev/null 2>&1
}

redis_is_running() {
    local port="${REDIS_PORT:-6379}"

    if command -v redis-cli >/dev/null 2>&1; then
        redis-cli -p "$port" ping >/dev/null 2>&1
    elif [ -x "$PROJECT_ROOT/local-dbs/redis/redis-cli.exe" ]; then
        "$PROJECT_ROOT/local-dbs/redis/redis-cli.exe" -p "$port" ping >/dev/null 2>&1
    else
        is_port_open 127.0.0.1 "$port"
    fi
}

mongo_is_running() {
    is_port_open 127.0.0.1 "${MONGO_PORT:-27017}"
}

cleanup() {
    echo "Stopping application components..."
    for pid in "${PIDS[@]:-}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done
    if [ "$STARTED_DOCKER_DBS" = "true" ]; then
        if [ "${#DOCKER_STARTED_SERVICES[@]}" -gt 0 ]; then
            docker_compose -f "$DOCKER_COMPOSE_FILE" stop "${DOCKER_STARTED_SERVICES[@]}" >/dev/null 2>&1 || true
        else
            docker_compose -f "$DOCKER_COMPOSE_FILE" down >/dev/null 2>&1 || true
        fi
    fi
    wait >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

start_redis() {
    if redis_is_running; then
        echo "Redis is already running; skipping Redis startup."
        return
    fi

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
    if mongo_is_running; then
        echo "MongoDB is already running; skipping MongoDB startup."
        return
    fi

    if command -v mongod >/dev/null 2>&1; then
        echo "Starting MongoDB from PATH..."
        mkdir -p "$PROJECT_ROOT/local-dbs/mongodb/data/db"
        mongod --dbpath "$PROJECT_ROOT/local-dbs/mongodb/data/db" --bind_ip 127.0.0.1 --port "${MONGO_PORT:-27017}" --quiet &
        PIDS+=("$!")
    elif [ -x "$PROJECT_ROOT/local-dbs/mongodb/bin/mongod.exe" ]; then
        echo "Starting bundled Windows MongoDB..."
        mkdir -p "$PROJECT_ROOT/local-dbs/mongodb/data/db"
        if command -v cygpath >/dev/null 2>&1; then
            DB_PATH="$(cygpath -w "$PROJECT_ROOT/local-dbs/mongodb/data/db")"
        else
            DB_PATH="$PROJECT_ROOT/local-dbs/mongodb/data/db"
        fi
        (cd "$PROJECT_ROOT/local-dbs/mongodb/bin" && ./mongod.exe --dbpath "$DB_PATH" --bind_ip 127.0.0.1 --port "${MONGO_PORT:-27017}") &
        PIDS+=("$!")
    else
        echo "MongoDB binary not found; run ./setup_dbs.sh or start MongoDB separately before generating products."
    fi
}

start_databases() {
    local redis_running=false
    local mongo_running=false

    if redis_is_running; then
        redis_running=true
        echo "Redis is already running; skipping Redis startup."
    fi

    if mongo_is_running; then
        mongo_running=true
        echo "MongoDB is already running; skipping MongoDB startup."
    fi

    if [ "$redis_running" = "true" ] && [ "$mongo_running" = "true" ]; then
        return
    fi

    if [ -f "$DOCKER_COMPOSE_FILE" ] && has_docker_compose; then
        local services=()
        [ "$redis_running" = "false" ] && services+=("redis")
        [ "$mongo_running" = "false" ] && services+=("mongodb")

        echo "Starting missing database services with Docker Compose: ${services[*]}..."
        docker_compose -f "$DOCKER_COMPOSE_FILE" up -d "${services[@]}"
        STARTED_DOCKER_DBS=true
        DOCKER_STARTED_SERVICES=("${services[@]}")
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
