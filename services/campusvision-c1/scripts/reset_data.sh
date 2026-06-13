#!/usr/bin/env bash
set -euo pipefail

rm -rf data/campusvision.sqlite3 data/frames data/uploads
mkdir -p data/uploads/videos data/uploads/query_images data/frames

echo "Local C1 data reset."
