#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "1) health"
curl -s "${BASE_URL}/health" | python -m json.tool

echo
echo "2) create demo camera"
curl -s -X POST "${BASE_URL}/api/v1/cameras" \
  -H "Content-Type: application/json" \
  -d '{"camera_id":"cam_demo_01","name":"Demo Camera 01","location":"Demo Gate","lat":31.0,"lng":121.0}' \
  | python -m json.tool

echo
echo "Smoke test finished. Upload a real video next."
