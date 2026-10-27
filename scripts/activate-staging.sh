#!/usr/bin/env bash
set -Eeuo pipefail

sha="${1:?Pass the commit SHA to deploy}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Expected a full commit SHA" >&2
  exit 1
fi

deployment_root="$(readlink -f "${HOME}/campus-resource-staging")"
release="${deployment_root}/releases/${sha}"
env_file="${deployment_root}/.env"
current_link="${deployment_root}/current"

if [[ ! -f "$release/compose.staging.yaml" || ! -f "$env_file" ]]; then
  echo "Staging release or server-side .env file is missing" >&2
  exit 1
fi

previous_release=""
if [[ -L "$current_link" ]]; then
  previous_release="$(readlink -f "$current_link")"
  if [[ "$previous_release" != "${deployment_root}/releases/"* ||
        ! -f "$previous_release/compose.staging.yaml" ]]; then
    echo "Current release link points outside the release directory" >&2
    exit 1
  fi
fi

compose_for() {
  local source_dir="$1"
  shift
  DEPLOY_SHA="${source_dir##*/}" docker compose --env-file "$env_file" -f "$source_dir/compose.staging.yaml" "$@"
}

healthy() {
  local source_dir="$1"
  compose_for "$source_dir" exec -T postgres pg_isready -U campus -d campus >/dev/null 2>&1 || return 1
  local port
  for port in 3101 3102 3103 3104; do
    curl --fail --silent --max-time 3 "http://127.0.0.1:${port}/healthz" >/dev/null || return 1
  done
  local web_address
  web_address="$(compose_for "$source_dir" port web 80)" || return 1
  if [[ "$web_address" == 0.0.0.0:* ]]; then
    web_address="127.0.0.1:${web_address##*:}"
  fi
  curl --fail --silent --max-time 3 "http://${web_address}/" >/dev/null || return 1
  if [[ -f "$source_dir/services/m3/export_contract.py" ]]; then
    curl --fail --silent --max-time 3 "http://${web_address}/api/m3/v1/context" >/dev/null || return 1
  fi
}

if [[ "${2:-}" == "--check" ]]; then
  healthy "$release"
  exit
fi

wait_until_healthy() {
  local source_dir="$1"
  local attempt
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if healthy "$source_dir"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

rollback() {
  local status=$?
  trap - ERR
  rm -f "${deployment_root}/.current-next"
  echo "Staging deployment of $sha failed; restoring the previous release" >&2
  if [[ -n "$previous_release" ]]; then
    if ! compose_for "$previous_release" up -d --no-build --pull never --remove-orphans ||
       ! wait_until_healthy "$previous_release"; then
      echo "Automatic application rollback also failed; inspect the server" >&2
    else
      ln -sfn "$previous_release" "${deployment_root}/.current-next"
      mv -Tf "${deployment_root}/.current-next" "$current_link"
    fi
  else
    compose_for "$release" down || true
    rm -f "$current_link"
  fi
  exit "$status"
}

compose_for "$release" config --quiet
ln -sfn "$release" "${deployment_root}/.current-next"
trap rollback ERR
compose_for "$release" up -d --no-build --pull never --remove-orphans
wait_until_healthy "$release"
mv -Tf "${deployment_root}/.current-next" "$current_link"
trap - ERR

printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sha" >> "${deployment_root}/deployments.log" ||
  echo "Warning: could not append deployments.log; current still records the deployed SHA" >&2
echo "Staging is healthy at commit $sha"
