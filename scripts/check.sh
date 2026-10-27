#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uv-cache}"
  python_cmd=(uv run --frozen python)
elif [[ -x .venv/bin/python ]]; then
  python_cmd=(.venv/bin/python)
else
  echo "Python environment not found: install uv or create .venv with Python 3.12" >&2
  exit 1
fi

node scripts/check-contracts.mjs
"${python_cmd[@]}" -m compileall -q services
"${python_cmd[@]}" -m unittest discover -s services/m3/tests -p 'test_*.py'
"${python_cmd[@]}" scripts/smoke.py
npm --prefix apps/web run typecheck
node --test apps/web/src/modules/m3/tests/adapter.test.cjs
npm --prefix apps/web run build
