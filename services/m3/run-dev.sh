#!/usr/bin/env bash
# TEMPORARY-DEPENDENCY M3-D-DEV / M3-M1-DEV. Loopback-only demo startup.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p services/m3/.local
export M3_MODE=development
export M3_DIRECTORY_MODE=development
export M3_DATABASE_URL="${M3_DATABASE_URL:-sqlite:///services/m3/.local/work-orders.sqlite3}"
export M3_M1_MODE="${M3_M1_MODE:-development-http}"
PYTHON_BIN="${M3_PYTHON:-.venv/bin/python}"
stub_pid=""
cleanup() {
  if [[ -n "$stub_pid" ]]; then kill "$stub_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
if [[ "$M3_M1_MODE" == "development-http" ]]; then
  export M3_M1_BASE_URL="http://127.0.0.1:3113"
  export M3_M1_TOKEN="m3-development-only"
  "$PYTHON_BIN" -m services.m3.dev_m1_stub &
  stub_pid=$!
elif [[ "$M3_M1_MODE" != "http" ]]; then
  echo 'M3_M1_MODE must be http or development-http' >&2
  exit 1
fi
echo 'M3 development mode: synthetic identities/directory; inspect /api/m3/v1/context.'
"$PYTHON_BIN" -m uvicorn services.m3.main:app --host 127.0.0.1 --port 3103
