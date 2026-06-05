#!/bin/bash
echo "Stopping Redis..."
taskkill.exe -F -IM redis-server.exe || true

echo "Stopping MongoDB..."
taskkill.exe -F -IM mongod.exe || true

echo "Databases stopped."
