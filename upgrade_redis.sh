#!/bin/bash
BASE_DIR="$(dirname "$0")/local-dbs"

taskkill.exe -F -IM redis-server.exe 2>/dev/null || true
echo "Stopped old Redis"

rm -rf "$BASE_DIR/redis"
mkdir -p "$BASE_DIR/redis" "$BASE_DIR/redis-temp"

echo "Downloading Redis v7.4.3..."
curl -L "https://github.com/redis-windows/redis-windows/releases/download/7.4.3/Redis-7.4.3-Windows-x64-msys2.zip" -o "$BASE_DIR/redis.zip"
echo "Extracting..."
unzip -q "$BASE_DIR/redis.zip" -d "$BASE_DIR/redis-temp"
# Move contents up (may be nested in a subdirectory)
INNER=$(ls "$BASE_DIR/redis-temp/")
if [ -d "$BASE_DIR/redis-temp/$INNER" ]; then
    mv "$BASE_DIR/redis-temp/$INNER/"* "$BASE_DIR/redis/"
else
    mv "$BASE_DIR/redis-temp/"* "$BASE_DIR/redis/"
fi
rm -rf "$BASE_DIR/redis-temp" "$BASE_DIR/redis.zip"
echo "Redis v7.4.3 ready. Starting..."
"$BASE_DIR/redis/redis-server.exe" &
echo "Redis started."
