#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR/local-dbs"
DOCKER_COMPOSE_FILE="$BASE_DIR/docker-compose.yml"

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

if [ -f "$DOCKER_COMPOSE_FILE" ] && has_docker_compose; then
    echo "Starting Redis and MongoDB with Docker Compose..."
    docker_compose -f "$DOCKER_COMPOSE_FILE" up -d
    echo "Databases started. Stop them with: docker compose -f $DOCKER_COMPOSE_FILE down"
    exit 0
fi

if command -v redis-server >/dev/null 2>&1; then
    echo "Starting Redis from PATH..."
    redis-server --port "${REDIS_PORT:-6379}" &
elif [ -x "$BASE_DIR/redis/redis-server.exe" ]; then
    echo "Starting bundled Windows Redis..."
    (cd "$BASE_DIR/redis" && ./redis-server.exe) &
else
    echo "Redis binary not found. Run ./setup_dbs.sh or install Redis on PATH." >&2
    exit 1
fi

if command -v mongod >/dev/null 2>&1; then
    echo "Starting MongoDB from PATH..."
    mkdir -p "$BASE_DIR/mongodb/data/db"
    mongod --dbpath "$BASE_DIR/mongodb/data/db" --bind_ip 127.0.0.1 --port "${MONGO_PORT:-27017}" --quiet &
elif [ -x "$BASE_DIR/mongodb/bin/mongod.exe" ]; then
    echo "Starting bundled Windows MongoDB..."
    if command -v cygpath >/dev/null 2>&1; then
        DB_PATH="$(cygpath -w "$BASE_DIR/mongodb/data/db")"
    else
        DB_PATH="$BASE_DIR/mongodb/data/db"
    fi
    (cd "$BASE_DIR/mongodb/bin" && ./mongod.exe --dbpath "$DB_PATH") &
else
    echo "MongoDB binary not found. Run ./setup_dbs.sh or install MongoDB on PATH." >&2
    exit 1
fi

sleep 2

if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -p "${REDIS_PORT:-6379}" ping && echo "Redis: OK" || echo "Redis: FAILED"
elif [ -x "$BASE_DIR/redis/redis-cli.exe" ]; then
    "$BASE_DIR/redis/redis-cli.exe" ping && echo "Redis: OK" || echo "Redis: FAILED"
fi

echo "Databases started in the background. Stop them manually when done."
