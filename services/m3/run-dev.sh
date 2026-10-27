#!/usr/bin/env bash
# TEMPORARY-DEPENDENCY: TEMP-M3-D-01 / TEMP-M3-M1-01. Local synthetic demo only.
set -euo pipefail
m3_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$m3_root"
mkdir -p services/m3/.local
export M3_MODE=development
export M3_DATABASE_URL="${M3_DATABASE_URL:-sqlite:///$m3_root/services/m3/.local/work-orders.sqlite3}"
export M3_M1_MODE="${M3_M1_MODE:-stub}"
echo 'M3 development mode: synthetic identities and rooms. M1 stub is not real seat integration.'
if command -v uv >/dev/null 2>&1; then
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$m3_root/.uv-cache}"
  exec uv run --frozen python -m uvicorn services.m3.main:app --host 127.0.0.1 --port 3103
elif [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m uvicorn services.m3.main:app --host 127.0.0.1 --port 3103
else
  echo 'Install project dependencies with uv sync --frozen first.' >&2
  exit 1
fi
