#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
VIDEO_PATH="${VIDEO_PATH:-/path/to/video.mp4}"
QUERY_IMAGE="${QUERY_IMAGE:-/path/to/person.jpg}"

curl -X POST "${BASE_URL}/api/v1/cameras" \
  -H "Content-Type: application/json" \
  -d '{"camera_id":"cam_dorm_gate_01","name":"宿舍区东门摄像头01","location":"宿舍区东门","lat":31.0001,"lng":121.0001}'

VIDEO_ID="$(
  curl -s -X POST "${BASE_URL}/api/v1/videos/upload" \
    -F "file=@${VIDEO_PATH}" \
    -F "camera_id=cam_dorm_gate_01" \
    -F "recorded_at=2026-07-01T09:00:00" \
    -F "frame_interval_sec=1.0" \
  | python -c 'import json,sys; print(json.load(sys.stdin)["video_id"])'
)"

echo "VIDEO_ID=${VIDEO_ID}"

curl -X POST "${BASE_URL}/api/v1/videos/${VIDEO_ID}/index" | python -m json.tool

curl -X POST "${BASE_URL}/api/v1/search/by-image" \
  -F "files=@${QUERY_IMAGE}" \
  -F "top_k=50" \
  -F "min_score=0.55" \
  | python -m json.tool
