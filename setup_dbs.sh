#!/bin/bash
set -e

BASE_DIR="$(dirname "$0")/local-dbs"
echo "Setting up local databases in $BASE_DIR"

mkdir -p "$BASE_DIR/redis"
mkdir -p "$BASE_DIR/mongodb/data/db"
mkdir -p "$BASE_DIR/mongodb-temp"

echo "Downloading Redis (v7.4.3 Windows build)..."
curl -L "https://github.com/redis-windows/redis-windows/releases/download/7.4.3/Redis-7.4.3-Windows-x64-msys2.zip" -o "$BASE_DIR/redis.zip"
echo "Extracting Redis..."
mkdir -p "$BASE_DIR/redis-temp"
tar -xf "$BASE_DIR/redis.zip" -C "$BASE_DIR/redis-temp"
mv "$BASE_DIR"/redis-temp/*/* "$BASE_DIR/redis/" 2>/dev/null || mv "$BASE_DIR"/redis-temp/* "$BASE_DIR/redis/"
rm -rf "$BASE_DIR/redis-temp"

echo "Downloading MongoDB (v7.0.5)..."
curl -L "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.5.zip" -o "$BASE_DIR/mongodb.zip"
echo "Extracting MongoDB..."
tar -xf "$BASE_DIR/mongodb.zip" -C "$BASE_DIR/mongodb-temp"

mv "$BASE_DIR"/mongodb-temp/mongodb-windows-x86_64-*/* "$BASE_DIR/mongodb/"
rm -rf "$BASE_DIR/mongodb-temp"

echo "Cleaning up archives..."
rm "$BASE_DIR/redis.zip" "$BASE_DIR/mongodb.zip"

echo "Setup complete."
