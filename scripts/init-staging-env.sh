#!/usr/bin/env bash
set -euo pipefail

web_bind_address="${STAGING_WEB_BIND_ADDRESS:-127.0.0.1}"
if [[ ! "$web_bind_address" =~ ^[0-9.]+$ ]]; then
  echo "STAGING_WEB_BIND_ADDRESS must be an IPv4 address" >&2
  exit 1
fi
web_port="${STAGING_WEB_PORT:-8080}"
if [[ ! "$web_port" =~ ^[0-9]{1,5}$ ]] ||
   (( 10#$web_port < 1 || 10#$web_port > 65535 )); then
  echo "STAGING_WEB_PORT must be a TCP port from 1 to 65535" >&2
  exit 1
fi

deployment_root="${HOME}/campus-resource-staging"
umask 077
install -d -m 700 "$deployment_root" "$deployment_root/releases"
if [[ -e "$deployment_root/.env" ]]; then
  echo "Preserving existing staging .env at $deployment_root/.env"
  exit 0
fi

env_temp="$(mktemp "$deployment_root/.env.XXXXXX")"
trap 'rm -f "$env_temp"' EXIT
printf 'POSTGRES_PASSWORD=%s\nSTAGING_WEB_BIND_ADDRESS=%s\nSTAGING_WEB_PORT=%s\n' \
  "$(openssl rand -hex 32)" "$web_bind_address" "$web_port" > "$env_temp"
chmod 600 "$env_temp"
mv "$env_temp" "$deployment_root/.env"
trap - EXIT
echo "Created private staging .env at $deployment_root/.env"
