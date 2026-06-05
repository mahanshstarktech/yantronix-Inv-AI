#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$SCRIPT_DIR/local-dbs"

echo "Starting Redis v7..."
# Must cd into the redis dir so msys2 DLLs are found
(cd "$BASE_DIR/redis" && ./redis-server.exe &)

echo "Starting MongoDB..."
(cd "$BASE_DIR/mongodb/bin" && ./mongod.exe --dbpath "$(cygpath -w "$BASE_DIR/mongodb/data/db")" &)

sleep 2
echo "Verifying Redis..."
"$BASE_DIR/redis/redis-cli.exe" ping && echo "Redis: OK" || echo "Redis: FAILED"
echo "Databases started."

