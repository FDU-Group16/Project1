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

"${python_cmd[@]}" scripts/check-dependencies.py
"${python_cmd[@]}" scripts/test-dependencies.py
"${python_cmd[@]}" scripts/test-staging-test-accounts.py
node scripts/check-contracts.mjs
"${python_cmd[@]}" -m services.m3.export_contract --check
"${python_cmd[@]}" -m compileall -q services
"${python_cmd[@]}" scripts/smoke.py
if [[ "${BUSINESS_TEST_EXTERNAL:-0}" == "1" ]]; then
  "${python_cmd[@]}" scripts/test-business.py --external
else
  "${python_cmd[@]}" scripts/test-business.py
fi
"${python_cmd[@]}" -m pytest services/m3/tests -q
"${python_cmd[@]}" services/m3/tests/mutation_check.py
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
