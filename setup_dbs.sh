#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$SCRIPT_DIR/local-dbs"
DOCKER_COMPOSE_FILE="$BASE_DIR/docker-compose.yml"
REDIS_VERSION="7.4.3"
MONGO_VERSION="7.0.5"

mkdir -p "$BASE_DIR/mongodb/data/db"

echo "Setting up local databases in $BASE_DIR"

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

write_docker_compose_file() {
    cat > "$DOCKER_COMPOSE_FILE" <<'YAML'
services:
  redis:
    image: redis:7-alpine
    container_name: yantronix-redis
    ports:
      - "6379:6379"
    volumes:
      - ./redis/data:/data
    command: redis-server --appendonly yes

  mongodb:
    image: mongo:7
    container_name: yantronix-mongodb
    ports:
      - "27017:27017"
    volumes:
      - ./mongodb/data/db:/data/db
YAML
}

setup_docker_databases() {
    write_docker_compose_file
    echo "Docker Compose database configuration written to $DOCKER_COMPOSE_FILE"
    echo "Pulling Redis and MongoDB container images..."
    docker_compose -f "$DOCKER_COMPOSE_FILE" pull
    echo "Docker database setup complete. Start them with ./start_dbs.sh or ./run_app.sh."
}

setup_windows_binaries() {
    mkdir -p "$BASE_DIR/redis" "$BASE_DIR/mongodb/data/db" "$BASE_DIR/mongodb-temp"

    if [ ! -x "$BASE_DIR/redis/redis-server.exe" ]; then
        echo "Downloading Redis (v$REDIS_VERSION Windows build)..."
        curl -L "https://github.com/redis-windows/redis-windows/releases/download/$REDIS_VERSION/Redis-$REDIS_VERSION-Windows-x64-msys2.zip" -o "$BASE_DIR/redis.zip"
        echo "Extracting Redis..."
        rm -rf "$BASE_DIR/redis-temp"
        mkdir -p "$BASE_DIR/redis-temp"
        tar -xf "$BASE_DIR/redis.zip" -C "$BASE_DIR/redis-temp"
        mv "$BASE_DIR"/redis-temp/*/* "$BASE_DIR/redis/" 2>/dev/null || mv "$BASE_DIR"/redis-temp/* "$BASE_DIR/redis/"
        rm -rf "$BASE_DIR/redis-temp" "$BASE_DIR/redis.zip"
    else
        echo "Redis Windows binary already exists; skipping download."
    fi

    if [ ! -x "$BASE_DIR/mongodb/bin/mongod.exe" ]; then
        echo "Downloading MongoDB (v$MONGO_VERSION Windows build)..."
        curl -L "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$MONGO_VERSION.zip" -o "$BASE_DIR/mongodb.zip"
        echo "Extracting MongoDB..."
        rm -rf "$BASE_DIR/mongodb-temp"
        mkdir -p "$BASE_DIR/mongodb-temp"
        tar -xf "$BASE_DIR/mongodb.zip" -C "$BASE_DIR/mongodb-temp"
        mv "$BASE_DIR"/mongodb-temp/mongodb-windows-x86_64-*/* "$BASE_DIR/mongodb/"
        rm -rf "$BASE_DIR/mongodb-temp" "$BASE_DIR/mongodb.zip"
    else
        echo "MongoDB Windows binary already exists; skipping download."
    fi

    echo "Windows database binaries setup complete. Start them with ./start_dbs.sh or ./run_app.sh."
}

case "${OSTYPE:-}" in
    msys*|cygwin*|win32*)
        if [ "${FORCE_DOCKER_DBS:-false}" = "true" ]; then
            if has_docker_compose; then
                setup_docker_databases
            else
                echo "FORCE_DOCKER_DBS=true was set, but Docker Compose was not found." >&2
                exit 1
            fi
        else
            setup_windows_binaries
        fi
        ;;
    *)
        if command -v redis-server >/dev/null 2>&1 && command -v mongod >/dev/null 2>&1; then
            echo "Redis and MongoDB are already available on PATH."
            echo "Setup complete. Start them with ./start_dbs.sh or ./run_app.sh."
        elif has_docker_compose; then
            setup_docker_databases
        else
            cat >&2 <<MSG
Redis/MongoDB binaries were not found, and Docker Compose is not available.
Install Redis and MongoDB on PATH, or install Docker Desktop / Docker Compose,
then rerun ./setup_dbs.sh.
MSG
            exit 1
        fi
        ;;
esac
