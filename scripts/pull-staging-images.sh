#!/usr/bin/env bash
set -euo pipefail
set +x

sha="${1:?Pass the release SHA}"
registry_user="${2:?Pass the registry user}"
api_image="${3:?Pass the API digest reference}"
web_image="${4:?Pass the Web digest reference}"
postgres_image="${5:?Pass the PostgreSQL digest reference}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ||
      ! "$registry_user" =~ ^[A-Za-z0-9_-]+(\[bot\])?$ ]]; then
  echo "Invalid release SHA or registry user" >&2
  exit 1
fi
missing_images=()
for image in "$api_image" "$web_image" "$postgres_image"; do
  if [[ ! "$image" =~ ^ghcr\.io/[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$ ]]; then
    echo "Expected immutable GHCR image references" >&2
    exit 1
  fi
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "Reusing local image $image"
  else
    missing_images+=("$image")
  fi
done

# Consume the credential even when every digest is already available locally.
IFS= read -r registry_token
: "${registry_token:?Registry token is required on stdin}"
if (( ${#missing_images[@]} > 0 )); then
  umask 077
  registry_config="$(mktemp -d)"
  trap 'rm -rf -- "$registry_config"' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  export DOCKER_CONFIG="$registry_config"
  printf '%s\n' "$registry_token" | docker login ghcr.io --username "$registry_user" --password-stdin
  unset registry_token
  for image in "${missing_images[@]}"; do
    docker pull --platform linux/amd64 "$image"
  done
fi
unset registry_token

# Prepare every digest before changing aliases or touching running containers.
for service in m1 m2 m3 d; do
  docker tag "$api_image" "campus-resource-${service}:${sha}"
done
docker tag "$web_image" "campus-resource-web:${sha}"
docker tag "$postgres_image" "campus-resource-postgres:${sha}"
