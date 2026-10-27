#!/usr/bin/env bash
# Explicit opt-in for the existing course staging deployment; never prints secrets.
set -euo pipefail
set +x
umask 077
if [[ "${1:-}" != "--course-test-site" || $# -gt 2 ]]; then
  echo 'Usage: enable-staging-test-accounts.sh --course-test-site [--credentials-stdin]' >&2
  exit 1
fi
credential_args=()
if [[ $# -eq 2 ]]; then
  [[ "$2" == "--credentials-stdin" ]] || exit 1
  credential_args+=(--credentials-stdin)
fi
deployment_root="$(readlink -f "${HOME}/campus-resource-staging")"
release="$(readlink -f "${deployment_root}/current")"
sha="${release##*/}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ || "$release" != "$deployment_root/releases/"* ||
      ! -f "$release/scripts/bootstrap-test-accounts.py" ]]; then
  echo 'Deploy the test-account implementation before running setup.' >&2
  exit 1
fi
compose=(docker compose --env-file "$deployment_root/.env" -f "$release/compose.staging.yaml")
export DEPLOY_SHA="$sha"
"${compose[@]}" up -d --no-build --pull never postgres </dev/null
# stdin belongs exclusively to the optional secret mapping, never a shell script.
"${compose[@]}" run --rm --no-deps -T --entrypoint python \
  -v "$deployment_root:/staging" -v "$release/scripts:/bootstrap-scripts:ro" \
  d-api /bootstrap-scripts/bootstrap-test-accounts.py --course-test-site \
  --env-file /staging/.env --output /staging/test-accounts.json "${credential_args[@]}"
"${compose[@]}" up -d --no-build --pull never d-api m1-api m3-api </dev/null
# Nginx resolves the upstream service IPs at startup. Refresh it after APIs are
# recreated with the newly completed database environment.
"${compose[@]}" up -d --no-build --pull never --no-deps --force-recreate web </dev/null
ready=0
for ((attempt=1; attempt<=30; attempt++)); do
  if "${compose[@]}" run --rm --no-deps -T --entrypoint python \
      -v "$deployment_root/test-accounts.json:/private-test-accounts.json:ro" \
      -v "$release/scripts:/bootstrap-scripts:ro" \
      d-api /bootstrap-scripts/verify-staging-test-accounts.py </dev/null; then
    ready=1
    break
  else
    status=$?
    if [[ "$status" != 75 ]]; then
      echo 'Test-account business verification failed; stopping without repeated password attempts.' >&2
      exit "$status"
    fi
  fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  echo 'Test accounts initialized, but business verification failed. Inspect API configuration; do not report deployment as complete.' >&2
  exit 1
fi
echo 'Password login and M3 business access verified on the server.'
echo "Private credentials: $deployment_root/test-accounts.json (keep this file out of Git and logs)."
