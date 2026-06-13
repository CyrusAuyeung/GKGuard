#!/usr/bin/env bash
set -euo pipefail

SOURCE_ENV="${1:-torch126}"
TARGET_ENV="${2:-campusvision-c1}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found. Please initialize conda first."
  exit 1
fi

CONDA_BASE="$(conda info --base)"
# shellcheck source=/dev/null
source "${CONDA_BASE}/etc/profile.d/conda.sh"

if conda env list | awk '{print $1}' | grep -qx "${TARGET_ENV}"; then
  echo "Conda env ${TARGET_ENV} already exists. Reusing it."
else
  echo "Cloning conda env ${SOURCE_ENV} -> ${TARGET_ENV}"
  conda create -y -n "${TARGET_ENV}" --clone "${SOURCE_ENV}"
fi

conda activate "${TARGET_ENV}"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python scripts/check_env.py

echo
echo "Done."
echo "Next:"
echo "  conda activate ${TARGET_ENV}"
echo "  cp .env.example .env"
echo "  bash scripts/run_dev.sh"
