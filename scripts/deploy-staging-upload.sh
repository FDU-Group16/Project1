#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${STAGING_SSH_HOST:?STAGING_SSH_HOST is required}"
: "${STAGING_SSH_USER:?STAGING_SSH_USER is required}"

if [[ ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Expected a full commit SHA" >&2
  exit 1
fi
if [[ ! "$STAGING_SSH_HOST" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] ||
   [[ ! "$STAGING_SSH_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]]; then
  echo "Invalid staging SSH host or user" >&2
  exit 1
fi

ssh_port="${STAGING_SSH_PORT:-22}"
if [[ ! "$ssh_port" =~ ^[0-9]{1,5}$ ]] ||
   (( 10#$ssh_port < 1 || 10#$ssh_port > 65535 )); then
  echo "Invalid staging SSH port" >&2
  exit 1
fi

ssh_key_file="${HOME}/.ssh/staging_key"
known_hosts_file="${HOME}/.ssh/known_hosts"
if [[ ! -s "$ssh_key_file" || ! -s "$known_hosts_file" ]]; then
  echo "Staging SSH key and verified known_hosts are required" >&2
  exit 1
fi

if [[ "$(git rev-parse HEAD)" != "$GITHUB_SHA" ]]; then
  echo "Checked-out commit does not match the workflow commit" >&2
  exit 1
fi
DEPLOY_SHA="$GITHUB_SHA" docker compose --env-file .env.example \
  -f compose.staging.yaml config --quiet

ssh_options=(
  -p "$ssh_port"
  -i "$ssh_key_file"
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="$known_hosts_file"
  -o ConnectTimeout=15
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
)
ssh_target="${STAGING_SSH_USER}@${STAGING_SSH_HOST}"

current_sha="$(ssh "${ssh_options[@]}" "$ssh_target" \
  'if [ -L "$HOME/campus-resource-staging/current" ]; then basename "$(readlink -f "$HOME/campus-resource-staging/current")"; fi')"
if [[ "$current_sha" =~ ^[0-9a-f]{40}$ ]] &&
   git cat-file -e "${current_sha}^{commit}" 2>/dev/null &&
   git merge-base --is-ancestor "$GITHUB_SHA" "$current_sha"; then
  if ssh "${ssh_options[@]}" "$ssh_target" \
       "bash \"\$HOME/campus-resource-staging/current/scripts/activate-staging.sh\" \"$current_sha\" --check"; then
    echo "Staging already runs $GITHUB_SHA or a healthy newer descendant; skipping"
    exit 0
  fi
  echo "Recorded staging release is unhealthy; redeploying $GITHUB_SHA" >&2
fi

ssh "${ssh_options[@]}" "$ssh_target" 'docker info >/dev/null && docker compose version >/dev/null'

api_image="campus-resource-m1:${GITHUB_SHA}"
docker build --pull --platform linux/amd64 -f docker/api.Dockerfile -t "$api_image" .
for service in m2 m3 d; do
  docker tag "$api_image" "campus-resource-${service}:${GITHUB_SHA}"
done
docker build --pull --platform linux/amd64 -f docker/web.Dockerfile \
  -t "campus-resource-web:${GITHUB_SHA}" .
docker pull --platform linux/amd64 postgres:18-alpine
docker tag postgres:18-alpine "campus-resource-postgres:${GITHUB_SHA}"

docker save \
  "campus-resource-m1:${GITHUB_SHA}" \
  "campus-resource-m2:${GITHUB_SHA}" \
  "campus-resource-m3:${GITHUB_SHA}" \
  "campus-resource-d:${GITHUB_SHA}" \
  "campus-resource-web:${GITHUB_SHA}" \
  "campus-resource-postgres:${GITHUB_SHA}" |
  gzip -1 |
  ssh "${ssh_options[@]}" "$ssh_target" \
    'bash -o pipefail -c "gzip -dc | docker image load"'

ssh "${ssh_options[@]}" "$ssh_target" \
  "mkdir -p \"\$HOME/campus-resource-staging/releases/$GITHUB_SHA\""
git archive --format=tar HEAD | ssh "${ssh_options[@]}" "$ssh_target" \
  "tar -xf - -C \"\$HOME/campus-resource-staging/releases/$GITHUB_SHA\""
ssh "${ssh_options[@]}" "$ssh_target" \
  "bash \"\$HOME/campus-resource-staging/releases/$GITHUB_SHA/scripts/activate-staging.sh\" \"$GITHUB_SHA\""
